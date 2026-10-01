"""Search behavior for the sealed old-technology archive."""
from __future__ import annotations

import json
from pathlib import Path


def _cards() -> list[dict]:
    root = Path(__file__).resolve().parents[2]
    return json.loads((root / "data/old_tech/snapshot_2026-09-29.json").read_text(encoding="utf-8"))["cards"]


def test_empty_query_preserves_research_ranking():
    from ts.old_tech import search_old_tech_cards

    rows = search_old_tech_cards(_cards())
    assert [row["rank"] for row in rows] == list(range(1, 16))


def test_search_finds_name_barrier_buyer_and_application_without_fabrication():
    from ts.old_tech import search_old_tech_cards

    assert search_old_tech_cards(_cards(), "Кнудсена")[0]["id"] == "T01"
    assert search_old_tech_cards(_cards(), "теплопотери")[0]["id"] == "T01"
    assert search_old_tech_cards(_cards(), "газоанализаторов")[0]["id"] == "T01"
    assert search_old_tech_cards(_cards(), "анализатора утечек")[0]["id"] == "T01"
    assert search_old_tech_cards(_cards(), "несуществующаяквазитехнология") == []


def test_name_match_outweighs_a_low_weight_market_mention():
    from ts.old_tech import search_old_tech_cards

    cards = [
        {"id": "a", "rank": 2, "name": "Квантовый насос", "market_findings": ""},
        {"id": "b", "rank": 1, "name": "Другая вещь", "market_findings": "квантовый рынок"},
    ]
    rows = search_old_tech_cards(cards, "квантовый")
    assert [row["id"] for row in rows] == ["a", "b"]
    assert rows[0]["matched_fields"] == ["name"]
