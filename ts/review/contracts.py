"""Closed typed contracts for one bounded adversarial-review round."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RoleName = Literal["researcher", "critic", "defender", "control_critic"]
ClaimStatus = Literal["verified", "supported", "unknown"]
EvidenceId = str
_ID = r"^[a-z0-9][a-z0-9._:-]{0,63}$"


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceItem(StrictContract):
    evidence_id: str = Field(pattern=_ID)
    quote: str = Field(min_length=1, max_length=1500)
    url: str = Field(min_length=1, max_length=2048)
    provenance: Literal["preserved_primary", "preserved_non_primary", "snippet_only"]
    snapshot_ref: str | None
    origin_group_id: str | None


class ReviewClaim(StrictContract):
    claim_id: str = Field(pattern=_ID)
    statement: str = Field(min_length=1, max_length=1000)
    critical: bool
    evidence_ids: list[EvidenceId] = Field(min_length=1, max_length=12)
    status: ClaimStatus
    reason_codes: list[str] = Field(max_length=12)


class ResearcherOutput(StrictContract):
    claims: list[ReviewClaim] = Field(min_length=1, max_length=12)
    promotion_hypothesis: str = Field(min_length=1, max_length=1000)
    uncertainties: list[str] = Field(max_length=12)


class Objection(StrictContract):
    objection_id: str = Field(pattern=_ID)
    claim_id: str = Field(pattern=_ID)
    failure_mode: Literal[
        "false_novelty",
        "mass_adoption",
        "single_origin",
        "weak_provenance",
        "chronology_conflict",
        "unsupported_transition",
    ]
    counterevidence_ids: list[EvidenceId] = Field(max_length=12)
    severity: Literal["material", "critical", "fatal"]
    status: ClaimStatus
    statement: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def _cited_if_asserted(self) -> Objection:
        if self.status in {"verified", "supported"} and not self.counterevidence_ids:
            raise ValueError("verified or supported objection requires counterevidence")
        return self


class CriticOutput(StrictContract):
    objections: list[Objection] = Field(max_length=12)


class Rebuttal(StrictContract):
    rebuttal_id: str = Field(pattern=_ID)
    objection_id: str = Field(pattern=_ID)
    action: Literal["ADD_EVIDENCE", "CORRECT", "NARROW", "CONCEDE"]
    evidence_ids: list[EvidenceId] = Field(max_length=12)
    replacement_claim: ReviewClaim | None
    changed_fields: list[str] = Field(max_length=12)
    statement: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def _evidence_bearing_action(self) -> Rebuttal:
        if self.action == "CONCEDE":
            if self.evidence_ids or self.replacement_claim is not None or self.changed_fields:
                raise ValueError("CONCEDE cannot smuggle evidence or a replacement claim")
            return self
        if not self.evidence_ids:
            raise ValueError("defender action requires cited evidence")
        if self.action in {"CORRECT", "NARROW"}:
            if self.replacement_claim is None or not self.changed_fields:
                raise ValueError("corrected or narrowed claim and changed fields are required")
        elif self.replacement_claim is not None or self.changed_fields:
            raise ValueError("ADD_EVIDENCE cannot silently rewrite the claim")
        return self


class DefenderOutput(StrictContract):
    rebuttals: list[Rebuttal] = Field(max_length=12)


class ControlFinding(StrictContract):
    finding_id: str = Field(pattern=_ID)
    objection_id: str = Field(pattern=_ID)
    rebuttal_id: str | None
    evidence_ids: list[EvidenceId] = Field(max_length=12)
    evidence_valid: bool
    origin_independent: bool
    residual_status: Literal["resolved", "unresolved", "fatal"]
    statement: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def _valid_evidence_is_cited(self) -> ControlFinding:
        if self.evidence_valid and not self.evidence_ids:
            raise ValueError("validated control finding requires evidence citations")
        return self


class ControlOutput(StrictContract):
    findings: list[ControlFinding] = Field(max_length=12)


class ArbiterDecision(StrictContract):
    verdict: Literal["PROMOTE", "REFRAME", "HOLD", "REJECT"]
    rule_version: str = Field(pattern=_ID)
    ledger_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    blocking_ids: list[str] = Field(max_length=24)
    reason_codes: list[str] = Field(min_length=1, max_length=24)


_ROLE_MODELS = {
    "researcher": ResearcherOutput,
    "critic": CriticOutput,
    "defender": DefenderOutput,
    "control_critic": ControlOutput,
}


def role_schema(role: RoleName) -> dict:
    try:
        model = _ROLE_MODELS[role]
    except KeyError as exc:
        raise ValueError(f"unsupported review role: {role}") from exc
    return model.model_json_schema()


def parse_role_output(role: RoleName, payload: object) -> StrictContract:
    try:
        model = _ROLE_MODELS[role]
    except KeyError as exc:
        raise ValueError(f"unsupported review role: {role}") from exc
    return model.model_validate(payload)
