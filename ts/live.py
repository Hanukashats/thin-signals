"""One live query for the CLI and the API. The wide list reads a checklist after admission, via the ZDR client."""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from time import monotonic

import httpx

from ts.checklist import CHECKLIST_VERSION, annotate_checklist
from ts.desk import near_miss_cards
from ts.fanout import _identity, is_wide, load_theme_plan, merge_theme_reports, theme_plan_fingerprint
from ts.harness import (
    RUN_CONTRACT_VERSION,
    TOP_N,
    Harness,
    RunReport,
    retrieval_fingerprint,
    transport_timeout,
)
from ts.persist import load_report, public_report, save_report
from ts.plain import REASONS, say
from ts.potential import rank_potential_cards
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
THEME_LOOKBACK_DAYS = 365


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _since(day: str) -> str:
    return (datetime.fromisoformat(day).date() - timedelta(days=THEME_LOOKBACK_DAYS)).isoformat()


def _key(
    query: str,
    rules_version: str,
    corpus: str = CORPUS,
    day: str | None = None,
    retrieval: str | None = None,
) -> str:
    """A repeat on the same UTC day returns the stored run. The next day searches again."""
    window = day or _today()
    return hashlib.sha256(
        f"{query}|{corpus}+{window}|{rules_version}|{RUN_CONTRACT_VERSION}|{retrieval or 'legacy'}".encode()
    ).hexdigest()


def _near_miss(registry: list[dict], settings: Settings) -> list[dict]:
    """Reach is read for the short list only, never for the whole registry."""
    cards = near_miss_cards({"exclusion_registry": registry})
    return annotate_reach(cards, settings) if cards else []


def _potential(registry: list[dict], settings: Settings, top: list[dict] | None = None) -> list[dict]:
    """Persist the separate evidence-triage queue; it never fills the admitted list."""
    cards = rank_potential_cards({"top": top or [], "exclusion_registry": registry})
    return annotate_reach(cards, settings) if cards else []


def _checklist_route(checked: dict) -> tuple[str | None, str | None]:
    """Return one model/provider pair from any card that the checklist read."""
    for bucket in ("top", "excluded", "unread"):
        for card in checked.get(bucket) or []:
            checklist = card.get("checklist") if isinstance(card, dict) else None
            if not isinstance(checklist, dict) or not checklist.get("model_id"):
                continue
            return str(checklist["model_id"]), (
                str(checklist["provider"]) if checklist.get("provider") else None
            )
    return None, None


def _wide_status(statuses: list[str]) -> str:
    """Fold theme run states without hiding a failed or degraded search."""
    if not statuses or all(status == "failed" for status in statuses):
        return "failed"
    if any(status != "succeeded" for status in statuses):
        return "degraded"
    return "succeeded"


def _tag_theme_card(card: dict, theme: dict) -> dict:
    """Keep a child verdict attributable when it does not enter the global reader."""
    return {
        **card,
        "theme": theme.get("id"),
        "theme_title": theme.get("title"),
        "theme_query": theme.get("query"),
    }


def _event_cards(report: dict) -> list[dict]:
    """Theme Harness emits one card per event across these disjoint buckets."""
    cards = []
    for bucket in ("top", "exclusion_registry", "unread"):
        for card in report.get(bucket) or []:
            if not isinstance(card, dict):
                continue
            try:
                count = int(card.get("events") or 0)
            except (TypeError, ValueError):
                count = 0
            if count > 0:
                cards.append(card)
    return cards


def _empty_card(rules_version: str, registry=None, unread=None) -> dict:
    """A run-level empty verdict; never borrow the first rejected card's verdict."""
    reasons = Counter(
        str(card.get("policy_reason"))
        for card in (registry or [])
        if isinstance(card, dict) and card.get("policy_reason")
    )
    unread_count = len([card for card in (unread or []) if isinstance(card, dict)])
    parts = [
        f"{say(REASONS, code, code)} — {count}"
        for code, count in sorted(reasons.items(), key=lambda item: (-item[1], item[0]))[:3]
    ]
    if unread_count:
        parts.append(f"нет доступного текста источника — {unread_count}")
    sentence = "В список никто не допущен."
    if parts:
        sentence += " Основные причины: " + "; ".join(parts) + "."
    return {
        "label": None,
        "confidence": None,
        "policy_action": "HOLD",
        "policy_reason": "no_admitted_cards",
        "reason_codes": [],
        "predictors": [],
        "rules_version": rules_version,
        "chain_link": {"score": 0, "families": [], "sentence": sentence},
    }


def _maker(session_factory):
    """session_factory() from ts.db returns a maker. A passed maker is used as-is."""
    if session_factory is None:
        from ts.db import session_factory as build
        return build()
    return session_factory


