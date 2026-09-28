"""Deterministic scorer (METHODOLOGY §2.2, §4): features + counters -> label, confidence, visible predictors.

No learned weights. Everything that moves the number is returned in `predictors` with its weight,
value and contribution, so the card can show "по каким признакам" (TZ interpretability).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

RULES_DIR = Path(__file__).parent
Status = Literal["verified", "supported", "unknown", "absent"]
PATTERN_IDS = tuple(f"P{i:02d}" for i in range(1, 19))
COUNTER_IDS = ("M01", "M02", "M03", "M04", "M05", "M06")


def load_rules(version: str = "rules-0.1") -> dict:
    return yaml.safe_load((RULES_DIR / f"{version}.yaml").read_text())


@dataclass
class FeatureVector:
    """Input to the scorer. In `description` mode statuses are capped at `supported`."""

    primary_pattern: str
    secondary_patterns: list[str] = field(default_factory=list)
    features: dict[str, str] = field(default_factory=dict)      # P01..P18 -> status
    counters: dict[str, bool] = field(default_factory=dict)     # M01..M06 -> fired
    evidence_events: int = 0
    independent_origins: int = 0
    transition: str = "unknown"                                 # verified | supported | unknown
    evidence: dict[str, str] = field(default_factory=dict)      # code -> short quote/rationale
    mode: str = "ledger"
    named_primary: bool = True                                  # False: no pattern was chosen, do not invent one


@dataclass
class ScoreResult:
    label: str
    confidence: float | None
    reason_codes: list[str]
    predictors: list[dict]
    rules_version: str
    gate: str


def _cap(status: str, max_status: str) -> str:
    order = ["absent", "unknown", "supported", "verified"]
    return status if order.index(status) <= order.index(max_status) else max_status


def independence(events: int, origins: int) -> float:
    if events <= 0 or origins <= 0:
        return 0.0
    return min(1.0, (events - 1) / 4) * min(1.0, (origins - 1) / 2)


def score(fv: FeatureVector, rules: dict | None = None) -> ScoreResult:
    r = rules or load_rules()
    value, w, u = r["value"], r["weights"], r["penalties"]
    mode = r["modes"].get(fv.mode, {})
    max_status = mode.get("max_status", "verified")
    thr = mode.get("thresholds", r["thresholds"])
    predictors: list[dict] = []
    reasons: list[str] = []

    # --- counters short-circuit (METHODOLOGY §2.2, gate 4)
    fired = [m for m in COUNTER_IDS if fv.counters.get(m)]
    for m in fired:
        predictors.append({"code": m, "kind": "counter", "value": 1, "weight": -u[m], "contribution": -u[m],
                           "evidence": fv.evidence.get(m, "")})
        reasons.append(m)
    if fired:
        labels = {r["counter_labels"][m] for m in fired}
        label = "noise" if "noise" in labels and "mature" not in labels else "mature"
        return ScoreResult(label, None, reasons, predictors, r["version"], gate="maturity")

    # --- Σ w_i v(F-Pi): primary + capped secondary
    conf = 0.0
    if fv.named_primary:
        p_status = _cap(fv.features.get(fv.primary_pattern, "unknown"), max_status)
        c = w["primary"] * value[p_status]
        conf += c
        predictors.append({"code": fv.primary_pattern, "kind": "primary", "value": p_status, "weight": w["primary"],
                           "contribution": round(c, 4), "evidence": fv.evidence.get(fv.primary_pattern, "")})
        if p_status in ("unknown", "absent"):
            reasons.append(f"{fv.primary_pattern}_{p_status}")
    sec_total = 0.0
    for p in fv.secondary_patterns:
        if p == fv.primary_pattern or p not in PATTERN_IDS:
            continue
        s = _cap(fv.features.get(p, "unknown"), max_status)
        c = w["secondary"] * value[s]
        allowed = max(0.0, w["secondary_cap"] - sec_total)
        c = min(c, allowed)
        sec_total += c
        conf += c
        predictors.append({"code": p, "kind": "secondary", "value": s, "weight": w["secondary"],
                           "contribution": round(c, 4), "evidence": fv.evidence.get(p, "")})

    # --- independence and transition
    ind = independence(fv.evidence_events, fv.independent_origins)
    conf += w["independence"] * ind
    predictors.append({"code": "IND", "kind": "independence", "value": round(ind, 3), "weight": w["independence"],
                       "contribution": round(w["independence"] * ind, 4),
                       "evidence": f"events={fv.evidence_events}, origins={fv.independent_origins}"})
    if fv.evidence_events <= 1:
        reasons.append("singleton")
    tr = {"verified": 1.0, "supported": 0.5}.get(_cap(fv.transition, max_status), 0.0)
    conf += w["transition"] * tr
    predictors.append({"code": "TR", "kind": "transition", "value": tr, "weight": w["transition"],
                       "contribution": round(w["transition"] * tr, 4), "evidence": fv.evidence.get("TR", "")})

    conf = round(max(0.0, min(1.0, conf)), 4)
    if conf >= thr["weak_signal"]:
        label, gate = "weak_signal", "rank_eligible"
    elif conf >= thr["watchlist"]:
        label, gate = "watchlist", "watchlist"
        reasons.append("below_tau")
    else:
        label, gate = "noise", "below_watchlist"
        reasons.append("insufficient_evidence")
    return ScoreResult(label, conf, reasons, predictors, r["version"], gate=gate)
