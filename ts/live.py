"""One live query for the CLI and the API. The wide list reads a checklist after admission, via the ZDR client."""
from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx

from ts.checklist import CHECKLIST_VERSION, annotate_checklist
from ts.desk import near_miss_cards
from ts.fanout import is_wide, load_theme_plan, merge_theme_reports
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


CORPUS = "live-w18"
THEME_LOOKBACK_DAYS = 365


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _since(day: str) -> str:
    return (datetime.fromisoformat(day).date() - timedelta(days=THEME_LOOKBACK_DAYS)).isoformat()


def _key(query: str, rules_version: str, corpus: str = CORPUS, day: str | None = None) -> str:
    """A repeat on the same UTC day returns the stored run. The next day searches again."""
    window = day or _today()
    return hashlib.sha256(f"{query}|{corpus}+{window}|{rules_version}".encode()).hexdigest()


def _near_miss(registry: list[dict], settings: Settings) -> list[dict]:
    """Reach is read for the short list only, never for the whole registry."""
    cards = near_miss_cards({"exclusion_registry": registry})
    return annotate_reach(cards, settings) if cards else []


def _maker(session_factory):
    """session_factory() from ts.db returns a maker. A passed maker is used as-is."""
    if session_factory is None:
        from ts.db import session_factory as build
        return build()
    return session_factory


def run_query(query: str, *, limit: int = 3, extract: bool = False, settings: Settings | None = None,
              connectors=None, session_factory=None, _theme: bool = False, _day: str | None = None) -> dict:
    # The extractor argument is ignored. Passing it into Harness.run collapses every find into one card.
    _ = extract
    s = settings or load()
    day = _day or _today()
    plan = load_theme_plan()
    if is_wide(query, plan):
        return _run_wide(
            query, plan, limit=limit, extract=extract, settings=s,
            connectors=connectors, session_factory=session_factory, day=day,
        )
    corpus = CORPUS if _theme else f"{CORPUS}+{CHECKLIST_VERSION}"
    key = _key(query, s.rules_version, corpus=corpus, day=day)
    factory = _maker(session_factory)
    with factory() as session:
        stored = load_report(session, key)
    if stored is not None:
        stored["repeated"] = True
        return stored
    report = Harness(
        rules_version=s.rules_version, snapshot_dir=s.snapshot_dir, corpus_version=CORPUS,
        since=_since(day) if _theme else None,
    ).run(
        query, connectors if connectors is not None else default_connectors(s),
        limit=limit, extractor=None,
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
        report.near_miss = _near_miss(report.exclusion_registry, s)
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


def _run_wide(query, plan, *, limit, extract, settings, connectors, session_factory, day) -> dict:
    """One stored run for the mission sentence. Theme queries stay their own runs."""
    rules = load_rules(settings.rules_version)
    corpus = f"{CORPUS}+{plan['version']}+{CHECKLIST_VERSION}"
    key = _key(query, rules["version"], corpus=corpus, day=day)
    factory = _maker(session_factory)
    with factory() as session:
        stored = load_report(session, key)
    if stored is not None:
        stored["repeated"] = True
        return stored
    parts = []
    for theme in plan["themes"]:
        report = run_query(
            theme["query"], limit=limit, extract=extract, settings=settings,
            connectors=connectors, session_factory=session_factory, _theme=True, _day=day,
        )
        parts.append((theme, list(report.get("top") or [])))
    merged = merge_theme_reports(parts, limit=TOP_N)
    # A theme query is not the operator's question. As one, it marks cross-theme papers ДРУГОЙ_МЕХАНИЗМ.
    checked = annotate_checklist(merged["top"], merged["overflow"], settings, query=None)
    top = sorted(annotate_scopes(checked["top"], settings), key=scope_rank, reverse=True)
    top = annotate_reach(top, settings)
    card = dict(top[0]) if top else {
        "label": None,
        "confidence": None,
        "policy_action": "WATCHLIST",
        "policy_reason": "no_verified_change",
        "reason_codes": [],
        "predictors": [],
        "rules_version": rules["version"],
        "chain_link": {},
    }
    card.setdefault("rules_version", rules["version"])
    registry = list(checked["excluded"]) + list(checked["overflow"])
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
            {"name": "fanout", "status": "ok", "themes": len(plan["themes"])},
            {"name": "checklist", "status": "ok", **checked["stats"]},
        ],
        sources=sources,
        events=[{"key": item.get("technology")} for item in top],
        card=card,
        top=top,
        shortfall=TOP_N - len(top),
        exclusion_registry=registry,
        unread=list(checked.get("unread") or []),
        near_miss=_near_miss(registry, settings),
        model_id=next((
            (item.get("checklist") or {}).get("model_id")
            for item in top
            if (item.get("checklist") or {}).get("model_id")
        ), None) or next((item.get("scope_model") for item in top if item.get("scope_model")), None),
        corpus_version=corpus,
        fanout={
            "version": plan["version"],
            "themes": merged["themes"],
            "reader": "scale",
            "checklist": checked["stats"],
        },
    )
    with factory() as session:
        save_report(session, report)
    return public_report(report)


def default_connectors(s: Settings):
    headers = {"User-Agent": "thin-signals/0.1 (research scan)", "Accept": "application/json"}

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
    connectors += [
        ArxivConnector(get), OpenAlexConnector(get), CrossrefConnector(get), EuropePmcConnector(get),
        DoajConnector(get), HalConnector(get), OpenReviewConnector(get), GithubConnector(get),
        NsfConnector(get), NihConnector(post), CordisConnector(get), ClinicalTrialsConnector(get),
        IetfConnector(get), SecConnector(get),
    ]
    return connectors


def _extractor(s: Settings):
    """Kept for a single-card read. The live list does not call it."""
    from ts.extract import Extractor
    from ts.llm import OpenRouterClient
    return Extractor(OpenRouterClient(s), model=s.llm_primary, mode="ledger")
