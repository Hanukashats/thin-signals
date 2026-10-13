"""One bounded researcher → critic → defender → control-critic round."""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Protocol

from pydantic import ValidationError

from ts.review.arbiter import arbitrate
from ts.review.contracts import (
    ArbiterDecision,
    ControlOutput,
    CriticOutput,
    DefenderOutput,
    EvidenceItem,
    ResearcherOutput,
    RoleName,
    StrictContract,
    parse_role_output,
    role_schema,
)
from ts.review.prompts import REVIEW_PROMPT_VERSION, build_messages, template_hash

REVIEW_CONTRACT_VERSION = "review-round-0.1"
_ROLES: tuple[RoleName, ...] = ("researcher", "critic", "defender", "control_critic")


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


@dataclass(frozen=True)
class RoleBudget:
    time_seconds: float
    max_output_tokens: int
    max_cost_usd: float
    evidence_limit: int

    def __post_init__(self):
        if (
            self.time_seconds <= 0
            or self.max_output_tokens <= 0
            or self.max_cost_usd <= 0
            or self.evidence_limit <= 0
        ):
            raise ValueError("review role budgets must be positive")

    def public(self) -> dict:
        return {
            "time_seconds": self.time_seconds,
            "max_output_tokens": self.max_output_tokens,
            "max_cost_usd": self.max_cost_usd,
            "evidence_limit": self.evidence_limit,
        }


@dataclass(frozen=True)
class ReviewModels:
    primary: str
    judge: str

    def for_role(self, role: RoleName) -> str:
        return self.primary if role in {"researcher", "defender"} else self.judge


@dataclass(frozen=True)
class RoleCallResult:
    payload: object
    model_id: str
    provider: str
    usage: dict
    latency_s: float
    cost_usd: float | None


class RoleGateway(Protocol):
    def call(
        self,
        role: RoleName,
        messages: list[dict[str, str]],
        schema: dict,
        budget: RoleBudget,
        model: str,
    ) -> RoleCallResult: ...


class EvidenceProvider(Protocol):
    def retrieve(
        self,
        role: RoleName,
        candidate: Mapping,
        budget: RoleBudget,
    ) -> Sequence[EvidenceItem]: ...


class OpenRouterRoleGateway:
    """Native strict-schema adapter; one HTTP request per role."""

    def __init__(self, client):
        self.client = client

    def call(self, role, messages, schema, budget, model) -> RoleCallResult:
        _ = role
        response = self.client.chat(
            messages,
            model,
            json_schema=schema,
            max_tokens=budget.max_output_tokens,
            temperature=0.0,
            reasoning=model.startswith("openai/"),
            require_parameters=True,
            timeout_seconds=budget.time_seconds,
        )
        usage = dict(response.usage or {})
        cost = usage.get("cost")
        return RoleCallResult(
            payload=response.json(),
            model_id=response.model_id,
            provider=response.provider,
            usage=usage,
            latency_s=response.latency_s,
            cost_usd=(
                float(cost)
                if isinstance(cost, (int, float)) and not isinstance(cost, bool)
                else None
            ),
        )


@dataclass(frozen=True)
class ReviewEventRecord:
    event_id: str
    sequence: int
    role: str
    state: str
    input_hash: str
    output_hash: str
    template_version: str
    template_hash: str
    model_id: str | None
    provider: str | None
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float | None
    evidence_ids: tuple[str, ...]
    budget: RoleBudget
    error_code: str | None
    payload: dict | None


@dataclass(frozen=True)
class ReviewRound:
    decision: ArbiterDecision
    events: tuple[ReviewEventRecord, ...]
    ledger_revision: str


def _candidate_view(candidate: Mapping) -> dict:
    return {
        key: candidate.get(key)
        for key in (
            "technology", "label", "confidence", "policy_action", "policy_reason",
            "reason_codes", "predictors",
        )
    }


def _typed_payload(value: StrictContract | None) -> dict | None:
    return value.model_dump(mode="json") if value is not None else None


