"""Checklist on cards that are already in the official list.

Same weights as the dataset scorer. A missing fragment is not a zero.
This module does not sort and does not call Harness.run.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from ts.extract import to_feature_vector
from ts.fanout import _identity
from ts.scale import fetch_abstract
from ts.scoring.scorer import load_rules, score

CHECKLIST_VERSION = "checklist-v7"
TEXT_HUNT = 4
BACKFILL_CAP = 5
DROP_COUNTERS = ("M01", "M02", "M03", "M05", "M06")


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _fragments(card: dict) -> tuple[list[str], list[str]]:
    fragments: list[str] = []
    urls: list[str] = []
    for source in card.get("sources") or []:
        if not isinstance(source, dict):
            continue
        snippet = str(source.get("snippet") or "").strip()
        if not snippet:
            continue
        name = str(source.get("name") or "").strip()
        fragments.append(f"{name}. {snippet}".strip(". "))
        urls.append(str(source.get("url") or ""))
        if len(fragments) >= 6:
            break
    if fragments:
        return fragments, urls
    abstract = fetch_abstract(card)
    if not abstract:
        return [], []
    url = ""
    for source in card.get("sources") or []:
        if isinstance(source, dict) and source.get("url"):
            url = str(source["url"])
            break
    return [abstract], [url]


def _hosts(card: dict) -> int:
    hosts = set()
    for source in card.get("sources") or []:
        if not isinstance(source, dict):
            continue
        url = str(source.get("url") or "")
        if url:
            hosts.add(_host(url) or url)
    return len(hosts)


def vector_for(card: dict, out: dict):
    """Ledger vector, with event counts taken from the find, not from the model."""
    fv = to_feature_vector(out, "ledger")
    fv.counters["M04"] = False
    planned = card.get("planned_not_deployment") or []
    planned_n = len(planned) if isinstance(planned, list) else 0
    try:
        events = int(card.get("events") or 0)
    except (TypeError, ValueError):
        events = 0
    evidence_events = max(0, events - planned_n)
    fv.evidence_events = evidence_events
    fv.independent_origins = min(_hosts(card), evidence_events)
    return fv


def _watchlist(rules: dict) -> float:
    mode = (rules.get("modes") or {}).get("ledger") or {}
    thresholds = mode.get("thresholds") or rules["thresholds"]
    return float(thresholds["watchlist"])


def _case_quote(out: dict, fragments: list[str], urls: list[str]) -> dict | None:
    for feature in out.get("features") or []:
        if not isinstance(feature, dict) or feature.get("code") != "P03":
            continue
        if feature.get("status") != "verified":
            return None
        match = re.search(r"\[(\d+)\]", str(feature.get("why") or ""))
        if not match:
            return None
        index = int(match.group(1))
        if index < 1 or index > len(fragments):
            return None
        url = urls[index - 1] if index - 1 < len(urls) else ""
        return {"text": fragments[index - 1][:300], "fragment": index, "url": url}
    return None


def _mark(row: dict, status: str, meta: dict | None = None) -> None:
    body = {"version": CHECKLIST_VERSION, "status": status}
    if meta:
        if meta.get("model_id"):
            body["model_id"] = meta.get("model_id")
        body["cached"] = bool(meta.get("cached"))
    row["checklist"] = body


def score_card(card: dict, reader, rules: dict) -> dict:
    row = dict(card)
    fragments, _urls = _fragments(row)
    if not fragments:
        _mark(row, "no_fragment")
        row["policy_reason"] = "no_source_text"
        row["confidence"] = None
        row["label"] = None
        return {"keep": False, "unread": True, "card": row}
    try:
        read = reader(row)
    except Exception as exc:
        _mark(row, "reader_failed")
        row["checklist"]["error"] = type(exc).__name__
        row["confidence"] = None
        row["label"] = None
        row["predictors"] = []
        return {"keep": True, "card": row}
    if not isinstance(read, dict) or not isinstance(read.get("output"), dict):
        _mark(row, "reader_failed")
        row["confidence"] = None
        row["label"] = None
        row["predictors"] = []
        return {"keep": True, "card": row}
    try:
        fv = vector_for(row, read["output"])
        result = score(fv, rules)
    except Exception:
        _mark(row, "reader_failed")
        row["confidence"] = None
        row["label"] = None
        row["predictors"] = []
        return {"keep": True, "card": row}
    row["label"] = result.label
    row["confidence"] = result.confidence
    row["reason_codes"] = list(result.reason_codes)
    row["predictors"] = list(result.predictors)
    _mark(row, "scored", read.get("meta") if isinstance(read.get("meta"), dict) else {})
    quote = _case_quote(
        read["output"],
        list(read.get("fragments") or fragments),
        list(read.get("urls") or []),
    )
    if quote:
        row["case_quote"] = quote
    fired = [code for code in DROP_COUNTERS if fv.counters.get(code)]
    if fired:
        row["policy_reason"] = "checklist_counter"
        row["checklist_quote"] = fv.evidence.get(fired[0], "")
        return {"keep": False, "card": row}
    if result.confidence is None or result.confidence < _watchlist(rules):
        row["policy_reason"] = "checklist_below_watchlist"
        row["checklist_quote"] = fv.evidence.get(fv.primary_pattern, "")
        return {"keep": False, "card": row}
    line = str((read.get("output") or {}).get("one_line_ru") or "").strip()
    if line.upper().replace(" ", "_").startswith("ДРУГОЙ_МЕХАНИЗМ"):
        row["policy_reason"] = "other_mechanism_after_read"
        row["checklist_quote"] = line
        return {"keep": False, "card": row}
    return {"keep": True, "card": row}


def _peek_index(pool: list[dict], theme: str, used: set) -> int | None:
    hunts = 0
    for index, card in enumerate(pool):
        if card.get("theme") != theme or _identity(card) in used:
            continue
        hunts += 1
        if hunts > TEXT_HUNT:
            return None
        if _fragments(card)[0]:
            return index
    return None


def apply_checklist(top: list[dict], overflow: list[dict], reader, rules: dict, *,
                    backfill_cap: int = BACKFILL_CAP) -> dict:
    kept: list[dict] = []
    excluded: list[dict] = []
    unread: list[dict] = []
    pool = [dict(card) for card in overflow]
    used = {_identity(card) for card in top}
    reads_used = 0
    attempted: set[str] = set()
    read = 0
    scored = 0
    unevaluated = 0

    def judge(card: dict) -> dict:
        nonlocal read, scored, unevaluated
        if _fragments(card)[0]:
            read += 1
        outcome = score_card(card, reader, rules)
        status = (outcome["card"].get("checklist") or {}).get("status")
        if status == "scored":
            scored += 1
        elif status in {"no_fragment", "reader_failed"}:
            unevaluated += 1
        return outcome

    def try_replace(theme: str, unread_card: dict | None = None) -> dict | None:
        nonlocal reads_used
        if reads_used >= backfill_cap:
            return None
        if theme is not None and theme in attempted:
            return None
        if theme is not None:
            attempted.add(theme)
        index = _peek_index(pool, theme, used)
        if index is None:
            return None
        nxt = pool.pop(index)
        reads_used += 1
        try:
            outcome = judge(nxt)
        except Exception:
            pool.insert(index, nxt)
            raise
        if outcome["keep"]:
            if unread_card is not None:
                unread_card["seat_replaced"] = True
                unread_card["policy_reason"] = "no_source_text_replaced"
            return outcome["card"]
        excluded.append(outcome["card"])
        return None

    for card in top:
        outcome = judge(card)
        if outcome["keep"]:
            kept.append(outcome["card"])
            continue
        if outcome.get("unread"):
            row = outcome["card"]
            unread.append(row)
            replacement = try_replace(card.get("theme"), row)
            if replacement:
                kept.append(replacement)
            continue
        excluded.append(outcome["card"])
        replacement = try_replace(card.get("theme"))
        if replacement:
            kept.append(replacement)
    kept_ids = {_identity(card) for card in kept}
    drop_ids = {_identity(card) for card in excluded}
    unread_ids = {_identity(card) for card in unread}
    leftover = [
        card for card in pool
        if _identity(card) not in kept_ids and _identity(card) not in drop_ids and _identity(card) not in unread_ids
    ]
    return {
        "top": kept,
        "excluded": excluded,
        "unread": unread,
        "overflow": leftover,
        "stats": {
            "read": read,
            "scored": scored,
            "unevaluated": unevaluated,
            "unread": len(unread),
            "dropped": len(excluded),
            "backfill": reads_used,
        },
    }


def make_reader(settings, query: str | None = None):
    from ts.extract import Extractor
    from ts.llm import OpenRouterClient

    extractor = Extractor(
        OpenRouterClient(settings),
        model=settings.llm_judge,
        mode="ledger",
        rules=load_rules(settings.rules_version),
    )

    def reader(card: dict):
        fragments, urls = _fragments(card)
        if not fragments:
            return None
        asked = str(card.get("theme_query") or query or "").strip()
        out, meta = extractor.extract({
            "technology": card.get("technology") or "",
            "fragments": fragments,
            **({"query": asked} if asked else {}),
        })
        return {"output": out, "meta": meta, "fragments": fragments, "urls": urls}

    return reader


def annotate_checklist(top: list[dict], overflow: list[dict], settings, query: str | None = None) -> dict:
    rules = load_rules(settings.rules_version)
    return apply_checklist(top, overflow, make_reader(settings, query), rules)
