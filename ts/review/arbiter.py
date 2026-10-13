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

ARBITER_RULE_VERSION = "review-arbiter-0.2"


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

    critical_claims = {
        claim.claim_id: claim for claim in researcher.claims if claim.critical
    }
    unresolved: list[str] = []
    reframed: list[str] = []
    accepted_by_claim: dict[str, set[str]] = {
        claim_id: set(claim.evidence_ids)
        for claim_id, claim in (critical_claims or claims).items()
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
            or finding.rebuttal_id != rebuttal.rebuttal_id
            or not set(rebuttal.evidence_ids) <= set(finding.evidence_ids)
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
            if claim is not None and claim.claim_id in accepted_by_claim:
                accepted_by_claim[claim.claim_id].update(new_ids)
        elif rebuttal.action in {"CORRECT", "NARROW"}:
            replacement = rebuttal.replacement_claim
            if (
                replacement is None
                or replacement.status == "unknown"
                or not replacement.critical
                or not set(replacement.evidence_ids) <= set(finding.evidence_ids)
                or not _attested(replacement.evidence_ids, evidence)
            ):
                unresolved.append(objection.objection_id)
                continue
            if claim is not None and claim.claim_id in accepted_by_claim:
                # CORRECT/NARROW replaces the effective claim. Evidence cited only
                # by the superseded claim cannot satisfy the replacement's gate.
                accepted_by_claim[claim.claim_id] = set(replacement.evidence_ids)
            reframed.append(objection.objection_id)
        else:
            unresolved.append(objection.objection_id)

    if unresolved:
        return _decision(
            "HOLD", ledger_revision, ["unresolved_critical"], sorted(unresolved),
        )
    if any(claim.critical and claim.status == "unknown" for claim in researcher.claims):
        unknown = [claim.claim_id for claim in researcher.claims if claim.critical and claim.status == "unknown"]
        return _decision("HOLD", ledger_revision, ["critical_claim_unknown"], unknown)
    unattested_claims = [
        claim_id for claim_id, evidence_ids in accepted_by_claim.items()
        if not any(_attested([evidence_id], evidence) for evidence_id in evidence_ids)
    ]
    if unattested_claims:
        return _decision(
            "HOLD", ledger_revision, ["critical_claim_unattested"], sorted(unattested_claims),
        )
    accepted_evidence = {
        evidence_id
        for evidence_ids in accepted_by_claim.values()
        for evidence_id in evidence_ids
    }
    attested_evidence = [
        evidence_id for evidence_id in accepted_evidence
        if _attested([evidence_id], evidence)
    ]
    if len(_origins(attested_evidence, evidence)) < 2:
        return _decision("HOLD", ledger_revision, ["insufficient_origin_diversity"], ["origins"])
    if reframed:
        return _decision(
            "REFRAME", ledger_revision, ["validated_narrower_claim"], sorted(reframed),
        )
    if (
        candidate.get("policy_action") != "RANK_ELIGIBLE"
        or candidate.get("label") != "weak_signal"
    ):
        return _decision("HOLD", ledger_revision, ["existing_policy_not_promotable"], ["base_policy"])
    return _decision("PROMOTE", ledger_revision, ["all_critical_objections_resolved"])
