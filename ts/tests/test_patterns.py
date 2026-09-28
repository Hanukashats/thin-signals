"""Pattern texts v7 and the primary-assignment rule. No model calls."""
from __future__ import annotations

import json
from pathlib import Path

from ts.extract import REGISTRY_PATH, _system, to_feature_vector
from ts.scoring.assign import assign_primary
from ts.scoring.scorer import PATTERN_IDS, FeatureVector, load_rules, score

ROOT = Path(__file__).resolve().parents[2]
R = load_rules()


def _blank(primary: str, secondary: list[str] | None = None, features: dict | None = None) -> dict:
    status = {code: "unknown" for code in PATTERN_IDS}
    status.update(features or {})
    return {
        "primary_pattern": primary,
        "secondary_patterns": secondary or [],
        "features": [{"code": code, "status": status[code], "why": ""} for code in PATTERN_IDS],
        "counters": [{"code": f"M0{i}", "fired": False, "why": ""} for i in range(1, 7)],
        "transition": {"status": "unknown", "why": ""},
        "distinct_actors": 1,
        "distinct_events": 1,
    }


def test_registry_keeps_eighteen_and_splits_recognition_from_proof():
    registry = json.loads(REGISTRY_PATH.read_text())
    assert registry["version"] == "7.1"
    assert len(registry["patterns"]) == 18
    for row in registry["patterns"]:
        assert row["supported_when"] and row["verified_when"] and row["absent_when"]
        assert row["provenance"].startswith("Analyst induction")
        assert row["status"] == "design_hypothesis"
        assert row["id"] in PATTERN_IDS
    names = {row["id"]: row["name"] for row in registry["patterns"]}
    assert names["P01"] == R["patterns"]["P01"]
    assert names["P06"] == R["patterns"]["P06"]
    assert names["P07"] == R["patterns"]["P07"]
    assert R["weights"]["primary"] == 0.35
    assert R["thresholds"]["weak_signal"] == 0.60
    assert R["version"] == "rules-0.1"


def test_prompt_states_one_paper_and_forbids_p06_over_a_new_mechanism():
    text = _system(R, "description")
    assert "Одна первичная работа с датой" in text
    assert "Одно измеренное значение с единицами" in text
    assert "P06 не может быть главным, если узнан P01 или P02" in text
    assert "Первичная работа без продукта" in text
    assert "на любом языке источника" in text
    assert "Масштаб сдвига" in text
    assert "Слово edge" not in text
    assert "extract" not in text  # the prompt itself is not a version banner


def test_one_paper_is_not_labeled_as_a_new_use_of_a_mature_technology():
    for title in ("гафниевый сегнетоэлектрик", "натрий-ионный катод", "крекинг аммиака"):
        out = _blank("P06", features={"P01": "supported", "P06": "supported"})
        out["one_line_ru"] = title
        fv = to_feature_vector(out, "ledger")
        assert fv.primary_pattern == "P01"
        assert "P06" in fv.secondary_patterns


def test_chain_substitution_beats_a_funding_round_as_primary():
    primary, secondary = assign_primary(
        {"P07": "supported", "P04": "supported"}, "P04", [])
    assert primary == "P07"
    assert "P04" in secondary


def test_grant_does_not_outrank_the_mechanism():
    primary, _ = assign_primary({"P01": "supported", "P18": "verified"}, "P18", [])
    assert primary == "P01"


def test_unknown_money_does_not_penalize_a_science_sign():
    common = dict(evidence_events=2, independent_origins=2, transition="unknown", mode="ledger")
    with_gaps = score(FeatureVector(
        primary_pattern="P01",
        secondary_patterns=["P04", "P14", "P15"],
        features={"P01": "supported", "P04": "unknown", "P14": "unknown", "P15": "unknown"},
        **common), R)
    science_only = score(FeatureVector(
        primary_pattern="P01", features={"P01": "supported"}, **common), R)
    assert with_gaps.confidence == science_only.confidence
    assert with_gaps.confidence is not None
    assert "M05" not in with_gaps.reason_codes
    assert with_gaps.label != "mature"


def test_mass_deployment_still_blocks_even_when_the_mechanism_is_new():
    result = score(FeatureVector(
        primary_pattern="P01", features={"P01": "supported"}, counters={"M03": True}, mode="ledger"), R)
    assert result.label == "mature" and result.confidence is None
    assert "M03" in result.reason_codes


def test_dataset_rows_still_form_a_feature_vector():
    rows = json.loads((ROOT / "data" / "dataset_patterns_100.json").read_text())
    assert len(rows) == 100
    for row in rows:
        fv = to_feature_vector(
            _blank(row["primary_pattern"], row.get("secondary_patterns") or []),
            "description", row.get("companies"))
        assert fv.primary_pattern == row["primary_pattern"]
        assert fv.primary_pattern in PATTERN_IDS