def _blind_pairs(critic: CriticOutput | None, defender: DefenderOutput | None, run_id: str) -> list[dict]:
    objections = critic.objections if critic is not None else []
    rebuttals = {row.objection_id: row for row in (defender.rebuttals if defender is not None else [])}
    pairs = []
    for objection in objections:
        left = objection.model_dump(mode="json")
        rebuttal = rebuttals.get(objection.objection_id)
        right = rebuttal.model_dump(mode="json") if rebuttal is not None else None
        if int(_hash([run_id, objection.objection_id])[-1], 16) % 2:
            left, right = right, left
        pairs.append({
            "pair_id": _hash([run_id, objection.objection_id])[:16],
            "record_a": left,
            "record_b": right,
        })
    return pairs


def _input_payload(
    role: RoleName,
    candidate: Mapping,
    evidence: Sequence[EvidenceItem],
    outputs: Mapping[str, StrictContract | None],
    budget: RoleBudget,
    run_id: str,
) -> dict:
    body = {
        "contract_version": REVIEW_CONTRACT_VERSION,
        "candidate": _candidate_view(candidate),
        "evidence": [row.model_dump(mode="json") for row in evidence],
        "budget": budget.public(),
    }
    if role == "critic":
        body["claims"] = _typed_payload(outputs.get("researcher"))
    elif role == "defender":
        body["claims"] = _typed_payload(outputs.get("researcher"))
        body["objections"] = _typed_payload(outputs.get("critic"))
    elif role == "control_critic":
        body["paired_records"] = _blind_pairs(
            outputs.get("critic") if isinstance(outputs.get("critic"), CriticOutput) else None,
            outputs.get("defender") if isinstance(outputs.get("defender"), DefenderOutput) else None,
            run_id,
        )
    return body


def _duplicates(values: Sequence[str]) -> bool:
    return len(values) != len(set(values))


def _validate_references(
    role: RoleName,
    value: StrictContract,
    evidence: Mapping[str, EvidenceItem],
    outputs: Mapping[str, StrictContract | None],
) -> str | None:
    known = set(evidence)
    if role == "researcher":
        assert isinstance(value, ResearcherOutput)
        if _duplicates([row.claim_id for row in value.claims]):
            return "invalid_role_output"
        for claim in value.claims:
            if not set(claim.evidence_ids) <= known:
                return "invalid_citation"
            if claim.status == "verified" and not any(
                evidence[evidence_id].provenance == "preserved_primary"
                and evidence[evidence_id].snapshot_ref
                for evidence_id in claim.evidence_ids
            ):
                return "invalid_citation"
    elif role == "critic":
        assert isinstance(value, CriticOutput)
        researcher = outputs.get("researcher")
        claim_ids = {
            row.claim_id for row in researcher.claims
        } if isinstance(researcher, ResearcherOutput) else set()
        if _duplicates([row.objection_id for row in value.objections]):
            return "invalid_role_output"
        for objection in value.objections:
            if objection.claim_id not in claim_ids or not set(objection.counterevidence_ids) <= known:
                return "invalid_citation"
    elif role == "defender":
        assert isinstance(value, DefenderOutput)
        critic = outputs.get("critic")
        researcher = outputs.get("researcher")
        objection_by_id = {
            row.objection_id: row for row in critic.objections
        } if isinstance(critic, CriticOutput) else {}
        claim_by_id = {
            row.claim_id: row for row in researcher.claims
        } if isinstance(researcher, ResearcherOutput) else {}
        if (
            _duplicates([row.rebuttal_id for row in value.rebuttals])
            or _duplicates([row.objection_id for row in value.rebuttals])
        ):
            return "invalid_role_output"
        for rebuttal in value.rebuttals:
            objection = objection_by_id.get(rebuttal.objection_id)
            if objection is None or not set(rebuttal.evidence_ids) <= known:
                return "invalid_citation"
            if rebuttal.replacement_claim is not None and not set(
                rebuttal.replacement_claim.evidence_ids
            ) <= known:
                return "invalid_citation"
            if rebuttal.action == "ADD_EVIDENCE":
                prior = set(objection.counterevidence_ids)
                claim = claim_by_id.get(objection.claim_id)
                if claim is not None:
                    prior.update(claim.evidence_ids)
                if not set(rebuttal.evidence_ids) - prior:
                    return "defender_no_new_evidence"
    else:
        assert isinstance(value, ControlOutput)
        critic = outputs.get("critic")
        defender = outputs.get("defender")
        objections = {
            row.objection_id for row in critic.objections
        } if isinstance(critic, CriticOutput) else set()
        rebuttals = {
            row.rebuttal_id for row in defender.rebuttals
        } if isinstance(defender, DefenderOutput) else set()
        rebuttal_by_id = {
            row.rebuttal_id: row for row in defender.rebuttals
        } if isinstance(defender, DefenderOutput) else {}
        objection_by_id = {
            row.objection_id: row for row in critic.objections
        } if isinstance(critic, CriticOutput) else {}
        if (
            _duplicates([row.finding_id for row in value.findings])
            or _duplicates([row.objection_id for row in value.findings])
        ):
            return "invalid_role_output"
        for finding in value.findings:
            rebuttal = rebuttal_by_id.get(finding.rebuttal_id or "")
            objection = objection_by_id.get(finding.objection_id)
            traceable_evidence = set(objection.counterevidence_ids) if objection else set()
            if rebuttal is not None:
                traceable_evidence.update(rebuttal.evidence_ids)
                if rebuttal.replacement_claim is not None:
                    traceable_evidence.update(rebuttal.replacement_claim.evidence_ids)
            if (
                finding.objection_id not in objections
                or (finding.rebuttal_id is not None and finding.rebuttal_id not in rebuttals)
                or (rebuttal is not None and rebuttal.objection_id != finding.objection_id)
                or not set(finding.evidence_ids) <= known
                or not set(finding.evidence_ids) <= traceable_evidence
            ):
                return "invalid_citation"
    return None


