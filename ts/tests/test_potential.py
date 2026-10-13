"""Evidence-honest ranking for the review queue outside the admitted list."""
from __future__ import annotations


def _card(
    name: str,
    confidence: float,
    predictors: list[dict],
    *,
    reason: str = "checklist_below_watchlist",
    status: str = "scored",
) -> dict:
    from ts.checklist import CHECKLIST_VERSION
    return {
        "technology": name,
        "confidence": confidence,
        "policy_reason": reason,
        "checklist": {"status": status, "version": CHECKLIST_VERSION},
        "predictors": predictors,
    }


def _p(code: str, value: str) -> dict:
    return {"code": code, "value": value, "kind": "secondary", "contribution": 0.0}


def test_missing_axes_stay_unknown_and_one_verified_axis_is_coverage_discounted():
    from ts.potential import potential_metrics

    metrics = potential_metrics(_card("механизм", 0.1, [_p("P01", "verified")]))

    assert metrics["technical"] == 70.0
    assert metrics["demand"] is None
    assert metrics["development"] is None
    assert metrics["evaluated_axes"] == 1
    assert metrics["potential_index"] == 46.7
    assert metrics["gate_proximity"] == 28.6


def test_two_signals_in_one_axis_do_not_masquerade_as_three_evaluated_axes():
    from ts.potential import potential_metrics

    metrics = potential_metrics(_card(
        "двойной технический признак",
        0.1,
        [_p("P01", "verified"), _p("P02", "verified")],
    ))

    assert metrics["technical"] == 100.0
    assert metrics["evaluated_axes"] == 1
    assert metrics["potential_index"] == 66.7


def test_unknown_is_zero_but_an_axis_absent_from_predictors_is_not_evaluated():
    from ts.potential import potential_metrics

    metrics = potential_metrics(_card(
        "разобранный ноль",
        0.1,
        [_p("P01", "unknown"), _p("P05", "absent")],
    ))

    assert metrics["technical"] == 0.0
    assert metrics["demand"] == 0.0
    assert metrics["development"] is None
    assert metrics["potential_index"] == 0.0


def test_already_scored_weak_signal_does_not_enter_the_review_queue():
    from ts.potential import rank_potential_cards

    card = _card(
        "уже слабый сигнал",
        0.65,
        [_p("P01", "verified"), _p("P02", "verified")],
    )

    rows = rank_potential_cards({"exclusion_registry": [card]})

    assert rows == []


def test_close_card_is_selected_without_inflating_unevaluated_potential():
    from ts.potential import rank_potential_cards

    card = _card("рядом", 0.325, [_p("P01", "supported")])

    rows = rank_potential_cards({"exclusion_registry": [card]})

    assert rows[0]["selection_reasons"] == ["near_gate"]
    assert rows[0]["potential"]["potential_index"] == 23.3
    assert rows[0]["review_priority"] == 92.9
    assert rows[0]["gate_gap"] == 0.025


def test_hard_counters_unread_invalid_and_off_topic_cards_are_excluded():
    from ts.potential import rank_potential_cards

    registry = [
        _card("контр", 0.3, [_p("P01", "verified"), {"code": "M01", "value": 1}]),
        _card("не прочитано", 0.3, [_p("P01", "verified")], status="reader_failed"),
        _card("невалидно", 0.3, [_p("P01", "verified")], status="evidence_invalid"),
        _card("другой механизм", 0.3, [_p("P01", "verified")], reason="other_mechanism_after_read"),
        _card("проходит", 0.3, [_p("P01", "supported")]),
    ]

    rows = rank_potential_cards({"exclusion_registry": registry})

    assert [row["technology"] for row in rows] == ["проходит"]


def test_ranking_is_stable_and_capped_after_priority_tie_breaks():
    from ts.potential import rank_potential_cards

    registry = [
        _card("бета", 0.3, [_p("P01", "supported")]),
        _card("альфа", 0.3, [_p("P01", "supported")]),
        _card("лидер", 0.34, [_p("P01", "supported")]),
    ]

    rows = rank_potential_cards({"exclusion_registry": registry}, cap=2)

    assert [row["technology"] for row in rows] == ["лидер", "альфа"]
    assert rank_potential_cards({}, cap=2) == []
    assert rank_potential_cards({"exclusion_registry": None}, cap=2) == []