def run_query(query: str, *, limit: int = 3, extract: bool = False, settings: Settings | None = None,
              connectors=None, session_factory=None, _theme: bool = False, _day: str | None = None,
              _deadline_at: float | None = None,
              _parent_retrieval_fingerprint: str | None = None) -> dict:
    # The extractor argument is ignored. Passing it into Harness.run collapses every find into one card.
    _ = extract
    s = settings or load()
    day = _day or _today()
    plan = load_theme_plan()
    wide = is_wide(query, plan)
    deadline_at = _deadline_at
    if deadline_at is None:
        seconds = s.wide_search_deadline_seconds if wide else s.search_deadline_seconds
        deadline_at = monotonic() + max(0.0, seconds)
    if wide:
        return _run_wide(
            query, plan, limit=limit, extract=extract, settings=s,
            connectors=connectors, session_factory=session_factory, day=day,
            deadline_at=deadline_at,
        )
    corpus = CORPUS if _theme else f"{CORPUS}+{CHECKLIST_VERSION}"
    active_connectors = list(connectors) if connectors is not None else default_connectors(s)
    since = _since(day) if _theme else None
    fingerprint = retrieval_fingerprint(
        [connector.name for connector in active_connectors],
        limit=limit,
        since=since,
        max_workers=s.search_max_workers,
        deadline_seconds=s.search_deadline_seconds,
        source_timeout_seconds=s.source_timeout_seconds,
        parent_fingerprint=_parent_retrieval_fingerprint,
    )
    key = _key(
        query, s.rules_version, corpus=corpus, day=day, retrieval=fingerprint,
    )
    factory = _maker(session_factory)
    with factory() as session:
        stored = load_report(session, key)
    if stored is not None:
        stored["repeated"] = True
        return stored
    report = Harness(
        rules_version=s.rules_version, snapshot_dir=s.snapshot_dir, corpus_version=CORPUS,
        since=since, max_workers=s.search_max_workers,
        deadline_seconds=s.search_deadline_seconds,
    ).run(
        query, active_connectors,
        limit=limit, extractor=None, deadline_at=deadline_at,
    )
    report = replace(
        report, id=key[:16], idempotency_key=key, corpus_version=corpus,
        retrieval_fingerprint=fingerprint,
    )
    if not _theme:
        tail = [card for card in report.exclusion_registry if card.get("policy_reason") == "beyond_top_n"]
        held = [card for card in report.exclusion_registry if card.get("policy_reason") != "beyond_top_n"]
        checked = annotate_checklist(list(report.top), tail, s, query=query)
        report.top = sort_admitted(list(checked["top"]))[:TOP_N]
        report.unread = list(checked.get("unread") or [])
        report.exclusion_registry = held + list(checked["excluded"]) + list(checked["overflow"])
        report.shortfall = TOP_N - len(report.top)
        report.near_miss = _near_miss(report.exclusion_registry, s)
        report.potential = _potential(report.exclusion_registry, s, report.top)
        checklist_model, checklist_provider = _checklist_route(checked)
        if checklist_model:
            report.model_id = checklist_model
        if checklist_provider:
            report.provider = checklist_provider
        if report.top:
            report.card = dict(report.top[0])
            report.card.setdefault("rules_version", s.rules_version)
        else:
            report.card = _empty_card(
                s.rules_version,
                report.exclusion_registry,
                report.unread,
            )
    with factory() as session:
        save_report(session, report)
        if report.repeated:
            stored = load_report(session, key)
            if stored is not None:
                stored["repeated"] = True
                return stored
    return public_report(report)


