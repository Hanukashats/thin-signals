"""Checklist on cards that are already in the official list.

Same weights as the dataset scorer. A missing fragment is not a zero.
This module does not sort and does not call Harness.run.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from ts.extract import to_feature_vector, validate_scoring_output
from ts.fanout import _identity
from ts.scale import fetch_abstract
from ts.scoring.scorer import load_rules, score

CHECKLIST_VERSION = "checklist-v16"
TEXT_HUNT = 4
# Four extra reads for each standing theme. One noisy theme must not spend the rest.
BACKFILL_CAP = TEXT_HUNT * 13
DROP_COUNTERS = ("M01", "M02", "M03", "M05", "M06")
# Connectors and the harness cut snippets here. A snippet this long was probably cut mid-text.
SNIPPET_CAP = 500
SOURCE_FRAGMENT_CAP = 6
COUNTER_FRAGMENT_CAP = 2
_FULL: dict[tuple[str, str], str] = {}
_FRAGMENT_REF = re.compile(r"\[(\d+)\]")


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _fuller(source: dict, snippet: str) -> str:
    """The official record text when the snippet was cut at the cap and the record says more."""
    if len(snippet) < SNIPPET_CAP:
        return snippet
    key = (str(source.get("url") or ""), str(source.get("doi") or ""))
    if key not in _FULL:
        if len(_FULL) >= 2048:
            _FULL.clear()
        _FULL[key] = fetch_abstract({"sources": [source]})
    text = _FULL[key].strip()
    return text if len(text) > len(snippet) else snippet


def _fragments(card: dict, full: bool = True) -> tuple[list[str], list[str]]:
    fragments: list[str] = []
    urls: list[str] = []
    for source in card.get("sources") or []:
        if not isinstance(source, dict):
            continue
        snippet = str(source.get("snippet") or "").strip()
        if not snippet:
            continue
        if full:
            snippet = _fuller(source, snippet)
        name = str(source.get("name") or "").strip()
        fragments.append(f"{name}. {snippet}".strip(". "))
        urls.append(str(source.get("url") or ""))
        if len(fragments) >= SOURCE_FRAGMENT_CAP:
            break
    counter_n = 0
    for source in card.get("counter_sources") or []:
        if not isinstance(source, dict):
            continue
        snippet = str(source.get("snippet") or "").strip()
        if not snippet:
            continue
        if full:
            snippet = _fuller(source, snippet)
        name = str(source.get("name") or "").strip()
        fragments.append(f"КОНТРПОИСК: {name}. {snippet}".strip(". "))
        urls.append(str(source.get("url") or ""))
        counter_n += 1
        if counter_n >= COUNTER_FRAGMENT_CAP:
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


def _has_fragment_reference(why: object, fragments: list[str]) -> bool:
    """A verified claim must cite at least one non-empty fragment that was actually read."""
    for raw_index in _FRAGMENT_REF.findall(str(why or "")):
        index = int(raw_index)
        if 1 <= index <= len(fragments) and str(fragments[index - 1]).strip():
            return True
    return False


def _uncited_verified(out: dict, fragments: list[str]) -> list[str]:
    missing: list[str] = []
    for feature in out.get("features") or []:
        if not isinstance(feature, dict) or feature.get("status") != "verified":
            continue
        if not _has_fragment_reference(feature.get("why"), fragments):
            missing.append(str(feature.get("code") or "UNKNOWN"))
    transition = out.get("transition") or {}
    if (
        isinstance(transition, dict)
        and transition.get("status") == "verified"
        and not _has_fragment_reference(transition.get("why"), fragments)
    ):
        missing.append("TR")
    for counter in out.get("counters") or []:
        if not isinstance(counter, dict) or counter.get("code") not in DROP_COUNTERS:
            continue
        if counter.get("fired") and not _has_fragment_reference(counter.get("why"), fragments):
            missing.append(str(counter.get("code")))
    return missing


def _cited_fragments(out: dict, fragments: list[str], urls: list[str]) -> list[dict]:
    """Persist bounded authoritative excerpts actually cited by verified decisions."""
    indices: set[int] = set()
    claims = [
        row for row in (out.get("features") or [])
        if isinstance(row, dict) and row.get("status") == "verified"
    ]
    transition = out.get("transition")
    if isinstance(transition, dict) and transition.get("status") == "verified":
        claims.append(transition)
    claims.extend(
        row for row in (out.get("counters") or [])
        if isinstance(row, dict) and row.get("code") in DROP_COUNTERS and row.get("fired")
    )
    for claim in claims:
        for raw_index in _FRAGMENT_REF.findall(str(claim.get("why") or "")):
            index = int(raw_index)
            if 1 <= index <= len(fragments):
                indices.add(index)
    return [
        {
            "fragment": index,
            "text": str(fragments[index - 1])[:300],
            "url": str(urls[index - 1]) if index - 1 < len(urls) else "",
        }
        for index in sorted(indices)
    ]


def _mark(row: dict, status: str, meta: dict | None = None) -> None:
    body = {"version": CHECKLIST_VERSION, "status": status}
    if meta:
        if meta.get("model_id"):
            body["model_id"] = meta.get("model_id")
        if meta.get("provider"):
            body["provider"] = meta.get("provider")
        body["cached"] = bool(meta.get("cached"))
    row["checklist"] = body


def _reader_failed(row: dict, error: str | None = None) -> dict:
    """Not read is not noise and not a zero. Like a card with no text, it leaves the seat."""
    _mark(row, "reader_failed")
    if error:
        row["checklist"]["error"] = error
    row["policy_reason"] = "reader_failed"
    row["confidence"] = None
    row["label"] = None
    row["predictors"] = []
    return {"keep": False, "unread": True, "card": row}


def _evidence_invalid(row: dict, missing: list[str], meta: dict | None = None) -> dict:
    """Fail closed when a claimed verification cannot be linked to the supplied evidence."""
    _mark(row, "evidence_invalid", meta)
    row["checklist"]["uncited_verified"] = missing
    row["policy_reason"] = "checklist_uncited_verified"
    row["confidence"] = None
    row["label"] = None
    row["reason_codes"] = []
    row["predictors"] = []
    return {"keep": False, "card": row}


def _checklist_invalid(row: dict, meta: dict | None = None) -> dict:
    """Malformed rows cannot be silently filtered or collapsed into a score."""
    _mark(row, "checklist_invalid", meta)
    row["policy_reason"] = "checklist_shape_invalid"
    row["confidence"] = None
    row["label"] = None
    row["reason_codes"] = []
    row["predictors"] = []
    return {"keep": False, "card": row}


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
    except Exception as exc:  # noqa: BLE001 — provider failures become explicit reader_failed cards
        return _reader_failed(row, type(exc).__name__)
    if not isinstance(read, dict) or not isinstance(read.get("output"), dict):
        return _reader_failed(row)
    meta = read.get("meta") if isinstance(read.get("meta"), dict) else {}
    try:
        validate_scoring_output(read["output"])
    except (TypeError, ValueError):
        return _checklist_invalid(row, meta)
    missing = _uncited_verified(read["output"], fragments)
    if missing:
        return _evidence_invalid(row, missing, meta)
    row["evidence_fragments"] = _cited_fragments(read["output"], fragments, _urls)
    try:
        fv = vector_for(row, read["output"])
        result = score(fv, rules)
    except Exception as exc:  # noqa: BLE001 — malformed reader behavior fails this card closed
        return _reader_failed(row, type(exc).__name__)
    row["label"] = result.label
    row["confidence"] = result.confidence
    row["reason_codes"] = list(result.reason_codes)
    row["predictors"] = list(result.predictors)
    _mark(row, "scored", read.get("meta") if isinstance(read.get("meta"), dict) else {})
    quote = _case_quote(
        read["output"],
        fragments,
        _urls,
    )
    if quote:
        row["case_quote"] = quote
    fired = [code for code in DROP_COUNTERS if fv.counters.get(code)]
    if fired:
        row["policy_reason"] = "checklist_counter"
        row["checklist_quote"] = fv.evidence.get(fired[0], "")
        return {"keep": False, "card": row}
    line = str((read.get("output") or {}).get("one_line_ru") or "").strip()
    if line.upper().replace(" ", "_").startswith("ДРУГОЙ_МЕХАНИЗМ"):
        row["policy_reason"] = "other_mechanism_after_read"
        row["checklist_quote"] = line
        return {"keep": False, "card": row}
    if result.confidence is None or result.confidence < _watchlist(rules):
        row["policy_reason"] = "checklist_below_watchlist"
        row["checklist_quote"] = fv.evidence.get(fv.primary_pattern, "")
        return {"keep": False, "card": row}
    if row.get("policy_reason") == "theme_quota":
        row["policy_reason"] = "evidence_gates_passed"
    return {"keep": True, "card": row}


def _peek_index(pool: list[dict], theme: str, used: set) -> int | None:
    hunts = 0
    for index, card in enumerate(pool):
        if card.get("theme") != theme or _identity(card) in used:
            continue
        hunts += 1
        if hunts > TEXT_HUNT:
            return None
        if _fragments(card, full=False)[0]:
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
        if _fragments(card, full=False)[0]:
            read += 1
        outcome = score_card(card, reader, rules)
        status = (outcome["card"].get("checklist") or {}).get("status")
        if status == "scored":
            scored += 1
        elif status in {"no_fragment", "reader_failed", "evidence_invalid", "checklist_invalid"}:
            unevaluated += 1
        return outcome

    def try_replace(theme: str, unread_card: dict | None = None) -> dict | None:
        nonlocal reads_used
        if reads_used >= backfill_cap:
            return None
        if theme is not None and theme in attempted:
            return None
        found = None
        hunts = 0
        while reads_used < backfill_cap and hunts < TEXT_HUNT:
            index = _peek_index(pool, theme, used)
            if index is None:
                break
            nxt = pool.pop(index)
            reads_used += 1
            hunts += 1
            try:
                outcome = judge(nxt)
            except Exception:
                pool.insert(index, nxt)
                raise
            status = (outcome["card"].get("checklist") or {}).get("status")
            if outcome["keep"] and status == "scored":
                if unread_card is not None:
                    failed = (unread_card.get("checklist") or {}).get("status") == "reader_failed"
                    unread_card["seat_replaced"] = True
                    unread_card["policy_reason"] = "reader_failed_replaced" if failed else "no_source_text_replaced"
                found = outcome["card"]
                break
            excluded.append(outcome["card"])
        if theme is not None:
            attempted.add(theme)
        return found

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
        asked = str(query or "").strip()
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
