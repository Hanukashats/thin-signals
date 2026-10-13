"""Deterministic arbitration over validated typed review records."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from ts.review.contracts import (
    ArbiterDecision,
    ControlOutput,
    CriticOutput,
    DefenderOutput,
    EvidenceItem,
    ResearcherOutput,
)

ARBITER_RULE_VERSION = "review-arbiter-0.1"


def _decision(
    verdict: str,
    ledger_revision: str,
    reasons: Sequence[str],
    blocking: Sequence[str] = (),
) -> ArbiterDecision:
    return ArbiterDecision.model_validate({
        "verdict": verdict,
        "rule_version": ARBITER_RULE_VERSION,
        "ledger_revision": ledger_revision,
        "blocking_ids": list(dict.fromkeys(blocking)),
        "reason_codes": list(dict.fromkeys(reasons)),
    })


def _attested(ids: Sequence[str], evidence: Mapping[str, EvidenceItem]) -> bool:
    return bool(ids) and all(
        evidence_id in evidence
        and evidence[evidence_id].provenance == "preserved_primary"
        and bool(evidence[evidence_id].snapshot_ref)
        for evidence_id in ids
    )


def _origins(ids: Sequence[str], evidence: Mapping[str, EvidenceItem]) -> set[str]:
    return {
        str(evidence[evidence_id].origin_group_id)
        for evidence_id in ids
        if evidence_id in evidence and evidence[evidence_id].origin_group_id
    }


def arbitrate(
    *,
    candidate: Mapping,
    researcher: ResearcherOutput | None,
    critic: CriticOutput | None,
    defender: DefenderOutput | None,
    control: ControlOutput | None,
    evidence: Mapping[str, EvidenceItem],
    failures: Sequence[tuple[str, str]],
    ledger_revision: str,
) -> ArbiterDecision:
    """Apply fail-closed rules; model prose never chooses the verdict."""
    if failures:
        return _decision(
            "HOLD",
            ledger_revision,
            [error for _role, error in failures],
            [role for role, _error in failures],
        )
    if researcher is None or critic is None or defender is None or control is None:
        return _decision("HOLD", ledger_revision, ["incomplete_review_round"], ["review"])

    claims = {row.claim_id: row for row in researcher.claims}
    rebuttals = {row.objection_id: row for row in defender.rebuttals}
    findings = {row.objection_id: row for row in control.findings}

    for objection in critic.objections:
        finding = findings.get(objection.objection_id)
        if (
            objection.severity == "fatal"
            and objection.status == "verified"
            and finding is not None
            and finding.residual_status == "fatal"
            and finding.evidence_valid
            and _attested(finding.evidence_ids, evidence)
        ):
            return _decision(
                "REJECT",
                ledger_revision,
                ["verified_fatal_objection"],
                [objection.objection_id],
            )

    unresolved: list[str] = []
    reframed: list[str] = []
    accepted_evidence: set[str] = {
        evidence_id for claim in researcher.claims for evidence_id in claim.evidence_ids
    }
    for objection in critic.objections:
        claim = claims.get(objection.claim_id)
        is_critical = bool(claim and claim.critical) or objection.severity in {"critical", "fatal"}
        if not is_critical:
            continue
        rebuttal = rebuttals.get(objection.objection_id)
        finding = findings.get(objection.objection_id)
        if (
            rebuttal is None
            or finding is None
            or finding.residual_status != "resolved"
            or not finding.evidence_valid
            or not _attested(finding.evidence_ids, evidence)
        ):
            unresolved.append(objection.objection_id)
            continue
        if rebuttal.action == "ADD_EVIDENCE":
            prior_ids = set(objection.counterevidence_ids)
            if claim is not None:
                prior_ids.update(claim.evidence_ids)
            new_ids = set(rebuttal.evidence_ids) - prior_ids
            prior_origins = _origins(list(prior_ids), evidence)
            new_origins = _origins(list(new_ids), evidence)
            independent = bool(new_origins - prior_origins)
            if (
                not new_ids
                or not _attested(list(new_ids), evidence)
                or not finding.origin_independent
                or not independent
            ):
                unresolved.append(objection.objection_id)
                continue
            accepted_evidence.update(new_ids)
        elif rebuttal.action in {"CORRECT", "NARROW"}:
            replacement = rebuttal.replacement_claim
            if replacement is None or not _attested(replacement.evidence_ids, evidence):
                unresolved.append(objection.objection_id)
                continue
            accepted_evidence.update(replacement.evidence_ids)
            reframed.append(objection.objection_id)
        else:
            unresolved.append(objection.objection_id)

    if unresolved:
        return _decision(
            "HOLD", ledger_revision, ["unresolved_critical"], sorted(unresolved),
        )
    if reframed:
        return _decision(
            "REFRAME", ledger_revision, ["validated_narrower_claim"], sorted(reframed),
        )
    if any(claim.critical and claim.status == "unknown" for claim in researcher.claims):
        unknown = [claim.claim_id for claim in researcher.claims if claim.critical and claim.status == "unknown"]
        return _decision("HOLD", ledger_revision, ["critical_claim_unknown"], unknown)
    if (
        candidate.get("policy_action") != "RANK_ELIGIBLE"
        or candidate.get("label") != "weak_signal"
    ):
        return _decision("HOLD", ledger_revision, ["existing_policy_not_promotable"], ["base_policy"])
    if len(_origins(list(accepted_evidence), evidence)) < 2:
        return _decision("HOLD", ledger_revision, ["insufficient_origin_diversity"], ["origins"])
    return _decision("PROMOTE", ledger_revision, ["all_critical_objections_resolved"])
