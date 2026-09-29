"""One live query for the CLI and the API. The wide list reads a checklist after admission, via the ZDR client."""
from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import date

import httpx

from ts.checklist import CHECKLIST_VERSION, annotate_checklist

from ts.fanout import load_theme_plan, merge_theme_reports
from ts.mine import CLOSED, direction, discover
from ts.harness import TOP_N, Harness, RunReport
from ts.persist import load_report, public_report, save_report
from ts.reach import annotate_reach
from ts.scale import annotate_scopes
from ts.scoring.order import scope_rank, sort_admitted
from ts.scoring.scorer import load_rules
from ts.settings import Settings, load
from ts.sources.connectors import (
    ArxivConnector,
    ClinicalTrialsConnector,
    CordisConnector,
    CrossrefConnector,
    DoajConnector,
    EuropePmcConnector,
    GithubConnector,
    HalConnector,
    IetfConnector,
    NihConnector,
    NsfConnector,
    OpenAlexConnector,
    OpenReviewConnector,
    SearxConnector,
    SecConnector,
)


CORPUS = "live-w19"


def _key(query: str, rules_version: str, corpus: str = CORPUS) -> str:
    return hashlib.sha256(f"{query}|{corpus}|{rules_version}".encode()).hexdigest()


def _maker(session_factory):
    """session_factory() from ts.db returns a maker. A passed maker is used as-is."""
    if session_factory is None:
        from ts.db import session_factory as build
        return build()
    return session_factory


def run_query(query: str, *, limit: int = 3, extract: bool = False, settings: Settings | None = None,
              connectors=None, session_factory=None, _theme: bool = False, as_of: str | None = None) -> dict:
    # The extractor argument is ignored. Passing it into Harness.run collapses every find into one card.
    _ = extract
    s = settings or load()
    plan = load_theme_plan()
    as_of = as_of or date.today().isoformat()
    if not _theme:
        found = direction(query, plan.get("frame") or [])
        if found["mode"] == "no_direction":
            return _empty_direction(query, plan, as_of, s, session_factory)
        return _run_mined(
            query, plan, limit=limit, settings=s, connectors=connectors,
            session_factory=session_factory, as_of=as_of,
        )
    corpus = f"{CORPUS}+{as_of}"
    key = _key(query, s.rules_version, corpus=corpus)
    factory = _maker(session_factory)
    with factory() as session:
        stored = load_report(session, key)
    if stored is not None:
        stored["repeated"] = True
        return stored
    historical = as_of < date.today().isoformat()
    report = Harness(rules_version=s.rules_version, snapshot_dir=s.snapshot_dir, corpus_version=corpus).run(
        query, connectors if connectors is not None else default_connectors(s, as_of=as_of, historical=historical),
        limit=limit, extractor=None, chain=False, countersearch=False, as_of=as_of,
    )
    report = replace(report, id=key[:16], idempotency_key=key, corpus_version=corpus)
    if not _theme:
        tail = [card for card in report.exclusion_registry if card.get("policy_reason") == "beyond_top_n"]
        held = [card for card in report.exclusion_registry if card.get("policy_reason") != "beyond_top_n"]
        checked = annotate_checklist(list(report.top), tail, s, query=query)
        report.top = sort_admitted(list(checked["top"]))[:TOP_N]
        report.unread = list(checked.get("unread") or [])
        report.exclusion_registry = held + list(checked["excluded"]) + list(checked["overflow"])
        report.shortfall = TOP_N - len(report.top)
        if report.top:
            report.card = dict(report.top[0])
            report.card.setdefault("rules_version", s.rules_version)
        else:
            report.card = {
                **report.card,
                "label": None,
                "confidence": None,
            }
    with factory() as session:
        save_report(session, report)
    return public_report(report)


def _empty_card(rules) -> dict:
    return {
        "label": None,
        "confidence": None,
        "policy_action": "WATCHLIST",
        "policy_reason": "no_verified_change",
        "reason_codes": [],
        "predictors": [],
        "rules_version": rules["version"],
        "chain_link": {},
    }