def _usage_int(usage: Mapping, key: str) -> int:
    value = usage.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _nonnegative_float(value: object) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    converted = float(value)
    return converted if math.isfinite(converted) and converted >= 0 else None


def _event_id(run_id: str, sequence: int, role: str, input_hash: str, output_hash: str) -> str:
    return "review-" + _hash([run_id, sequence, role, input_hash, output_hash])[:40]


def run_review(
    *,
    run_id: str,
    candidate: Mapping,
    gateway: RoleGateway,
    evidence_provider: EvidenceProvider,
    budget: RoleBudget,
    models: ReviewModels,
) -> ReviewRound:
    outputs: dict[str, StrictContract | None] = {}
    evidence_by_id: dict[str, EvidenceItem] = {}
    events: list[ReviewEventRecord] = []
    failures: list[tuple[str, str]] = []

    for sequence, role in enumerate(_ROLES, start=1):
        started_at = datetime.now(UTC)
        started = monotonic()
        retrieved_error: str | None = None
        try:
            raw_rows = list(evidence_provider.retrieve(role, candidate, budget))[:budget.evidence_limit]
            rows = [EvidenceItem.model_validate(row) for row in raw_rows]
        except (TypeError, ValueError, ValidationError):
            rows = []
            retrieved_error = "evidence_provider_invalid"
        for row in rows:
            prior = evidence_by_id.get(row.evidence_id)
            if prior is not None and prior != row:
                retrieved_error = "evidence_identity_conflict"
                continue
            evidence_by_id[row.evidence_id] = row
        input_payload = _input_payload(role, candidate, rows, outputs, budget, run_id)
        input_hash = _hash(input_payload)
        raw_output: object = None
        parsed: StrictContract | None = None
        result: RoleCallResult | None = None
        state = "succeeded"
        error_code = retrieved_error
        try:
            candidate_result = gateway.call(
                role,
                build_messages(role, input_payload),
                role_schema(role),
                budget,
                models.for_role(role),
            )
            if not isinstance(candidate_result, RoleCallResult):
                raise TypeError("role gateway returned an invalid result")
            result = candidate_result
            raw_output = result.payload
            parsed = parse_role_output(role, raw_output)
        except TimeoutError:
            state, error_code = "timeout", "role_timeout"
        except (TypeError, ValueError, ValidationError, json.JSONDecodeError):
            state, error_code = "invalid", "invalid_role_output"
        except Exception:  # noqa: BLE001 - provider failures become typed HOLD events
            state, error_code = "failed", "role_call_failed"

        elapsed_s = monotonic() - started
        usage = result.usage if result is not None and isinstance(result.usage, Mapping) else {}
        claimed_latency = _nonnegative_float(result.latency_s) if result is not None else None
        if result is not None and claimed_latency is None and state == "succeeded":
            state, error_code, parsed = "invalid", "provider_metadata_invalid", None
        if claimed_latency is not None:
            elapsed_s = max(elapsed_s, claimed_latency)
        completion_tokens = _usage_int(usage, "completion_tokens")
        cost_usd = _nonnegative_float(result.cost_usd) if result is not None else None
        if state == "succeeded" and elapsed_s > budget.time_seconds:
            state, error_code, parsed = "timeout", "role_timeout", None
        if state == "succeeded" and (
            completion_tokens > budget.max_output_tokens
            or result is None
            or cost_usd is None
            or cost_usd > budget.max_cost_usd
        ):
            state, error_code, parsed = "budget_exceeded", "role_budget_exceeded", None
        if state == "succeeded" and parsed is not None:
            reference_error = _validate_references(role, parsed, evidence_by_id, outputs)
            if reference_error:
                state, error_code, parsed = "invalid", reference_error, None
        if retrieved_error and state == "succeeded":
            state, error_code, parsed = "invalid", retrieved_error, None
        outputs[role] = parsed
        if error_code:
            failures.append((role, error_code))

        output_hash = _hash(raw_output)
        finished_at = datetime.now(UTC)
        events.append(ReviewEventRecord(
            event_id=_event_id(run_id, sequence, role, input_hash, output_hash),
            sequence=sequence,
            role=role,
            state=state,
            input_hash=input_hash,
            output_hash=output_hash,
            template_version=REVIEW_PROMPT_VERSION,
            template_hash=template_hash(role),
            model_id=result.model_id if result else None,
            provider=result.provider if result else None,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=max(0, round(elapsed_s * 1000)),
            prompt_tokens=_usage_int(usage, "prompt_tokens"),
            completion_tokens=completion_tokens,
            total_tokens=_usage_int(usage, "total_tokens"),
            cost_usd=cost_usd,
            evidence_ids=tuple(row.evidence_id for row in rows),
            budget=budget,
            error_code=error_code,
            payload=_typed_payload(parsed),
        ))

    semantic_ledger = {
        "contract_version": REVIEW_CONTRACT_VERSION,
        "candidate": _candidate_view(candidate),
        "evidence": [
            evidence_by_id[key].model_dump(mode="json") for key in sorted(evidence_by_id)
        ],
        "outputs": {key: _typed_payload(outputs.get(key)) for key in _ROLES},
        "failures": failures,
    }
    ledger_revision = _hash(semantic_ledger)
    decision = arbitrate(
        candidate=candidate,
        researcher=(
            outputs.get("researcher")
            if isinstance(outputs.get("researcher"), ResearcherOutput) else None
        ),
        critic=outputs.get("critic") if isinstance(outputs.get("critic"), CriticOutput) else None,
        defender=(
            outputs.get("defender")
            if isinstance(outputs.get("defender"), DefenderOutput) else None
        ),
        control=(
            outputs.get("control_critic")
            if isinstance(outputs.get("control_critic"), ControlOutput) else None
        ),
        evidence=evidence_by_id,
        failures=failures,
        ledger_revision=ledger_revision,
    )
    arbiter_input_hash = _hash(semantic_ledger)
    arbiter_output = decision.model_dump(mode="json")
    arbiter_output_hash = _hash(arbiter_output)
    now = datetime.now(UTC)
    events.append(ReviewEventRecord(
        event_id=_event_id(run_id, 5, "arbiter", arbiter_input_hash, arbiter_output_hash),
        sequence=5,
        role="arbiter",
        state="succeeded",
        input_hash=arbiter_input_hash,
        output_hash=arbiter_output_hash,
        template_version=decision.rule_version,
        template_hash=_hash(decision.rule_version),
        model_id=None,
        provider=None,
        started_at=now,
        finished_at=now,
        duration_ms=0,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        cost_usd=0.0,
        evidence_ids=tuple(sorted(evidence_by_id)),
        budget=budget,
        error_code=None,
        payload=arbiter_output,
    ))
    return ReviewRound(decision=decision, events=tuple(events), ledger_revision=ledger_revision)