def _run_wide(query, plan, *, limit, extract, settings, connectors, session_factory, day,
              deadline_at) -> dict:
    """One stored run for the mission sentence. Theme queries stay their own runs."""
    rules = load_rules(settings.rules_version)
    corpus = f"{CORPUS}+{plan['version']}+{CHECKLIST_VERSION}"
    active_connectors = list(connectors) if connectors is not None else default_connectors(settings)
    fingerprint = retrieval_fingerprint(
        [connector.name for connector in active_connectors],
        limit=limit,
        since=_since(day),
        max_workers=settings.search_max_workers,
        deadline_seconds=settings.search_deadline_seconds,
        source_timeout_seconds=settings.source_timeout_seconds,
        wide_deadline_seconds=settings.wide_search_deadline_seconds,
        parent_fingerprint=f"theme-plan:{theme_plan_fingerprint(plan)}",
    )
    key = _key(
        query, rules["version"], corpus=corpus, day=day, retrieval=fingerprint,
    )
    factory = _maker(session_factory)
    with factory() as session:
        stored = load_report(session, key)
    if stored is not None:
        stored["repeated"] = True
        return stored
    parts = []
    theme_statuses = []
    theme_runs = []
    theme_steps = []
    discovered_sources = []
    discovered_source_urls = set()
    event_identities: set[tuple] = set()
    theme_event_observations = 0
    child_exclusions: dict[tuple, dict] = {}
    child_exclusion_observations = 0
    skipped_themes = []
    for theme in plan["themes"]:
        if monotonic() >= deadline_at:
            parts.append((theme, []))
            theme_statuses.append("failed")
            skipped_themes.append(theme["id"])
            continue
        report = run_query(
            theme["query"], limit=limit, extract=extract, settings=settings,
            connectors=active_connectors, session_factory=session_factory, _theme=True, _day=day,
            _deadline_at=deadline_at,
            _parent_retrieval_fingerprint=fingerprint,
        )
        parts.append((theme, list(report.get("top") or [])))
        theme_status = str(report.get("run_status") or "failed")
        theme_statuses.append(theme_status)
        theme_runs.append({
            "id": theme["id"],
            "status": theme_status,
            "repeated": bool(report.get("repeated")),
        })
        event_cards = _event_cards(report)
        event_identities.update(_identity(card) for card in event_cards)
        try:
            theme_event_observations += max(0, int(report.get("events") or 0))
        except (TypeError, ValueError):
            pass
        for child_card in report.get("exclusion_registry") or []:
            if not isinstance(child_card, dict):
                continue
            child_exclusion_observations += 1
            tagged = _tag_theme_card(child_card, theme)
            child_exclusions.setdefault(_identity(tagged), tagged)
        retrieval = report.get("retrieval") if isinstance(report.get("retrieval"), dict) else {}
        for step in retrieval.get("connectors") or []:
            if isinstance(step, dict):
                safe_step = {
                    key: step[key]
                    for key in (
                        "name", "connector", "status", "error", "n",
                        "elapsed_ms", "queued_ms",
                    )
                    if key in step and isinstance(step[key], (str, int, float, bool))
                }
                if safe_step.get("name") and safe_step.get("connector"):
                    theme_steps.append({
                        **safe_step,
                        "theme": theme["id"],
                        "cached": bool(report.get("repeated")),
                    })
        for source in report.get("sources") or []:
            if not isinstance(source, dict):
                continue
            url = str(source.get("url") or "")
            identity = url or repr(sorted(source.items()))
            if identity in discovered_source_urls:
                continue
            discovered_source_urls.add(identity)
            discovered_sources.append(dict(source))
    merged = merge_theme_reports(parts, limit=TOP_N)
    # A theme query is not the operator's question. As one, it marks cross-theme papers ДРУГОЙ_МЕХАНИЗМ.
    checked = annotate_checklist(merged["top"], merged["overflow"], settings, query=None)
    top = sorted(annotate_scopes(checked["top"], settings), key=scope_rank, reverse=True)
    top = annotate_reach(top, settings)
    checklist_model, checklist_provider = _checklist_route(checked)
    registry = list(checked["excluded"]) + list(checked["overflow"])
    unread = list(checked.get("unread") or [])
    represented = {
        _identity(item)
        for item in [*top, *registry, *unread]
        if isinstance(item, dict)
    }
    for identity, child_card in child_exclusions.items():
        if identity in represented:
            continue
        registry.append(child_card)
        represented.add(identity)
    card = dict(top[0]) if top else _empty_card(
        rules["version"],
        registry,
        checked.get("unread"),
    )
    card.setdefault("rules_version", rules["version"])
    sources = list(discovered_sources)
    seen = {str(source.get("url") or "") for source in sources}
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
            {
                "name": "fanout",
                "status": (
                    "ok" if _wide_status(theme_statuses) == "succeeded"
                    else _wide_status(theme_statuses)
                ),
                "themes": len(plan["themes"]), "deadline_skipped": skipped_themes,
            },
            *theme_steps,
            {"name": "checklist", "status": "ok", **checked["stats"]},
        ],
        sources=sources,
        events=[
            {"key": hashlib.sha256(repr(identity).encode()).hexdigest()[:16]}
            for identity in sorted(event_identities, key=repr)
        ],
        card=card,
        top=top,
        shortfall=TOP_N - len(top),
        exclusion_registry=registry,
        status=_wide_status(theme_statuses),
        unread=unread,
        near_miss=_near_miss(registry, settings),
        potential=_potential(registry, settings, top),
        model_id=checklist_model or next((item.get("scope_model") for item in top if item.get("scope_model")), None),
        provider=checklist_provider,
        corpus_version=corpus,
        retrieval_fingerprint=fingerprint,
        fanout={
            "version": plan["version"],
            "themes": merged["themes"],
            "reader": "scale",
            "checklist": checked["stats"],
            "deadline_skipped": skipped_themes,
            "theme_runs": theme_runs,
            "discovered_events": len(event_identities),
            "theme_event_observations": theme_event_observations,
            "child_exclusion_observations": child_exclusion_observations,
            "unique_child_exclusions": len(child_exclusions),
        },
    )
    with factory() as session:
        save_report(session, report)
        if report.repeated:
            stored = load_report(session, key)
            if stored is not None:
                stored["repeated"] = True
                return stored
    return public_report(report)


def default_connectors(s: Settings):
    headers = {"User-Agent": "thin-signals/0.1 (research scan)", "Accept": "application/json"}

    def get(url: str) -> str:
        response = httpx.get(
            url, timeout=transport_timeout(getattr(s, "source_timeout_seconds", 40.0)),
            follow_redirects=True, headers=headers,
        )
        response.raise_for_status()
        return response.text

    def post(url: str, payload: dict) -> str:
        response = httpx.post(
            url, json=payload,
            timeout=transport_timeout(getattr(s, "source_timeout_seconds", 40.0)),
            headers={**headers, "Content-Type": "application/json"},
        )
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