def _empty_direction(query, plan, as_of, settings, session_factory) -> dict:
    rules = load_rules(settings.rules_version)
    corpus = f"{CORPUS}+{as_of}+{plan['version']}+{CHECKLIST_VERSION}"
    key = _key(query, rules["version"], corpus=corpus)
    factory = _maker(session_factory)
    with factory() as session:
        stored = load_report(session, key)
    if stored is not None:
        stored["repeated"] = True
        return stored
    report = RunReport(
        id=key[:16], query=query, idempotency_key=key, repeated=False,
        steps=[{"name": "direction", "status": "ok", "mode": "no_direction"}],
        sources=[], events=[], card=_empty_card(rules), top=[], shortfall=TOP_N,
        exclusion_registry=[], corpus_version=corpus,
        fanout={"version": plan["version"], "as_of": as_of, "direction": {"mode": "no_direction"},
                "closed_sources": list(CLOSED), "themes": []},
    )
    with factory() as session:
        save_report(session, report)
    return public_report(report)


def _seed_themes(mined: dict) -> list[dict]:
    """The operator's own words, searched before any mined phrase."""
    direction = mined.get("direction") or {}
    if direction.get("mode") == "narrow" and direction.get("object"):
        text = direction["object"]
        return [{"id": "seed", "title": text, "query": text, "language": "operator", "seed": True}]
    if direction.get("mode") != "wide":
        return []
    themes = []
    seen = set()
    if mined.get("labels_match") in {"exact", "lexeme"}:
        for lang, label in (mined.get("labels") or {}).items():
            if not label or label.casefold() in seen:
                continue
            seen.add(label.casefold())
            themes.append({"id": f"seed-{lang}", "title": label, "query": label, "language": lang, "seed": True})
    text = mined.get("operator_text")
    if text and text.casefold() not in seen:
        themes.append({"id": "seed-operator", "title": text, "query": text, "language": "operator", "seed": True})
    return themes


def _run_mined(query, plan, *, limit, settings, connectors, session_factory, as_of) -> dict:
    """One stored run. Phrases come from this window's titles."""
    rules = load_rules(settings.rules_version)
    corpus = f"{CORPUS}+{as_of}+{plan['version']}+{CHECKLIST_VERSION}"
    key = _key(query, rules["version"], corpus=corpus)
    factory = _maker(session_factory)
    with factory() as session:
        stored = load_report(session, key)
    if stored is not None:
        stored["repeated"] = True
        return stored
    mined = discover(query, plan, as_of, _http_get(), api_key=settings.openalex_key)
    if mined.get("error") in {"no_key", "network"}:
        return {
            "run_id": key[:16], "run_status": "failed", "query": query, "repeated": False,
            "signal_label": None, "confidence": None, "policy_action": "WATCHLIST",
            "policy_reason": mined["error"], "reason_codes": [], "predictors": [],
            "sources": [], "events": 0, "top": [], "shortfall": TOP_N,
            "exclusion_registry": [], "counters": {"sources": 0}, "fanout": mined,
        }
    parts = []
    seen_query = set()
    for theme in _seed_themes(mined) + list(mined["concepts"]):
        text = (theme.get("query") or "").strip()
        if not text or text.casefold() in seen_query:
            continue
        seen_query.add(text.casefold())
        report = run_query(
            theme["query"], limit=limit, settings=settings,
            connectors=connectors, session_factory=session_factory, _theme=True, as_of=as_of,
        )
        parts.append((theme, list(report.get("top") or [])))
    merged = merge_theme_reports(parts, limit=TOP_N) if parts else {"top": [], "overflow": [], "themes": []}
    checked = annotate_checklist(merged["top"], merged["overflow"], settings, query=query)
    top = sorted(annotate_scopes(checked["top"], settings), key=scope_rank, reverse=True)
    top = annotate_reach(top, settings)
    card = dict(top[0]) if top else _empty_card(rules)
    card.setdefault("rules_version", rules["version"])
    sources = []
    seen = set()
    for item in top:
        for source in item.get("sources") or []:
            url = source.get("url")
            if url and url not in seen:
                seen.add(url)
                sources.append(source)
    report = RunReport(
        id=key[:16],
        query=query,
        idempotency_key=key,
        repeated=False,
        steps=[
            {"name": "mine", "status": "failed" if mined.get("error") else "ok", "error": mined.get("error")},
            {"name": "checklist", "status": "ok", **checked["stats"]},
        ],
        sources=sources,
        events=[{"key": item.get("technology")} for item in top],
        card=card,
        top=top,
        shortfall=TOP_N - len(top),
        exclusion_registry=list(checked["excluded"]) + list(checked["overflow"]),
        unread=list(checked.get("unread") or []),
        model_id=next((
            (item.get("checklist") or {}).get("model_id")
            for item in top
            if (item.get("checklist") or {}).get("model_id")
        ), None) or next((item.get("scope_model") for item in top if item.get("scope_model")), None),
        corpus_version=corpus,
        fanout={
            "version": plan["version"],
            "as_of": as_of,
            "themes": merged["themes"],
            "reader": "scale",
            "checklist": checked["stats"],
            "direction": mined.get("direction"),
            "seed": [theme.get("query") for theme, _cards in parts if theme.get("seed")],
            "sample": mined.get("sample"),
            "labels": mined.get("labels"),
            "labels_match": mined.get("labels_match"),
            "knives": mined.get("knives"),
            "closed_sources": mined.get("closed_sources"),
            "cut_by_cap12": mined.get("cut_by_cap12"),
            "calls": mined.get("calls"),
            "error": mined.get("error"),
        },
    )
    with factory() as session:
        save_report(session, report)
    return public_report(report)


