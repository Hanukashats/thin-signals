"""Nearest window stays outside the official TOP-15."""
from __future__ import annotations

from ts.desk import document
from ts.nearest import build_nearest, nearest_lines


def _payload():
    return {
        "query": "перовскитный датчик",
        "signal_label": "noise",
        "confidence": None,
        "policy_action": "REFRAME_CHILD",
        "policy_reason": "mature_parent",
        "reason_codes": ["M04"],
        "top": [],
        "shortfall": 15,
        "sources": [
            {
                "name": "Индикатор без даты",
                "url": "https://blog.example/a",
                "date": None,
                "date_unknown_reason": "источник не указал дату",
                "trust": "indicator",
            },
            {
                "name": "Статья с датой",
                "url": "https://arxiv.org/abs/1",
                "date": "2026-02-02",
                "trust": "primary",
            },
            {
                "name": "Обзор",
                "url": "https://news.example/b",
                "date": "2026-03-03",
                "trust": "professional",
            },
        ],
        "exclusion_registry": [{
            "technology": "перовскитный датчик",
            "label": "noise",
            "policy_action": "REFRAME_CHILD",
            "policy_reason": "mature_parent",
        }],
    }


def test_nearest_ranks_checks_and_does_not_fill_top():
    payload = _payload()
    payload["exclusion_registry"] = []
    board = build_nearest(payload)
    assert board["official_count"] == 0
    assert board["shortfall"] == 15
    assert board["shown"] == 3
    assert board["rows"][0]["name"] == "Статья с датой"
    assert board["rows"][0]["rank"] == 1
    assert board["rows"][0]["approach_percent"] == 100
    assert board["rows"][1]["name"] == "Обзор"
    assert board["rows"][2]["approach_percent"] < 100
    assert "Стоппер" in board["stuck"]
    assert "M04" in board["why"]
    assert "не официальный ТОП-15" in board["note"]
    assert board["rows"][0]["gaps"] == []
    assert any("дату" in gap or "доверие" in gap for gap in board["rows"][2]["gaps"])


def test_chain_shift_sorts_above_a_complete_lab_note_and_stays_out_of_the_list():
    payload = _payload()
    payload["exclusion_registry"] = [
        {
            "technology": "датчик влажности",
            "label": "noise",
            "policy_action": "WATCHLIST",
            "policy_reason": "one_origin_result",
            "chain_link": {"score": 0, "sentence": "Связь не видна. Это не отказ."},
            "sources": [{"url": "https://arxiv.org/abs/1", "trust": "primary"}],
        },
        {
            "technology": "прямая продажа ячеек без посредника",
            "label": "noise",
            "policy_action": "WATCHLIST",
            "policy_reason": "one_origin_result",
            "chain_link": {
                "score": 1,
                "sentence": "В тексте видно касание: финансовый рынок, цепочка поставок или производство.",
            },
            "sources": [{"url": "https://www.cnesa.org/a", "trust": "primary"}],
        },
    ]
    board = build_nearest(payload)
    assert board["official_count"] == 0
    assert [row["name"] for row in board["rows"]] == [
        "прямая продажа ячеек без посредника",
        "датчик влажности",
    ]
    assert "цепочка поставок" in board["rows"][0]["gaps"][0]


def test_nearest_does_not_invent_fifteen_rows():
    payload = _payload()
    payload["sources"] = payload["sources"][:1]
    board = build_nearest(payload)
    assert board["shown"] == 1
    assert len(board["rows"]) == 1


def test_unknown_reason_does_not_invent_a_ladder_percent():
    payload = _payload()
    payload["confidence"] = 0.2
    payload["reason_codes"] = []
    payload["policy_reason"] = "something_new"
    payload["sources"] = []
    payload["exclusion_registry"][0]["policy_reason"] = "something_new"
    board = nearest_lines(payload)
    assert board["ladder_percent"] is None
    assert board["shown"] == 1
    assert "процент проверок не выведен" in board["lines"][0]
    text = document(payload, "датчик", "", "", "")
    assert "## Список до ТОП-15" in text
    assert "В список никто не прошёл" in text
    assert "## Ближайшие к допуску" in text
    assert "не официальный ТОП-15" in text


def test_screen_keeps_nearest_on_its_own_tab():
    from pathlib import Path
    text = Path("ui/app.py").read_text(encoding="utf-8")
    assert 'st.tabs(["Официальный ТОП-15", "Ближайшие к допуску"])' in text


def test_admitted_card_stays_a_hundred_percent_of_stages():
    payload = _payload()
    payload["confidence"] = 0.4
    payload["reason_codes"] = []
    payload["policy_reason"] = "evidence_gates_passed"
    payload["signal_label"] = "weak_signal"
    payload["top"] = [{"technology": "датчик", "label": "weak_signal", "confidence": 0.4}]
    payload["shortfall"] = 14
    board = build_nearest(payload)
    assert board["official_count"] == 1
    assert board["ladder_percent"] == 100
    assert "контр-признак" not in board["why"]
