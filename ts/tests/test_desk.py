"""Viewer document, admin gate, and draft notes. No scoring."""
from __future__ import annotations

from ts.access import can_admin, hash_password, role_for, verify_password
from ts.desk import compose_query, document, field_help, load_draft, reasoning, save_draft, score_story

PAYLOAD = {
    "run_status": "succeeded",
    "signal_label": "noise",
    "policy_action": "WATCHLIST",
    "policy_reason": "no_verified_change",
    "reason_codes": ["M04"],
    "predictors": [],
    "sources": [],
    "exclusion_registry": [],
    "shortfall": 15,
    "counters": {"sources": 1, "admitted": 0, "excluded": 1, "confident": 0},
}


def test_document_keeps_run_status_and_label_apart():
    text = document(PAYLOAD, "фотонный процессор", "только пилоты", "2026-01-01", "2026-09-01")
    assert "Статус прогона: succeeded" in text
    assert "Метка сигнала: шум" in text
    assert "Направление: фотонный процессор" in text
    assert "Период: 2026-01-01 — 2026-09-01" in text
    chain = reasoning(PAYLOAD)
    assert chain["conclusion"] == "шум"
    assert any("no_verified_change" in step for step in chain["steps"])
    assert "succeeded" not in chain["conclusion"]


def test_every_field_has_what_why_and_how():
    for field_id in ("direction", "correction", "period", "run_status", "signal_label", "prompt_draft", "logic_note"):
        help_text = field_help(field_id)
        assert "Зачем:" in help_text
        assert "Как менять:" in help_text


def test_query_needs_a_direction_and_stays_short():
    assert "период" in compose_query("клетка", "", "2026-01-01", "")
    try:
        compose_query("x", "", "", "")
        raise AssertionError("one letter is not a direction")
    except ValueError:
        pass
    try:
        compose_query("а" * 401, "", "", "")
        raise AssertionError("overlong query must fail")
    except ValueError:
        pass


def test_viewer_cannot_open_admin_and_password_roundtrip(tmp_path):
    stored = hash_password("desk-test-secret")
    assert verify_password("desk-test-secret", stored)
    assert not verify_password("other", stored)
    accounts = {
        "user1": {"role": "viewer", "password_hash": stored},
        "admin": {"role": "admin", "password_hash": stored},
    }
    assert role_for(accounts, "user1", "desk-test-secret") == "viewer"
    assert role_for(accounts, "admin", "wrong") is None
    assert can_admin("viewer") is False
    assert can_admin("admin") is True
    path = tmp_path / "draft.yaml"
    save_draft(path, "новый чек-лист", "порог не трогать с экрана")
    loaded = load_draft(path)
    assert loaded["prompt_draft"] == "новый чек-лист"
    assert "applied_to_scorer: false" in path.read_text(encoding="utf-8")


def test_score_story_is_not_a_startup_probability():
    story = score_story({
        "confidence": 0.42,
        "predictors": [
            {"code": "P01", "contribution": 0.35, "weight": 0.35, "value": "verified"},
            {"code": "IND", "contribution": 0.07, "weight": 0.2, "value": 0.35},
        ],
        "top": [{"technology": "фотон", "label": "weak_signal", "confidence": 0.42}],
    })
    assert story["lines"][1] == "Итог суммы: 0.42."
    assert story["lines"][2].startswith("P01:")
    assert story["lines"][3].startswith("IND:")
    assert "стартап" in story["disclaimer"]
    assert "акци" in story["disclaimer"]
    assert story["top"] == ["фотон: слабый сигнал, уверенность 0.42"]
    stopped = score_story({"confidence": None, "predictors": [{"code": "M04", "contribution": -0.3, "weight": -0.3, "value": 1}]})
    assert stopped["lines"][0].startswith("Контр-признак")
    text = document(PAYLOAD, "клетка", "", "", "")
    assert "не вероятность" in text
    assert "Статус прогона: succeeded" in text
    assert "Метка сигнала: шум" in text


def test_empty_chain_says_so():
    chain = reasoning({"signal_label": "weak_signal"})
    assert chain["steps"] == ["Цепочка пуста: прогон не вернул причины."]
    assert chain["conclusion"] == "слабый сигнал"
