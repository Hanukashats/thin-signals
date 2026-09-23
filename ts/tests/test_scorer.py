"""Scorer invariants + METHODOLOGY §8 error cases expressed as feature statuses."""
from __future__ import annotations

from ts.scoring.scorer import FeatureVector, independence, load_rules, score

R = load_rules()


def fv(**kw) -> FeatureVector:
    base = dict(primary_pattern="P04", secondary_patterns=["P02", "P10"],
                features={"P04": "verified", "P02": "verified", "P10": "supported"},
                counters={}, evidence_events=4, independent_origins=3, transition="verified", mode="ledger")
    base.update(kw)
    return FeatureVector(**base)


def test_full_evidence_is_weak_signal_with_visible_predictors():
    r = score(fv(), R)
    assert r.label == "weak_signal" and r.gate == "rank_eligible"
    # 0.35 + 0.15 + 0.075 + 0.2*ind(0.75*1) + 0.15 = 0.875
    assert r.confidence == 0.875
    codes = [p["code"] for p in r.predictors]
    assert codes == ["P04", "P02", "P10", "IND", "TR"]
    assert all("contribution" in p and "weight" in p for p in r.predictors)


def test_counter_feature_short_circuits_to_mature_or_noise():
    assert score(fv(counters={"M02": True}), R).label == "mature"
    assert score(fv(counters={"M04": True}), R).label == "noise"
    r = score(fv(counters={"M01": True, "M05": True}), R)
    assert r.label == "mature" and r.confidence is None and r.gate == "maturity"
    assert set(r.reason_codes) == {"M01", "M05"}


def test_secondary_contributions_are_capped():
    r = score(fv(secondary_patterns=["P01", "P02", "P03", "P05"],
                 features={"P04": "verified", "P01": "verified", "P02": "verified", "P03": "verified", "P05": "verified"}), R)
    sec = sum(p["contribution"] for p in r.predictors if p["kind"] == "secondary")
    assert abs(sec - R["weights"]["secondary_cap"]) < 1e-9


def test_round_is_not_valuation_absent_primary_drops_confidence():
    # №1: "раунд" was actually a valuation → P04 absent
    r = score(fv(features={"P04": "absent", "P02": "verified", "P10": "supported"}), R)
    assert "P04_absent" in r.reason_codes and r.confidence < score(fv(), R).confidence


def test_singleton_event_flagged():
    r = score(fv(evidence_events=1, independent_origins=1), R)
    assert "singleton" in r.reason_codes and independence(1, 1) == 0.0


def test_description_mode_caps_verified_to_supported():
    r = score(fv(mode="description"), R)
    assert all(p["value"] != "verified" for p in r.predictors if p["kind"] in ("primary", "secondary"))
    # 0.175 + 0.075 + 0.075 + 0.15 + 0.075 = 0.55 → weak_signal under description thresholds
    assert r.confidence == 0.55 and r.label == "weak_signal"


def test_thresholds_produce_watchlist_and_noise():
    # 0.175 + 0.2*ind(3,3)=0.1 + 0.075 = 0.35 → watchlist boundary
    r = score(fv(features={"P04": "supported"}, secondary_patterns=[], evidence_events=3, independent_origins=3,
                 transition="supported"), R)
    assert r.label == "watchlist" and "below_tau" in r.reason_codes
    r = score(fv(features={}, secondary_patterns=[], evidence_events=0, independent_origins=0, transition="unknown"), R)
    assert r.label == "noise" and r.confidence == 0.0
