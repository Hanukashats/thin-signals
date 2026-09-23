"""Gate-order parity with reference/policy.py + F03 fixes + METHODOLOGY §8 scenarios."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ts.scoring.policy import normalized_growth, route, validate_contract

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "reference"))
import policy as reference


def base(**changes):
    s = dict(
        as_of="2026-09-17", novelty="new", maturity="emerging",
        critical_claims=["verified", "supported"], fatal_finding="none",
        evidence_events=3, independent_origins=2, countersearch_done=True,
        source_availability_valid=True, budget_exhausted=False,
        branches_complete=True, transition_verified=True,
    )
    s.update(changes)
    return s


def window(start, end, n, N=100, days=90, **changes):
    s = dict(start=start, end=end, n=n, N=N, days=days, protocol="fixed-v1",
             coverage="complete_for_query", complete_period=True)
    s.update(changes)
    return s


# --- parity with v6.1 reference on all its 15 scenarios -----------------------------------
PARITY_CASES = [
    base(fatal_finding="verified", budget_exhausted=True),
    base(critical_claims=[]),
    base(critical_claims=["unknown"], budget_exhausted=True),
    base(fatal_finding="weak"),
    base(source_availability_valid=False),
    base(maturity="established"),
    base(novelty="unclear"),
    base(countersearch_done=False),
    base(evidence_events=1, independent_origins=1),
    base(evidence_events=2, independent_origins=2),
    base(branches_complete=False),
    base(transition_verified=False),
    base(),
    base(critical_claims=["refuted"]),
    base(budget_exhausted=True, countersearch_done=False),
]


@pytest.mark.parametrize("state", PARITY_CASES)
def test_action_parity_with_reference(state):
    assert route(state)["action"] == reference.route(state)["action"]


# --- F03: types before membership --------------------------------------------------------
@pytest.mark.parametrize("bad", [
    base(novelty=[]),
    base(critical_claims=[{}]),
    base(maturity=None),
    base(fatal_finding=1),
    base(as_of=20260917),
    base(evidence_events=True),
    base(countersearch_done=1),
    "not a mapping",
    None,
])
def test_invalid_types_are_controlled_hold(bad):
    r = route(bad)
    assert r["action"] == "HOLD"
    assert r["reason"] in {"invalid_contract", "invalid_as_of"}


def test_reference_raises_on_same_input_documenting_the_gap():
    with pytest.raises(TypeError):
        reference.route(base(novelty=[]))


def test_origins_cannot_exceed_events():
    r = route(base(evidence_events=3, independent_origins=100))
    assert r["action"] == "HOLD" and "ledger" in r["trigger"]
    assert reference.route(base(evidence_events=3, independent_origins=100))["action"] == "RANK_ELIGIBLE"


# --- METHODOLOGY §3 / §8 scenarios -------------------------------------------------------
def test_deadline_cannot_turn_unknown_into_pass():
    assert route(base(critical_claims=["verified", "unknown"], budget_exhausted=True))["action"] == "HOLD"


def test_verified_refutation_beats_budget():
    assert route(base(fatal_finding="verified", budget_exhausted=True))["action"] == "REJECT_OR_REFRAME"


def test_row85_many_articles_one_event_is_singleton():
    # 10 media reprints deduplicated to one canonical event from one origin group
    assert route(base(evidence_events=1, independent_origins=1))["action"] == "WATCHLIST_SINGLETON"


def test_mature_parent_reframes_not_rejects():
    r = route(base(maturity="established"))
    assert r["action"] == "REFRAME_CHILD" and r["gate"] == "maturity"


def test_every_result_names_gate():
    for s in PARITY_CASES:
        assert "gate" in route(s)


# --- growth --------------------------------------------------------------------------------
def test_growth_requires_90_day_windows_in_product_config():
    prev = window("2026-03-19", "2026-06-16", 4)
    rec = window("2026-06-17", "2026-09-14", 8)
    g = normalized_growth(rec, prev)
    assert g is not None and g > 0
    assert normalized_growth(window("2026-08-16", "2026-09-14", 8, days=30),
                             window("2026-07-17", "2026-08-15", 4, days=30)) is None
    assert normalized_growth(window("2026-08-16", "2026-09-14", 8, days=30),
                             window("2026-07-17", "2026-08-15", 4, days=30), required_days=None) is not None


def test_growth_null_not_zero_when_incomplete():
    prev = window("2026-03-19", "2026-06-16", 4)
    rec = window("2026-06-17", "2026-09-14", 8, complete_period=False)
    assert normalized_growth(rec, prev) is None
    assert normalized_growth(rec, prev) != 0


def test_growth_matches_reference_formula():
    prev = window("2026-03-19", "2026-06-16", 4)
    rec = window("2026-06-17", "2026-09-14", 8)
    assert normalized_growth(rec, prev) == pytest.approx(reference.normalized_growth(rec, prev))


def test_validate_contract_ok_returns_none():
    assert validate_contract(base()) is None