def _http_get():
    headers = {"User-Agent": "thin-signals/0.1 (https://tsignal.aispaces.ru; research)", "Accept": "application/json"}

    def get(url: str) -> str:
        last = "fail"
        for attempt in (1, 2):
            try:
                response = httpx.get(url, timeout=40, follow_redirects=True, headers=headers)
            except httpx.HTTPError:
                last = "fail"
                if attempt == 1:
                    continue
                raise OSError("http fail") from None
            if response.status_code == 429 and attempt == 1:
                continue
            if response.status_code >= 400:
                last = str(response.status_code)
                raise OSError(f"http {last}") from None
            return response.text
        raise OSError(f"http {last}")

    return get


def default_connectors(s: Settings, as_of: str | None = None, historical: bool = False):
    """Every run calls every connector. `historical` is kept for callers; it drops nothing.

    The dated connectors carry `.until = as_of`; the harness drops hits published after the window.
    """
    _ = historical
    headers = {"User-Agent": "thin-signals/0.1 (https://tsignal.aispaces.ru; research)", "Accept": "application/json"}

    def get(url: str) -> str:
        response = httpx.get(url, timeout=40, follow_redirects=True, headers=headers)
        response.raise_for_status()
        return response.text

    def post(url: str, payload: dict) -> str:
        response = httpx.post(url, json=payload, timeout=40, headers={**headers, "Content-Type": "application/json"})
        response.raise_for_status()
        return response.text

    connectors = []
    if s.searxng_url:
        connectors.append(SearxConnector(s.searxng_url, get))
    dated = [
        ArxivConnector(get), OpenAlexConnector(get), CrossrefConnector(get), EuropePmcConnector(get),
        HalConnector(get),
    ]
    for item in dated:
        item.until = as_of
    dated[1].api_key = s.openalex_key
    connectors += dated
    connectors += [
        DoajConnector(get), OpenReviewConnector(get), GithubConnector(get),
        NsfConnector(get), NihConnector(post), CordisConnector(get), ClinicalTrialsConnector(get),
        IetfConnector(get), SecConnector(get),
    ]
    return connectors


def _extractor(s: Settings):
    """Kept for a single-card read. The live list does not call it."""
    from ts.extract import Extractor
    from ts.llm import OpenRouterClient
    return Extractor(OpenRouterClient(s), model=s.llm_primary, mode="ledger")
