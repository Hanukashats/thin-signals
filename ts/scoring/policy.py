"""Evidence gates for a candidate (METHODOLOGY §3).

Adapted from reference/policy.py (v6.1, unchanged copy kept for provenance).
Changes vs reference — KNOWN_GAPS #1 / Library audit F03:
  * type checks happen BEFORE set membership (novelty=[] / critical_claims=[{}] → HOLD, not TypeError);
  * non-dict input → HOLD invalid_contract;
  * independent_origins > evidence_events is rejected as contract violation (aggregates must come
    from the ledger; an origin group without an event is impossible);
  * every result carries `gate` (which gate decided) so the UI can show it as a predictor.
Order of gates is intentionally identical to the reference and covered by tests.
"""
from __future__ import annotations

from datetime import date
from math import log2
from typing import Any, Mapping, Optional

STATUSES = frozenset({"verified", "supported", "unknown", "disputed", "refuted"})
NOVELTY = frozenset({"new", "known", "unclear"})
MATURITY = frozenset({"emerging", "established", "unclear"})
FATAL = frozenset({"verified", "weak", "none"})
BOOL_FIELDS = (
    "countersearch_done", "source_availability_valid", "budget_exhausted",
    "branches_complete", "transition_verified",
)
INT_FIELDS = ("evidence_events", "independent_origins")
REQUIRED = frozenset(
    {"as_of", "novelty", "maturity", "critical_claims", "fatal_finding", *INT_FIELDS, *BOOL_FIELDS}
)

# Versioned admission heuristic (METHODOLOGY §3 p.6) — not a scientific constant.
MIN_EVENTS = 3
MIN_ORIGINS = 2


def _hold(reason: str, trigger: str, gate: str = "contract") -> dict[str, Any]:
    return {"action": "HOLD", "reason": reason, "trigger": trigger, "gate": gate}


def _is_str_in(value: Any, allowed: frozenset) -> bool:
    return isinstance(value, str) and value in allowed


def validate_contract(s: Any) -> Optional[dict[str, Any]]:
    """Return a HOLD dict when the input violates the contract, else None."""
    if not isinstance(s, Mapping):
        return _hold("invalid_contract", "pass_mapping_with_required_fields")
    if not REQUIRED <= set(s.keys()):
        return _hold("invalid_contract", "complete_required_fields")
    if not isinstance(s["as_of"], str):
        return _hold("invalid_as_of", "correct_date")
    try:
        date.fromisoformat(s["as_of"])
    except ValueError:
        return _hold("invalid_as_of", "correct_date")
    if not (_is_str_in(s["novelty"], NOVELTY) and _is_str_in(s["maturity"], MATURITY)
            and _is_str_in(s["fatal_finding"], FATAL)):
        return _hold("invalid_contract", "correct_types_and_enums")
    claims = s["critical_claims"]
    if not isinstance(claims, list) or not all(_is_str_in(c, STATUSES) for c in claims):
        return _hold("invalid_contract", "correct_types_and_enums")
    if any(type(s[k]) is not bool for k in BOOL_FIELDS):
        return _hold("invalid_contract", "correct_types_and_enums")
    if any(type(s[k]) is not int or s[k] < 0 for k in INT_FIELDS):
        return _hold("invalid_contract", "correct_types_and_enums")
    if s["independent_origins"] > s["evidence_events"]:
        return _hold("invalid_contract", "origins_cannot_exceed_events_derive_from_ledger")
    return None


