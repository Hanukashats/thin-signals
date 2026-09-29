"""A mission sentence is not a search string. Mined phrases take turns in the list.

Each phrase keeps the ordinary order. The official list takes one card from each
phrase before a second card from any phrase. Score weights are not touched.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from ts.harness import TOP_N
from ts.scoring.order import scope_rank

PLAN_PATH = Path(__file__).resolve().parents[1] / "data" / "theme_plan.yaml"


def load_theme_plan(path: Path = PLAN_PATH) -> dict:
    plan = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    plan["frame"] = [str(word).lower() for word in plan.get("frame") or []]
    plan["themes"] = list(plan.get("themes") or [])
    plan["version"] = str(plan.get("version") or "themes-0")
    return plan


def is_wide(query: str, plan: dict) -> bool:
    """True when the sentence names a field rather than one object."""
    from ts.mine import direction

    return direction(query, plan.get("frame") or [])["mode"] == "wide"


def _identity(card: dict) -> tuple:
    urls = tuple(sorted(source.get("url") or "" for source in card.get("sources") or [] if source.get("url")))
    if urls:
        return urls
    return ("title", str(card.get("technology") or "").lower())


def merge_theme_reports(parts: list[tuple[dict, list[dict]]], *, limit: int = TOP_N) -> dict:
    """parts are (theme, already admitted cards in that theme's own order)."""
    queues: list[list[dict]] = []
    notes = []
    for theme, cards in parts:
        tagged = []
        for card in cards:
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
