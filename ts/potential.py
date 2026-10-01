"""Deterministic review priority for scored observations below weak-signal status.

The resulting numbers are evidence-triage indices, not probabilities of technical
success, demand, adoption, revenue, or investment return.  Missing dimensions
stay ``None`` and are never silently converted to zero.
"""
from __future__ import annotations

from collections.abc import Iterable

from ts.checklist import CHECKLIST_VERSION
from ts.fanout import _identity

POTENTIAL_VERSION = "potential-v2"
WATCHLIST_THRESHOLD = 0.35
WEAK_SIGNAL_THRESHOLD = 0.60
NEAR_GATE_FLOOR = 0.25
HIGH_POTENTIAL_THRESHOLD = 65.0
DEFAULT_CAP = 8

AXIS_CODES = {
    "technical": frozenset({"P01", "P02", "P03", "P06", "P07", "P10", "P16", "P17"}),
    "demand": frozenset({"P05", "P09", "P14", "P15"}),
    "development": frozenset({"P04", "P08", "P11", "P12", "P13", "P18"}),
}
AXIS_WEIGHTS = {"technical": 0.45, "demand": 0.30, "development": 0.25}
STATUS_STRENGTH = {"verified": 1.0, "supported": 0.5, "unknown": 0.0, "absent": 0.0}
COUNTER_CODES = frozenset({"M01", "M02", "M03", "M04", "M05", "M06"})


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _axis_values(predictors: Iterable[dict], codes: frozenset[str]) -> tuple[list[float], list[str]]:
    """Return one strongest recognized status per code, so duplicates cannot inflate a score."""
    by_code: dict[str, float] = {}
    for row in predictors:
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or "")
        value = row.get("value")
        if code not in codes or value not in STATUS_STRENGTH:
            continue
        by_code[code] = max(by_code.get(code, 0.0), STATUS_STRENGTH[value])
    ordered = sorted(by_code.values(), reverse=True)
    return ordered, sorted(by_code)


def _axis_score(values: list[float]) -> float | None:
    if not values:
        return None
    strongest = values[0]
    second = values[1] if len(values) > 1 else 0.0
    return round(100.0 * (0.7 * strongest + 0.3 * second), 1)


def potential_metrics(card: dict) -> dict:
    """Describe evidenced potential and gate proximity without making a forecast."""
    predictors = card.get("predictors") if isinstance(card, dict) else None
    predictors = predictors if isinstance(predictors, list) else []
    metrics: dict[str, float | int | None | dict] = {}
    evidence_codes: dict[str, list[str]] = {}
    for axis, codes in AXIS_CODES.items():
        values, found = _axis_values(predictors, codes)
        metrics[axis] = _axis_score(values)
        evidence_codes[axis] = found

    evaluated = [axis for axis in AXIS_CODES if metrics[axis] is not None]
    if evaluated:
        weight_total = sum(AXIS_WEIGHTS[axis] for axis in evaluated)
        observed_mean = sum(
            AXIS_WEIGHTS[axis] * float(metrics[axis]) for axis in evaluated
        ) / weight_total
        coverage_factor = 0.5 + len(evaluated) / 6.0
        potential_index: float | None = round(observed_mean * coverage_factor, 1)
    else:
        potential_index = None

    confidence = card.get("confidence") if isinstance(card, dict) else None
    gate_proximity = None
    gate_target = WATCHLIST_THRESHOLD
    if _number(confidence):
        if float(confidence) >= WATCHLIST_THRESHOLD:
            gate_target = WEAK_SIGNAL_THRESHOLD
        gate_proximity = round(
            100.0 * max(0.0, min(float(confidence), gate_target)) / gate_target,
            1,
        )
    metrics.update({
        "evaluated_axes": len(evaluated),
        "potential_index": potential_index,
        "gate_proximity": gate_proximity,
        "gate_target": gate_target,
        "evidence_codes": evidence_codes,
    })
    return metrics


def _eligible(card: dict) -> bool:
    checklist = card.get("checklist")
    if not isinstance(checklist, dict) or checklist.get("status") != "scored":
        return False
    if checklist.get("version") != CHECKLIST_VERSION:
        return False
    confidence = card.get("confidence")
    if not _number(confidence) or not 0 <= float(confidence) < WEAK_SIGNAL_THRESHOLD:
        return False
    if float(confidence) < WATCHLIST_THRESHOLD:
        if card.get("policy_reason") != "checklist_below_watchlist":
            return False
    elif card.get("label") != "watchlist" or card.get("policy_reason") not in {
        "evidence_gates_passed", "theme_quota", "beyond_top_n", "below_tau",
    }:
        return False
    for row in card.get("predictors") or []:
        if isinstance(row, dict) and str(row.get("code") or "") in COUNTER_CODES:
            return False
    return True


def rank_potential_cards(payload: dict, *, cap: int = DEFAULT_CAP) -> list[dict]:
    """Rank observations worth another check; never change their signal label.

    A card enters for being close to the existing gate or for having a high
    evidence-based potential index.  The review priority is the stronger of
    those two triage signals, not a combined probability.
    """
    registry = [
        card for bucket in ("top", "exclusion_registry")
        for card in (payload.get(bucket) or [])
    ] if isinstance(payload, dict) else []
    rows: list[dict] = []
    seen: set[tuple] = set()
    for card in registry or []:
        if not isinstance(card, dict) or not _eligible(card):
            continue
        identity = _identity(card)
        if identity in seen:
            continue
        seen.add(identity)
        confidence = float(card["confidence"])
        potential = potential_metrics(card)
        reasons = []
        if NEAR_GATE_FLOOR <= confidence < WATCHLIST_THRESHOLD:
            reasons.append("near_gate")
        potential_index = potential["potential_index"]
        if _number(potential_index) and float(potential_index) >= HIGH_POTENTIAL_THRESHOLD:
            reasons.append("high_potential")
        if not reasons:
            continue
        gate_proximity = float(potential["gate_proximity"] or 0.0)
        potential_value = float(potential_index or 0.0)
        row = dict(card)
        row.update({
            "potential_version": POTENTIAL_VERSION,
            "potential": potential,
            "selection_reasons": reasons,
            "gate_target": potential["gate_target"],
            "gate_gap": round(float(potential["gate_target"]) - confidence, 4),
            "review_priority": round(max(
                gate_proximity if "near_gate" in reasons else 0.0, potential_value,
            ), 1),
        })
        rows.append(row)
    rows.sort(key=lambda row: (
        -float(row["review_priority"]),
        -float(row["potential"].get("potential_index") or 0.0),
        -float(row["potential"].get("gate_proximity") or 0.0),
        -float(row.get("confidence") or 0.0),
        str(row.get("technology") or row.get("id") or ""),
    ))
    return rows[:max(0, int(cap))]
