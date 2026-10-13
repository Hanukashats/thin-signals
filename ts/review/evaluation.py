"""Deterministic replay/holdout evaluation for the bounded review round.

This measures contracts and arbitration over frozen fixtures. It deliberately
does not claim to measure live model research quality; that requires the release
canary and remains a separate gate.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ts.llm import MANDATORY_PROVIDER_POLICY
from ts.review.arbiter import ARBITER_RULE_VERSION
from ts.review.contracts import EvidenceItem
from ts.review.runner import (
    ReviewModels,
    RoleBudget,
    RoleCallResult,
    review_hash,
    run_review,
)

PATHS = ("baseline", "proposed", "no_defender", "no_control")
ACCEPTED = frozenset({"PROMOTE", "REFRAME"})
SCENARIOS = frozenset({
    "clean_positive",
    "defended_positive",
    "fatal_false_novelty",
    "fatal_mass_adoption",
    "unresolved_critical",
    "insufficient_origins",
    "base_watchlist",
    "valid_narrowing",
    "evidence_less",
    "noncritical_objection",
    "defended_multi_objection",
    "fatal_chronology",
    "critical_unknown",
    "weak_provenance",
    "base_mature",
    "valid_correction",
    "provider_failure",
})
_BUDGET = RoleBudget(5.0, 500, 0.02, 4)
_MODELS = ReviewModels(primary="fixture-primary", judge="fixture-judge")


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def load_review_dataset(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {
        "version", "fixture_version", "frozen_code_sha", "arbiter_candidate",
        "replay", "holdout", "cases",
    }
    if not isinstance(data, dict) or not required <= set(data):
        raise ValueError("review evaluation dataset is incomplete")
    if not isinstance(data["cases"], list) or not data["cases"]:
        raise ValueError("review evaluation cases are missing")
    if not isinstance(data["holdout"], dict) or data["holdout"].get("sealed") is not True:
        raise ValueError("review holdout must be sealed")
    if data["arbiter_candidate"] != ARBITER_RULE_VERSION:
        raise ValueError("review dataset arbiter candidate does not match executable contract")
    seen: set[str] = set()
    for row in data["cases"]:
        if not isinstance(row, dict):
            raise TypeError("review evaluation case must be an object")
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError("review evaluation case ids must be unique strings")
        seen.add(case_id)
        if row.get("split") not in {"replay", "holdout"}:
            raise ValueError(f"invalid split for {case_id}")
        if row.get("scenario") not in SCENARIOS:
            raise ValueError(f"invalid scenario for {case_id}")
        if type(row.get("gold_accept")) is not bool:
            raise ValueError(f"invalid gold_accept for {case_id}")
        if row.get("gold_verdict") not in {"PROMOTE", "REFRAME", "HOLD", "REJECT"}:
            raise ValueError(f"invalid gold verdict for {case_id}")
        if (row["gold_verdict"] in ACCEPTED) != row["gold_accept"]:
            raise ValueError(f"inconsistent gold verdict for {case_id}")
        if not isinstance(row.get("risk_flags"), list) or not isinstance(row.get("adjudication"), str):
            raise TypeError(f"invalid adjudication for {case_id}")
    splits = {row["split"] for row in data["cases"]}
    if splits != {"replay", "holdout"}:
        raise ValueError("both replay and holdout splits are required")
    replay_scenarios = {
        row["scenario"] for row in data["cases"] if row["split"] == "replay"
    }
    holdout_scenarios = {
        row["scenario"] for row in data["cases"] if row["split"] == "holdout"
    }
    if not replay_scenarios.isdisjoint(holdout_scenarios):
        raise ValueError("replay and holdout scenarios must be structurally distinct")
    return data


def _evidence(
    evidence_id: str,
    origin: str,
    marker: str,
    provenance: str = "preserved_primary",
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        quote=f"Frozen attested fixture text for {evidence_id}.",
        url=f"https://fixture.invalid/{evidence_id}",
        provenance=provenance,
        snapshot_ref="sha256:" + marker * 64,
        origin_group_id=origin,
    )


def _candidate(case: dict) -> dict:
    if case["scenario"] == "base_watchlist":
        label, confidence, action, reason = "watchlist", 0.45, "WATCHLIST", "below_tau"
    elif case["scenario"] == "base_mature":
        label, confidence, action, reason = "mature", None, "REJECT_OR_REFRAME", "verified_fatal_claim"
    else:
        label, confidence, action, reason = "weak_signal", 0.72, "RANK_ELIGIBLE", "evidence_gates_passed"
    return {
        "technology": case["technology"],
        "label": label,
        "confidence": confidence,
        "policy_action": action,
        "policy_reason": reason,
        "reason_codes": ["P01"],
        "predictors": [{"code": "P01", "value": "verified"}],
    }


def _base_outputs(claim_evidence: list[str]) -> dict[str, dict]:
    return {
        "researcher": {
            "claims": [{
                "claim_id": "claim-1",
                "statement": "The evidence reports an early mechanism.",
                "critical": True,
                "evidence_ids": claim_evidence,
                "status": "verified",
                "reason_codes": ["P01"],
            }],
            "promotion_hypothesis": "The mechanism may qualify as a weak signal.",
            "uncertainties": [],
        },
        "critic": {"objections": []},
        "defender": {"rebuttals": []},
        "control_critic": {"findings": []},
    }


def _fixture(case: dict) -> tuple[dict, list[EvidenceItem], dict[str, dict]]:
    scenario = case["scenario"]
    evidence = [
        _evidence("evidence-1", "ror:origin-a", "1"),
        _evidence("evidence-2", "ror:origin-b", "2"),
        _evidence("evidence-3", "ror:origin-c", "3"),
    ]
    outputs = _base_outputs(["evidence-1", "evidence-2"])
    if scenario == "evidence_less":
        evidence = []
        outputs = _base_outputs(["evidence-missing"])
    elif scenario == "insufficient_origins":
        evidence = evidence[:1]
        outputs = _base_outputs(["evidence-1"])
    elif scenario in {"defended_positive", "unresolved_critical", "valid_narrowing"}:
        outputs = _base_outputs(["evidence-1"])
        outputs["critic"] = {"objections": [{
            "objection_id": "objection-1",
            "claim_id": "claim-1",
            "failure_mode": "unsupported_transition" if scenario == "unresolved_critical" else "single_origin",
            "counterevidence_ids": ["evidence-2"],
            "severity": "critical",
            "status": "supported",
            "statement": "A critical evidence gap must be resolved.",
        }]}
        if scenario == "valid_narrowing":
            outputs["defender"] = {"rebuttals": [{
                "rebuttal_id": "rebuttal-1",
                "objection_id": "objection-1",
                "action": "NARROW",
                "evidence_ids": ["evidence-1", "evidence-3"],
                "replacement_claim": {
                    "claim_id": "claim-1-narrow",
                    "statement": "The preserved evidence supports a laboratory prototype only.",
                    "critical": True,
                    "evidence_ids": ["evidence-1", "evidence-3"],
                    "status": "verified",
                    "reason_codes": ["P01"],
                },
                "changed_fields": ["statement", "scope", "evidence_ids"],
                "statement": "The overbroad deployment scope is removed.",
            }]}
        else:
            outputs["defender"] = {"rebuttals": [{
                "rebuttal_id": "rebuttal-1",
                "objection_id": "objection-1",
                "action": "ADD_EVIDENCE",
                "evidence_ids": ["evidence-3"],
                "replacement_claim": None,
                "changed_fields": [],
                "statement": "A second independent preserved origin is added.",
            }]}
        outputs["control_critic"] = {"findings": [{
            "finding_id": "finding-1",
            "objection_id": "objection-1",
            "rebuttal_id": "rebuttal-1",
            "evidence_ids": (
                ["evidence-1", "evidence-3"]
                if scenario == "valid_narrowing"
                else ["evidence-3"]
            ),
            "evidence_valid": True,
            "origin_independent": True,
            "residual_status": "unresolved" if scenario == "unresolved_critical" else "resolved",
            "statement": "The cited response is independently checked.",
        }]}
    elif scenario in {"fatal_false_novelty", "fatal_mass_adoption"}:
        failure_mode = "false_novelty" if scenario == "fatal_false_novelty" else "mass_adoption"
        outputs["critic"] = {"objections": [{
            "objection_id": "objection-1",
            "claim_id": "claim-1",
            "failure_mode": failure_mode,
            "counterevidence_ids": ["evidence-2"],
            "severity": "fatal",
            "status": "verified",
            "statement": "Preserved counterevidence verifies a fatal contradiction.",
        }]}
        outputs["defender"] = {"rebuttals": [{
            "rebuttal_id": "rebuttal-1",
            "objection_id": "objection-1",
            "action": "CONCEDE",
            "evidence_ids": [],
            "replacement_claim": None,
            "changed_fields": [],
            "statement": "The fatal contradiction is conceded.",
        }]}
        outputs["control_critic"] = {"findings": [{
            "finding_id": "finding-1",
            "objection_id": "objection-1",
            "rebuttal_id": "rebuttal-1",
            "evidence_ids": ["evidence-2"],
            "evidence_valid": True,
            "origin_independent": False,
            "residual_status": "fatal",
            "statement": "The fatal counterevidence is valid.",
        }]}
    elif scenario == "noncritical_objection":
        outputs["researcher"]["claims"][0]["critical"] = False
        outputs["critic"] = {"objections": [{
            "objection_id": "objection-1",
            "claim_id": "claim-1",
            "failure_mode": "weak_provenance",
            "counterevidence_ids": ["evidence-3"],
            "severity": "material",
            "status": "supported",
            "statement": "A noncritical provenance caveat remains visible.",
        }]}
        outputs["control_critic"] = {"findings": [{
            "finding_id": "finding-1",
            "objection_id": "objection-1",
            "rebuttal_id": None,
            "evidence_ids": ["evidence-3"],
            "evidence_valid": True,
            "origin_independent": True,
            "residual_status": "unresolved",
            "statement": "The material caveat remains but is not a critical blocker.",
        }]}
    elif scenario == "defended_multi_objection":
        evidence.append(_evidence("evidence-4", "ror:origin-d", "4"))
        outputs["researcher"]["claims"].append({
            "claim_id": "claim-2",
            "statement": "A second critical technical claim is reported.",
            "critical": True,
            "evidence_ids": ["evidence-2"],
            "status": "verified",
            "reason_codes": ["P03"],
        })
        outputs["critic"] = {"objections": [
            {
                "objection_id": "objection-1",
                "claim_id": "claim-1",
                "failure_mode": "single_origin",
                "counterevidence_ids": ["evidence-2"],
                "severity": "critical",
                "status": "supported",
                "statement": "The first claim needs an independent origin.",
            },
            {
                "objection_id": "objection-2",
                "claim_id": "claim-2",
                "failure_mode": "unsupported_transition",
                "counterevidence_ids": ["evidence-1"],
                "severity": "critical",
                "status": "supported",
                "statement": "The second claim needs independent transition evidence.",
            },
        ]}
        outputs["defender"] = {"rebuttals": [
            {
                "rebuttal_id": "rebuttal-1",
                "objection_id": "objection-1",
                "action": "ADD_EVIDENCE",
                "evidence_ids": ["evidence-3"],
                "replacement_claim": None,
                "changed_fields": [],
                "statement": "A third origin resolves the first objection.",
            },
            {
                "rebuttal_id": "rebuttal-2",
                "objection_id": "objection-2",
                "action": "ADD_EVIDENCE",
                "evidence_ids": ["evidence-4"],
                "replacement_claim": None,
                "changed_fields": [],
                "statement": "A fourth origin resolves the second objection.",
            },
        ]}
        outputs["control_critic"] = {"findings": [
            {
                "finding_id": "finding-1",
                "objection_id": "objection-1",
                "rebuttal_id": "rebuttal-1",
                "evidence_ids": ["evidence-3"],
                "evidence_valid": True,
                "origin_independent": True,
                "residual_status": "resolved",
                "statement": "The first new origin is valid and independent.",
            },
            {
                "finding_id": "finding-2",
                "objection_id": "objection-2",
                "rebuttal_id": "rebuttal-2",
                "evidence_ids": ["evidence-4"],
                "evidence_valid": True,
                "origin_independent": True,
                "residual_status": "resolved",
                "statement": "The second new origin is valid and independent.",
            },
        ]}
    elif scenario == "fatal_chronology":
        outputs["critic"] = {"objections": [{
            "objection_id": "objection-1",
            "claim_id": "claim-1",
            "failure_mode": "chronology_conflict",
            "counterevidence_ids": ["evidence-2"],
            "severity": "fatal",
            "status": "verified",
            "statement": "Earlier preserved evidence fatally contradicts the chronology.",
        }]}
        outputs["defender"] = {"rebuttals": [{
            "rebuttal_id": "rebuttal-1",
            "objection_id": "objection-1",
            "action": "CONCEDE",
            "evidence_ids": [],
            "replacement_claim": None,
            "changed_fields": [],
            "statement": "The chronology conflict is conceded.",
        }]}
        outputs["control_critic"] = {"findings": [{
            "finding_id": "finding-1",
            "objection_id": "objection-1",
            "rebuttal_id": "rebuttal-1",
            "evidence_ids": ["evidence-2"],
            "evidence_valid": True,
            "origin_independent": False,
            "residual_status": "fatal",
            "statement": "The chronology contradiction is verified.",
        }]}
    elif scenario == "critical_unknown":
        outputs["researcher"]["claims"][0]["status"] = "unknown"
    elif scenario == "weak_provenance":
        evidence = [
            _evidence("evidence-1", "ror:origin-a", "1", "preserved_non_primary"),
            _evidence("evidence-2", "ror:origin-b", "2", "preserved_non_primary"),
        ]
        outputs["researcher"]["claims"][0]["status"] = "supported"
    elif scenario == "valid_correction":
        outputs = _base_outputs(["evidence-1"])
        outputs["critic"] = {"objections": [{
            "objection_id": "objection-1",
            "claim_id": "claim-1",
            "failure_mode": "unsupported_transition",
            "counterevidence_ids": ["evidence-2"],
            "severity": "critical",
            "status": "supported",
            "statement": "The original mechanism wording is unsupported.",
        }]}
        outputs["defender"] = {"rebuttals": [{
            "rebuttal_id": "rebuttal-1",
            "objection_id": "objection-1",
            "action": "CORRECT",
            "evidence_ids": ["evidence-1", "evidence-3"],
            "replacement_claim": {
                "claim_id": "claim-1-corrected",
                "statement": "The preserved evidence supports the corrected mechanism wording.",
                "critical": True,
                "evidence_ids": ["evidence-1", "evidence-3"],
                "status": "verified",
                "reason_codes": ["P01"],
            },
            "changed_fields": ["statement", "evidence_ids"],
            "statement": "The claim is corrected to match the attested evidence.",
        }]}
        outputs["control_critic"] = {"findings": [{
            "finding_id": "finding-1",
            "objection_id": "objection-1",
            "rebuttal_id": "rebuttal-1",
            "evidence_ids": ["evidence-1", "evidence-3"],
            "evidence_valid": True,
            "origin_independent": True,
            "residual_status": "resolved",
            "statement": "The corrected claim is attested and resolves the objection.",
        }]}
    return _candidate(case), evidence, outputs


@dataclass
class _Provider:
    rows: list[EvidenceItem]

    def retrieve(self, _role, _candidate, _budget):
        return list(self.rows)


@dataclass
class _Gateway:
    outputs: dict[str, dict]
    failure_roles: frozenset[str] = frozenset()

    def call(self, role, _messages, _schema, _budget, model):
        if role in self.failure_roles:
            raise RuntimeError("deterministic provider failure fixture")
        return RoleCallResult(
            payload=deepcopy(self.outputs[role]),
            model_id=model,
            provider="FixtureZDR",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            latency_s=0.01,
            cost_usd=0.001,
            provider_policy=dict(MANDATORY_PROVIDER_POLICY),
        )

    @staticmethod
    def route_is_valid(requested_model, response_model, provider):
        return requested_model == response_model and provider == "FixtureZDR"


def _resources(events) -> dict[str, int | float]:
    selected = [event for event in events if event.role != "arbiter"]
    return {
        # The fixture gateway declares 10 ms for every completed role call.
        # Wall-clock Python overhead is intentionally excluded from the stable artifact.
        "latency_ms": sum(10 for event in selected if event.total_tokens is not None),
        "tokens": sum(event.total_tokens or 0 for event in selected),
        "cost_usd": round(sum(event.cost_usd or 0.0 for event in selected), 6),
    }


def _primary_origin_count(
    evidence: list[EvidenceItem], evidence_ids: set[str] | None = None,
) -> int:
    origins = {
        row.origin_group_id for row in evidence
        if (
            row.provenance == "preserved_primary"
            and row.snapshot_ref
            and row.origin_group_id
            and (evidence_ids is None or row.evidence_id in evidence_ids)
        )
    }
    return len(origins)


def _promotion_evidence_ids(outputs: dict[str, dict]) -> set[str]:
    claims = outputs["researcher"].get("claims", [])
    critical_claim_ids = {
        claim.get("claim_id") for claim in claims if claim.get("critical")
    }
    selected_claim_ids = critical_claim_ids or {
        claim.get("claim_id") for claim in claims
    }
    evidence_by_claim = {
        claim.get("claim_id"): set(claim.get("evidence_ids", []))
        for claim in claims
        if claim.get("claim_id") in selected_claim_ids
    }
    objection_claims = {
        objection.get("objection_id"): objection.get("claim_id")
        for objection in outputs["critic"].get("objections", [])
    }
    rebuttals_by_claim: dict[str, list[dict]] = {}
    for rebuttal in outputs["defender"].get("rebuttals", []):
        claim_id = objection_claims.get(rebuttal.get("objection_id"))
        if claim_id not in selected_claim_ids:
            continue
        rebuttals_by_claim.setdefault(claim_id, []).append(rebuttal)
    for claim_id, rebuttals in rebuttals_by_claim.items():
        replacements = [
            rebuttal for rebuttal in rebuttals
            if rebuttal.get("action") in {"CORRECT", "NARROW"}
        ]
        if replacements:
            if len(replacements) != 1 or len(rebuttals) != 1:
                # Match the runner's fail-closed unordered-round contract.
                evidence_by_claim[claim_id] = set()
                continue
            replacement = replacements[0].get("replacement_claim")
            # Match the arbiter's effective-claim semantics: a replacement must
            # explicitly retain every citation it wants credited.
            evidence_by_claim[claim_id] = set(
                replacement.get("evidence_ids", [])
                if isinstance(replacement, dict)
                else []
            )
            continue
        for rebuttal in rebuttals:
            if rebuttal.get("action") == "ADD_EVIDENCE":
                evidence_by_claim[claim_id].update(rebuttal.get("evidence_ids", []))
    return {
        evidence_id
        for evidence_ids in evidence_by_claim.values()
        for evidence_id in evidence_ids
    }


def _has_unresolved_critical(outputs: dict[str, dict]) -> bool:
    claims = {
        claim["claim_id"]: claim
        for claim in outputs["researcher"].get("claims", [])
    }
    if any(
        claim.get("critical") and claim.get("status") == "unknown"
        for claim in claims.values()
    ):
        return True
    findings = {
        finding["objection_id"]: finding
        for finding in outputs["control_critic"].get("findings", [])
    }
    rebuttals = {
        rebuttal["objection_id"]: rebuttal
        for rebuttal in outputs["defender"].get("rebuttals", [])
    }
    for objection in outputs["critic"].get("objections", []):
        claim = claims.get(objection.get("claim_id"))
        critical = bool(claim and claim.get("critical")) or objection.get("severity") in {
            "critical", "fatal",
        }
        if not critical:
            continue
        finding = findings.get(objection.get("objection_id"))
        rebuttal = rebuttals.get(objection.get("objection_id"))
        if (
            not isinstance(finding, dict)
            or not isinstance(rebuttal, dict)
            or finding.get("residual_status") != "resolved"
            or finding.get("evidence_valid") is not True
            or finding.get("rebuttal_id") != rebuttal.get("rebuttal_id")
        ):
            return True
        accepted_ids = set(rebuttal.get("evidence_ids", []))
        replacement = rebuttal.get("replacement_claim")
        if isinstance(replacement, dict):
            accepted_ids.update(replacement.get("evidence_ids", []))
        if not accepted_ids <= set(finding.get("evidence_ids", [])):
            return True
        action = rebuttal.get("action")
        if action == "ADD_EVIDENCE" and finding.get("origin_independent") is not True:
            return True
        if action in {"CORRECT", "NARROW"} and (
            not isinstance(replacement, dict)
            or replacement.get("status") == "unknown"
            or replacement.get("critical") is not True
        ):
            return True
        if action == "CONCEDE":
            return True
    return False


def _role_errors(round_result) -> list[list[str]]:
    return [
        [event.role, str(event.error_code)]
        for event in round_result.events
        if event.role != "arbiter" and event.error_code
    ]


def evaluate_case(case: dict) -> dict[str, dict[str, Any]]:
    """Evaluate paths without consulting gold_accept, gold_verdict or adjudication."""
    candidate, evidence, output_payloads = _fixture(case)
    scenario_failures = {"critic"} if case["scenario"] == "provider_failure" else set()

    def execute(path: str):
        unavailable_role = {
            "proposed": None,
            "no_defender": "defender",
            "no_control": "control_critic",
        }[path]
        failure_roles = set(scenario_failures)
        if unavailable_role is not None:
            failure_roles.add(unavailable_role)
        return run_review(
            run_id=f"eval-{case['case_id']}-{path}",
            candidate=candidate,
            gateway=_Gateway(output_payloads, frozenset(failure_roles)),
            evidence_provider=_Provider(evidence),
            budget=_BUDGET,
            models=_MODELS,
        )

    first = execute("proposed")
    second = execute("proposed")
    ablation_rounds = {
        path: (execute(path), execute(path))
        for path in ("no_defender", "no_control")
    }

    baseline_verdict = (
        "PROMOTE"
        if candidate["policy_action"] == "RANK_ELIGIBLE" and candidate["label"] == "weak_signal"
        else "HOLD"
    )
    results = {
        "baseline": {
            "verdict": baseline_verdict,
            "ledger_revision": review_hash([case["case_id"], "baseline", candidate]),
            "stable": True,
            "latency_ms": 0,
            "tokens": 0,
            "cost_usd": 0.0,
            "role_errors": [],
        },
        "proposed": {
            "verdict": first.decision.verdict,
            "ledger_revision": first.ledger_revision,
            "stable": first.decision == second.decision and first.ledger_revision == second.ledger_revision,
            "role_errors": _role_errors(first),
            **_resources(first.events),
        },
    }
    for path, (first_ablation, second_ablation) in ablation_rounds.items():
        results[path] = {
            "verdict": first_ablation.decision.verdict,
            "ledger_revision": first_ablation.ledger_revision,
            "stable": (
                first_ablation.decision == second_ablation.decision
                and first_ablation.ledger_revision == second_ablation.ledger_revision
            ),
            "role_errors": _role_errors(first_ablation),
            **_resources(first_ablation.events),
        }
    # The baseline projection has no typed citation contract, so available
    # fixture evidence cannot be credited as decision evidence.
    results["baseline"]["primary_origin_count"] = 0
    results["proposed"]["primary_origin_count"] = _primary_origin_count(
        evidence, _promotion_evidence_ids(output_payloads),
    )
    for path in ("no_defender", "no_control"):
        results[path]["primary_origin_count"] = 0
    for row in results.values():
        row["evidence_covered"] = row["primary_origin_count"] >= 2
    unresolved = _has_unresolved_critical(output_payloads)
    for path, row in results.items():
        row["unresolved_critical"] = unresolved or bool(row["role_errors"])
    return results


def _metrics(rows: list[dict], path: str) -> dict[str, int | float]:
    verdicts = [row["paths"][path]["verdict"] for row in rows]
    predicted = [verdict in ACCEPTED for verdict in verdicts]
    gold = [bool(row["gold_accept"]) for row in rows]
    tp = sum(p and g for p, g in zip(predicted, gold, strict=True))
    fp = sum(p and not g for p, g in zip(predicted, gold, strict=True))
    fn = sum(not p and g for p, g in zip(predicted, gold, strict=True))
    tn = sum(not p and not g for p, g in zip(predicted, gold, strict=True))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    accepted_rows = [row for row, value in zip(rows, predicted, strict=True) if value]
    covered = sum(row["paths"][path]["evidence_covered"] for row in accepted_rows)
    latency_ms = sum(int(row["paths"][path]["latency_ms"]) for row in rows)
    tokens = sum(int(row["paths"][path]["tokens"]) for row in rows)
    cost = sum(float(row["paths"][path]["cost_usd"]) for row in rows)
    return {
        "n": len(rows),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "false_promotions": fp,
        "evidence_less_promotions": sum(
            value and row["paths"][path]["primary_origin_count"] == 0
            for row, value in zip(rows, predicted, strict=True)
        ),
        "unresolved_critical_promotions": sum(
            value and row["paths"][path]["unresolved_critical"]
            for row, value in zip(rows, predicted, strict=True)
        ),
        "exact_verdict_accuracy": round(sum(
            verdict == row["gold_verdict"]
            for row, verdict in zip(rows, verdicts, strict=True)
        ) / len(rows), 4),
        "overpromotions": sum(
            verdict == "PROMOTE" and row["gold_verdict"] != "PROMOTE"
            for row, verdict in zip(rows, verdicts, strict=True)
        ),
        "evidence_coverage": round(covered / len(accepted_rows), 4) if accepted_rows else 1.0,
        "stability": round(sum(row["paths"][path]["stable"] for row in rows) / len(rows), 4),
        "latency_ms": latency_ms,
        "mean_latency_ms": round(latency_ms / len(rows), 2),
        "tokens": tokens,
        "mean_tokens": round(tokens / len(rows), 2),
        "cost_usd": round(cost, 6),
        "mean_cost_usd": round(cost / len(rows), 6),
    }


def evaluate_review_dataset(dataset: dict) -> dict:
    evaluated = []
    for case in dataset["cases"]:
        evaluated.append({
            "case_id": case["case_id"],
            "split": case["split"],
            "scenario": case["scenario"],
            "gold_accept": case["gold_accept"],
            "gold_verdict": case["gold_verdict"],
            "risk_flags": list(case["risk_flags"]),
            "paths": evaluate_case(case),
        })
    metrics = {}
    for split in ("replay", "holdout", "all"):
        rows = evaluated if split == "all" else [row for row in evaluated if row["split"] == split]
        metrics[split] = {path: _metrics(rows, path) for path in PATHS}
    deterministic = {
        "dataset_version": dataset["version"],
        "fixture_version": dataset["fixture_version"],
        "frozen_code_sha": dataset["frozen_code_sha"],
        "arbiter_candidate": dataset["arbiter_candidate"],
        "dataset_digest": _digest(dataset),
        "cases": evaluated,
        "metrics": metrics,
        "limitations": [
            "Frozen fixtures measure contract, fail-closed and arbiter behavior.",
            "They do not measure live model retrieval or reasoning quality.",
            "Live quality and candidate count require a separately bounded production canary.",
        ],
    }
    deterministic["result_digest"] = _digest(deterministic)
    return deterministic


def render_review_report(summary: dict) -> str:
    lines = [
        "# Adversarial review evaluation — replay + sealed holdout",
        "",
        (
            f"Dataset `{summary['dataset_version']}` · fixture `{summary['fixture_version']}` · "
            f"frozen code `{summary['frozen_code_sha']}` · arbiter `{summary['arbiter_candidate']}`."
        ),
        "",
        "| split/path | P | R | exact | overpromote | false promote | evidence-less | unresolved | coverage | stable | fixture ms | tokens | cost USD |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for split in ("replay", "holdout", "all"):
        for path in PATHS:
            row = summary["metrics"][split][path]
            lines.append(
                f"| {split}/{path} | {row['precision']:.4f} | {row['recall']:.4f} | "
                f"{row['exact_verdict_accuracy']:.4f} | {row['overpromotions']} | "
                f"{row['false_promotions']} | {row['evidence_less_promotions']} | "
                f"{row['unresolved_critical_promotions']} | {row['evidence_coverage']:.4f} | "
                f"{row['stability']:.4f} | {row['latency_ms']} | {row['tokens']} | {row['cost_usd']:.6f} |"
            )
    lines += [
        "",
        "## Interpretation",
        "",
        (
            "`baseline` is the pre-review base admission. `proposed` runs all four typed roles and the "
            "deterministic arbiter. Role-removal ablations execute the same runner twice with the selected role "
            "unavailable; their typed failure, downstream validation, stability and resources are measured rather "
            "than reconstructed post hoc."
        ),
        "",
        "## Limitation",
        "",
        (
            "Это fixture-оценка контрактов и арбитра; она **не измеряет качество живых ответов модели**. "
            "Реальный поиск, число квалифицированных сигналов и сетевые расходы проверяются отдельным bounded canary."
        ),
        "",
        f"Dataset SHA-256: `{summary['dataset_digest']}`",
        f"Result SHA-256: `{summary['result_digest']}`",
    ]
    return "\n".join(lines) + "\n"


def write_review_evaluation(dataset_path: Path, out_dir: Path) -> dict:
    dataset = load_review_dataset(dataset_path)
    summary = evaluate_review_dataset(dataset)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "report.md").write_text(render_review_report(summary), encoding="utf-8")
    return summary