def route(s: Any) -> dict[str, Any]:
    """Always apply evidence gates before budget or deadline shortcuts."""
    bad = validate_contract(s)
    if bad:
        return bad
    hold_or = lambda action: "HOLD" if s["budget_exhausted"] else action  # noqa: E731

    if not s["source_availability_valid"]:
        return _hold("unresolved_availability", "dated_accessible_evidence", "availability")
    if s["fatal_finding"] == "verified" or "refuted" in s["critical_claims"]:
        return {"action": "REJECT_OR_REFRAME", "reason": "verified_fatal_claim",
                "trigger": "materially_new_evidence", "gate": "critical_refutation"}
    if s["fatal_finding"] == "weak":
        return {"action": hold_or("VERIFY_COUNTEREVIDENCE"), "reason": "weak_negative_not_terminal",
                "trigger": "verify_scope_and_origin", "gate": "critical_refutation"}
    if not s["critical_claims"] or any(c in ("unknown", "disputed") for c in s["critical_claims"]):
        return {"action": hold_or("TARGETED_RESEARCH"), "reason": "critical_unknown",
                "trigger": "resolve_critical_claim", "gate": "critical_claims"}
    if s["maturity"] == "established" or s["novelty"] == "known":
        return {"action": "REFRAME_CHILD", "reason": "mature_parent",
                "trigger": "new_application_or_mechanism", "gate": "maturity"}
    if s["maturity"] == "unclear" or s["novelty"] == "unclear":
        return {"action": hold_or("MATURITY_RESEARCH"), "reason": "maturity_unclear",
                "trigger": "prior_art_and_adoption_evidence", "gate": "maturity"}
    if not s["countersearch_done"]:
        return {"action": hold_or("COUNTERSEARCH"), "reason": "missing_falsification",
                "trigger": "counterevidence_pass", "gate": "countersearch"}
    if s["evidence_events"] == 1 and s["independent_origins"] >= 1:
        return {"action": "WATCHLIST_SINGLETON", "reason": "one_origin_result",
                "trigger": "independent_replication_or_new_event", "gate": "independence"}
    if s["evidence_events"] < MIN_EVENTS or s["independent_origins"] < MIN_ORIGINS:
        return {"action": "WATCHLIST", "reason": "insufficient_independence",
                "trigger": "independent_evidence", "gate": "independence"}
    if not s["branches_complete"]:
        return {"action": hold_or("EXECUTE_BRANCH"), "reason": "incomplete_relevant_checks",
                "trigger": "complete_selected_branch", "gate": "branches"}
    if not s["transition_verified"]:
        return {"action": "WATCHLIST", "reason": "no_verified_change",
                "trigger": "verified_technical_or_adoption_change", "gate": "transition"}
    return {"action": "RANK_ELIGIBLE", "reason": "evidence_gates_passed", "trigger": None, "gate": "admit"}


def normalized_growth(recent: Any, previous: Any, *, required_days: Optional[int] = 90) -> Optional[float]:
    """log2 ratio of smoothed shares over two equal, complete, non-overlapping windows.

    Product configuration (METHODOLOGY §5) pins required_days=90; pass None to accept any equal length.
    Returns None (never 0) when windows are not comparable. Not a p-value.
    """
    for w in (recent, previous):
        if not isinstance(w, Mapping):
            return None
        if w.get("coverage") != "complete_for_query" or w.get("complete_period") is not True:
            return None
        if not isinstance(w.get("protocol"), str) or not w["protocol"]:
            return None
        if any(type(w.get(k)) is not int for k in ("n", "N", "days")):
            return None
        if not 0 <= w["n"] <= w["N"] or w["N"] <= 0 or w["days"] <= 0:
            return None
        try:
            start, end = date.fromisoformat(w["start"]), date.fromisoformat(w["end"])
        except (KeyError, ValueError, TypeError):
            return None
        if (end - start).days + 1 != w["days"]:
            return None
        if required_days is not None and w["days"] != required_days:
            return None
    if recent["protocol"] != previous["protocol"] or recent["days"] != previous["days"]:
        return None
    if previous["end"] >= recent["start"]:
        return None
    p_recent = (recent["n"] + 0.5) / (recent["N"] + 1)
    p_previous = (previous["n"] + 0.5) / (previous["N"] + 1)
    return log2(p_recent / p_previous)