def test_duplicate_predictor_code_cannot_inflate_an_axis():
    from ts.potential import potential_metrics

    metrics = potential_metrics(_card(
        "дубликат",
        0.1,
        [_p("P01", "verified"), _p("P01", "verified")],
    ))

    assert metrics["technical"] == 70.0
    assert metrics["potential_index"] == 46.7


def test_real_scored_watchlist_can_enter_high_potential_without_becoming_a_signal(tmp_path):
    from ts.checklist import score_card
    from ts.potential import rank_potential_cards
    from ts.scoring.scorer import load_rules
    from ts.tests.test_checklist import _card as source_card
    from ts.tests.test_checklist import _out, _read

    output = _out(verified={"P01", "P02"}, transition="unknown")
    output["secondary_patterns"] = ["P02"]
    judged = score_card(
        source_card(snapshot_root=tmp_path), lambda _: _read(output), load_rules(),
        snapshot_root=tmp_path,
    )
    card = judged["card"]
    assert card["confidence"] == 0.5
    assert card["label"] == "watchlist"

    rows = rank_potential_cards({"top": [card], "exclusion_registry": [card]})

    assert len(rows) == 1
    assert rows[0]["selection_reasons"] == ["high_potential"]
    assert rows[0]["potential"]["potential_index"] == 66.7
    assert rows[0]["gate_target"] == 0.6
    assert rows[0]["gate_gap"] == 0.1
    assert card["label"] == "watchlist"


def test_off_topic_below_gate_result_never_enters_potential():
    from ts.checklist import score_card
    from ts.potential import rank_potential_cards
    from ts.scoring.scorer import load_rules
    from ts.tests.test_checklist import _card as source_card
    from ts.tests.test_checklist import _out, _read

    output = _out(transition="unknown")
    for feature in output["features"]:
        feature["status"] = "supported" if feature["code"] in {"P01", "P02", "P03"} else "absent"
    output["one_line_ru"] = "ДРУГОЙ_МЕХАНИЗМ: источник о другом предмете"
    judged = score_card(source_card(), lambda _: _read(output), load_rules())

    assert judged["card"]["confidence"] == 0.325
    assert judged["card"]["policy_reason"] == "other_mechanism_after_read"
    assert rank_potential_cards({"exclusion_registry": [judged["card"]]}) == []


def test_legacy_exclusion_cannot_silently_become_current_potential():
    from ts.checklist import CHECKLIST_VERSION
    from ts.desk import potential_board, run_integrity

    card = _card("старое наблюдение", 0.325, [_p("P01", "supported")])
    card["checklist"]["version"] = "checklist-v11"
    payload = {"top": [], "exclusion_registry": [card], "potential": [card]}

    board = potential_board(payload)
    assert board["cards"] == []
    assert "новый прогон" in board["note"]
    warnings = " ".join(run_integrity(payload, expected_checklist=CHECKLIST_VERSION)["warnings"])
    assert "checklist-v11" in warnings


def test_potential_uses_injected_rules_thresholds_instead_of_module_constants():
    from copy import deepcopy

    from ts.potential import potential_metrics, rank_potential_cards
    from ts.scoring.scorer import load_rules

    rules = deepcopy(load_rules())
    rules["thresholds"] = {"weak_signal": 0.70, "watchlist": 0.40}
    card = _card("динамический порог", 0.39, [_p("P01", "supported")])

    rows = rank_potential_cards({"exclusion_registry": [card]}, rules=rules)

    assert len(rows) == 1
    assert rows[0]["selection_reasons"] == ["near_gate"]
    assert rows[0]["gate_target"] == 0.4
    assert potential_metrics(card, rules=rules)["gate_target"] == 0.4
