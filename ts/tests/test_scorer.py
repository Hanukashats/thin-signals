"""Scorer invariants + METHODOLOGY §8 error cases expressed as feature statuses."""
from __future__ import annotations

from itertools import product

from ts.scoring.scorer import FeatureVector, independence, load_rules, score, thresholds_for

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


def test_unnamed_search_does_not_invent_an_early_money_sign():
    r = score(FeatureVector(primary_pattern="P04", named_primary=False, evidence_events=1,
                            independent_origins=1, mode="ledger"), R)
    assert "P04_unknown" not in r.reason_codes
    assert all(p["code"] != "P04" for p in r.predictors)


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


def test_rules_0_2_pattern_score_is_invariant_to_semantic_primary_choice():
    rules = load_rules("rules-0.2")
    features = {"P01": "supported", "P02": "verified", "P04": "supported"}
    confidences = {
        score(fv(
            primary_pattern=primary,
            secondary_patterns=[code for code in features if code != primary],
            features=features,
            evidence_events=0,
            independent_origins=0,
            transition="unknown",
        ), rules).confidence
        for primary in features
    }

    assert confidences == {0.5}


def test_rules_0_2_positive_evidence_is_monotonic_when_primary_changes():
    rules = load_rules("rules-0.2")
    before = score(fv(
        primary_pattern="P02",
        secondary_patterns=["P04"],
        features={"P02": "verified", "P04": "supported"},
        evidence_events=0,
        independent_origins=0,
        transition="unknown",
    ), rules)
    after = score(fv(
        primary_pattern="P01",
        secondary_patterns=["P02", "P04"],
        features={"P01": "supported", "P02": "verified", "P04": "supported"},
        evidence_events=0,
        independent_origins=0,
        transition="unknown",
    ), rules)

    assert before.confidence == 0.425
    assert after.confidence == 0.5
    assert after.confidence >= before.confidence


def test_thresholds_for_is_the_single_mode_aware_contract():
    rules = load_rules("rules-0.2")

    assert thresholds_for(rules) == {"weak_signal": 0.60, "watchlist": 0.35}
    assert thresholds_for(rules, "description") == {"weak_signal": 0.30, "watchlist": 0.18}


def test_rules_0_2_is_exhaustively_primary_invariant_and_status_monotonic():
    rules = load_rules("rules-0.2")
    codes = ("P01", "P02", "P03")
    statuses = ("absent", "unknown", "supported", "verified")
    strength = {"absent": 0, "unknown": 0, "supported": 1, "verified": 2}

    def confidence(features: dict[str, str], primary: str) -> float:
        return score(FeatureVector(
            primary_pattern=primary,
            secondary_patterns=[code for code in codes if code != primary],
            features=features,
            evidence_events=0,
            independent_origins=0,
            transition="unknown",
        ), rules).confidence or 0.0

    for values in product(statuses, repeat=len(codes)):
        features = dict(zip(codes, values, strict=True))
        primary_scores = {confidence(features, primary) for primary in codes}
        assert len(primary_scores) == 1
        baseline = primary_scores.pop()
        for code in codes:
            for upgraded in statuses:
                if strength[upgraded] < strength[features[code]]:
                    continue
                changed = {**features, code: upgraded}
                assert confidence(changed, code) >= baseline
