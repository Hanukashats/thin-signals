"""A mission sentence is not a search string. It runs the standing theme queries.

Each theme keeps the ordinary word gate and the ordinary order. The official list
takes one card from each theme before a second card from any theme. A read scale
of 2 or 1 moves ahead of unread cards. Unread cards are not labeled fundamental.
Score weights are not touched.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from ts.harness import TOP_N, _tokens
from ts.scoring.order import _published_rank, scope_rank

PLAN_PATH = Path(__file__).resolve().parents[1] / "data" / "theme_plan.yaml"


def load_theme_plan(path: Path = PLAN_PATH) -> dict:
    plan = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    plan["frame"] = [str(word).lower() for word in plan.get("frame") or []]
    plan["themes"] = list(plan.get("themes") or [])
    plan["version"] = str(plan.get("version") or "themes-0")
    return plan


def is_wide(query: str, plan: dict) -> bool:
    """True when the sentence names the assignment and almost no object."""
    text = (query or "").strip().lower()
    if not text:
        return False
    if text in {str(theme.get("query") or "").strip().lower() for theme in plan["themes"]}:
        return False
    tokens = _tokens(text)
    if len(tokens) < 4:
        return False
    frame = set(plan["frame"])
    distinctive = [token for token in tokens if token not in frame and not token.isdigit()]
    return len(distinctive) < 2


def _identity(card: dict) -> tuple:
    urls = tuple(sorted(source.get("url") or "" for source in card.get("sources") or [] if source.get("url")))
    if urls:
        return urls
    return ("title", str(card.get("technology") or "").lower())


def _newer_first(cards: list[dict]) -> list[dict]:
    """Among cards that hold the query words, the newer date goes first.

    A card without a date stays in the queue, after the dated ones. Cards without
    the query words keep their own order behind them.
    """
    def key(card: dict) -> tuple:
        if int(card.get("subject_hits") or 0) > 0:
            return (0, -_published_rank(card))
        return (1, 0)
    return sorted(cards, key=key)


def merge_theme_reports(parts: list[tuple[dict, list[dict]]], *, limit: int = TOP_N) -> dict:
    """parts are (theme, already admitted cards in that theme's own order)."""
    queues: list[list[dict]] = []
    notes = []
    for theme, cards in parts:
        tagged = []
        for card in _newer_first(cards):
            tagged.append({
                **card,
                "theme": theme.get("id"),
                "theme_title": theme.get("title"),
                "theme_query": theme.get("query"),
            })
        queues.append(tagged)
        notes.append({
            "id": theme.get("id"),
            "title": theme.get("title"),
            "query": theme.get("query"),
            "admitted": len(tagged),
            "taken": 0,
        })
    picked: list[dict] = []
    overflow: list[dict] = []
    seen: set[tuple] = set()
    while len(picked) < limit and any(queues):
        for index, queue in enumerate(queues):
            if len(picked) >= limit:
                break
            while queue:
                card = queue.pop(0)
                ident = _identity(card)
                if ident in seen:
                    continue
                seen.add(ident)
                picked.append(card)
                notes[index]["taken"] += 1
                break
    for queue in queues:
        for card in queue:
            ident = _identity(card)
            if ident in seen:
                continue
            seen.add(ident)
            overflow.append({**card, "policy_reason": "theme_quota"})
    picked = sorted(picked, key=scope_rank, reverse=True)
    return {"top": picked, "overflow": overflow, "themes": notes}
