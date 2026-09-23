from __future__ import annotations

from pathlib import Path

from ts.eval import (
    FAMILIES,
    binary_metrics,
    calibrate_tau,
    load_negatives,
    load_positives,
    read_organizer,
    split,
)

ROOT = Path(__file__).resolve().parents[2]


def test_positives_and_negatives_load_with_contamination_guard():
    pos = load_positives(ROOT / "data/dataset_patterns_100.json")
    neg = load_negatives(ROOT / "data/negatives_v1.json")
    assert len(pos) == 100 and all(p.label == "weak_signal" for p in pos)
    assert len(neg) >= 60 and {n.label for n in neg} <= {"mature", "noise", "watchlist"}
    # Item carries no rationale/score/trend fields at all
    assert not {"dataset_rationale", "dataset_score", "dataset_trend"} & set(vars(pos[0]))


def test_families_never_split():
    pos = load_positives(ROOT / "data/dataset_patterns_100.json")
    train, _hold = split(pos)
    tr = {p.id for p in train}
    for fam in FAMILIES:
        ids = {str(i) for i in fam}
        assert ids <= tr or not (ids & tr)
    assert 30 <= len(train) <= 70


def test_organizer_xlsx_adapter():
    xl = next((ROOT / "sources").glob("100_*.xlsx"))
    items = read_organizer(xl)
    assert len(items) == 100 and items[0].technology.startswith("Квантово")
    assert items[0].companies and items[0].domain


def test_metrics_and_calibration():
    m = binary_metrics([("weak_signal", "weak_signal"), ("mature", "weak_signal"), ("weak_signal", "noise"), ("noise", "noise")])
    assert m == {"n": 4, "tp": 1, "fp": 1, "fn": 1, "tn": 1, "accuracy": 0.5, "precision": 0.5, "recall": 0.5, "f1": 0.5}
    recs = [{"gold": "weak_signal", "confidence": 0.5, "counter_label": None},
            {"gold": "weak_signal", "confidence": 0.4, "counter_label": None},
            {"gold": "mature", "confidence": 0.2, "counter_label": None},
            {"gold": "mature", "confidence": None, "counter_label": "mature"}]
    cal = calibrate_tau(recs)
    assert 0.2 < cal["tau"] <= 0.4 and cal["train_metrics"]["f1"] == 1.0
