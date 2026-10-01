"""Deterministic full-text lookup over the sealed 2026-09-29 old-tech archive.

This is an archive search, not fresh web discovery.  It ranks only text that is
already inside the integrity-checked snapshot and never changes research scores.
"""
from __future__ import annotations

import re

FIELD_WEIGHTS = {
    "name": 6,
    "family": 5,
    "first_product": 4,
    "buyers": 4,
    "barrier_then": 3,
    "change_now": 3,
    "history": 2,
    "evidence": 2,
    "risk": 1,
    "test": 1,
    "market_findings": 1,
}


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[\w]+", str(text or "").casefold()) if len(token) >= 2]


def _excerpt(text: str, tokens: list[str], limit: int = 220) -> str:
    compact = " ".join(str(text or "").split())
    if not compact:
        return ""
    lower = compact.casefold()
    offsets = [lower.find(token) for token in tokens if lower.find(token) >= 0]
    start = max(0, min(offsets) - 55) if offsets else 0
    end = min(len(compact), start + limit)
    prefix = "…" if start else ""
    suffix = "…" if end < len(compact) else ""
    return f"{prefix}{compact[start:end].strip()}{suffix}"


def search_old_tech_cards(cards: list[dict], query: str = "", *, limit: int = 15) -> list[dict]:
    """Return stable archive matches with transparent field weights and excerpts."""
    words = _tokens(query)
    if not words:
        return sorted(
            (dict(card) for card in cards if isinstance(card, dict)),
            key=lambda card: card.get("rank") if isinstance(card.get("rank"), int) else 10**9,
        )[:max(0, int(limit))]

    matches = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        score = 0
        matched = []
        excerpts = []
        for field, weight in FIELD_WEIGHTS.items():
            value = str(card.get(field) or "")
            normalized = value.casefold()
            hits = [word for word in words if word in normalized]
            if not hits:
                continue
            score += weight * len(set(hits))
            matched.append(field)
            excerpt = _excerpt(value, hits)
            if excerpt:
                excerpts.append({"field": field, "text": excerpt})
        if not score:
            continue
        row = dict(card)
        row["search_score"] = score
        row["matched_fields"] = matched
        row["match_excerpts"] = excerpts[:3]
        matches.append(row)
    matches.sort(key=lambda card: (
        -int(card["search_score"]),
        card.get("rank") if isinstance(card.get("rank"), int) else 10**9,
        str(card.get("name") or ""),
    ))
    return matches[:max(0, int(limit))]
