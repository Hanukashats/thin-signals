"""One bounded researcher → critic → defender → control-critic round."""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Protocol

from pydantic import ValidationError

from ts.llm import MANDATORY_PROVIDER_POLICY
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

REVIEW_CONTRACT_VERSION = "review-round-0.2"
_ROLES: tuple[RoleName, ...] = ("researcher", "critic", "defender", "control_critic")
_MODEL_ID = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}"
    r"(?:/[A-Za-z0-9][A-Za-z0-9._:-]{0,95})?$",
)
_PROVIDER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def review_hash(value: object) -> str:
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
            not isinstance(self.time_seconds, (int, float))
            or isinstance(self.time_seconds, bool)
            or not math.isfinite(float(self.time_seconds))
            or self.time_seconds <= 0
            or not isinstance(self.max_output_tokens, int)
            or isinstance(self.max_output_tokens, bool)
            or self.max_output_tokens <= 0
            or not isinstance(self.max_cost_usd, (int, float))
            or isinstance(self.max_cost_usd, bool)
            or not math.isfinite(float(self.max_cost_usd))
            or self.max_cost_usd <= 0
            or not isinstance(self.evidence_limit, int)
            or isinstance(self.evidence_limit, bool)
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
    provider_policy: dict


class RoleGateway(Protocol):
    def call(
        self,
        role: RoleName,
        messages: list[dict[str, str]],
        schema: dict,
        budget: RoleBudget,
        model: str,
    ) -> RoleCallResult: ...

    def route_is_valid(
        self,
        requested_model: str,
        response_model: str,
        provider: str,
    ) -> bool: ...


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
        self._validated_routes: set[tuple[str, str, str]] = set()

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
        self._validated_routes.add((model, response.model_id, response.provider))
        usage = dict(response.usage or {})
        cost = usage.get("cost")
        try:
            payload = response.json()
        except (json.JSONDecodeError, TypeError, ValueError):
            # Preserve accounting and an opaque rejection hash even when the
            # provider returned malformed JSON. Raw text is never persisted.
            payload = response.content
        return RoleCallResult(
            payload=payload,
            model_id=response.model_id,
            provider=response.provider,
            usage=usage,
            latency_s=response.latency_s,
            cost_usd=(
                float(cost)
                if isinstance(cost, (int, float)) and not isinstance(cost, bool)
                else None
            ),
            provider_policy=dict(MANDATORY_PROVIDER_POLICY),
        )

    def route_is_valid(self, requested_model, response_model, provider) -> bool:
        return (requested_model, response_model, provider) in self._validated_routes


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
    provider_policy: dict
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cost_usd: float | None
    evidence_ids: tuple[str, ...]
    provenance: tuple[dict, ...]
    budget: RoleBudget
    error_code: str | None
    payload: dict | None


@dataclass(frozen=True)
class ReviewRound:
    run_id: str
    candidate_hash: str
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


def review_candidate_hash(candidate: Mapping) -> str:
    return review_hash(_candidate_view(candidate))


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
        if int(review_hash([run_id, objection.objection_id])[-1], 16) % 2:
            left, right = right, left
        pairs.append({
            "pair_id": review_hash([run_id, objection.objection_id])[:16],
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


def _allowed_references(
    evidence: Mapping[str, EvidenceItem],
    outputs: Mapping[str, StrictContract | None],
) -> dict[str, list[str]]:
    researcher = outputs.get("researcher")
    critic = outputs.get("critic")
    defender = outputs.get("defender")
    objection_by_id = {
        row.objection_id: row for row in critic.objections
    } if isinstance(critic, CriticOutput) else {}
    traceable_control_ids: set[str] = set()
    if isinstance(defender, DefenderOutput):
        for rebuttal in defender.rebuttals:
            objection = objection_by_id.get(rebuttal.objection_id)
            if objection is not None:
                traceable_control_ids.update(objection.counterevidence_ids)
            traceable_control_ids.update(rebuttal.evidence_ids)
            if rebuttal.replacement_claim is not None:
                traceable_control_ids.update(rebuttal.replacement_claim.evidence_ids)
    for objection in objection_by_id.values():
        traceable_control_ids.update(objection.counterevidence_ids)
    return {
        "evidence_ids": list(evidence),
        "claim_ids": (
            [row.claim_id for row in researcher.claims]
            if isinstance(researcher, ResearcherOutput) else []
        ),
        "objection_ids": (
            [row.objection_id for row in critic.objections]
            if isinstance(critic, CriticOutput) else []
        ),
        "rebuttal_ids": (
            [row.rebuttal_id for row in defender.rebuttals]
            if isinstance(defender, DefenderOutput) else []
        ),
        "control_evidence_ids": [
            evidence_id for evidence_id in evidence if evidence_id in traceable_control_ids
        ],
    }


def _reference_bindings(
    role: RoleName,
    evidence: Mapping[str, EvidenceItem],
    outputs: Mapping[str, StrictContract | None],
) -> list[dict]:
    """Expose exact cross-record citation relationships without trusting prose."""
    researcher = outputs.get("researcher")
    critic = outputs.get("critic")
    defender = outputs.get("defender")
    claim_by_id = {
        row.claim_id: row for row in researcher.claims
    } if isinstance(researcher, ResearcherOutput) else {}
    objection_by_id = {
        row.objection_id: row for row in critic.objections
    } if isinstance(critic, CriticOutput) else {}
    rebuttal_by_objection = {
        row.objection_id: row for row in defender.rebuttals
    } if isinstance(defender, DefenderOutput) else {}

    bindings = []
    for objection in objection_by_id.values():
        claim = claim_by_id.get(objection.claim_id)
        existing = set(objection.counterevidence_ids)
        if claim is not None:
            existing.update(claim.evidence_ids)
        if role == "defender":
            bindings.append({
                "objection_id": objection.objection_id,
                "claim_id": objection.claim_id,
                "existing_evidence_ids": [row for row in evidence if row in existing],
                "new_evidence_ids": [row for row in evidence if row not in existing],
            })
            continue
        if role != "control_critic":
            continue
        rebuttal = rebuttal_by_objection.get(objection.objection_id)
        traceable = set(objection.counterevidence_ids)
        required = set()
        if rebuttal is not None:
            traceable.update(rebuttal.evidence_ids)
            required.update(rebuttal.evidence_ids)
            if rebuttal.replacement_claim is not None:
                replacement_ids = rebuttal.replacement_claim.evidence_ids
                traceable.update(replacement_ids)
                required.update(replacement_ids)
        bindings.append({
            "objection_id": objection.objection_id,
            "rebuttal_id": rebuttal.rebuttal_id if rebuttal is not None else None,
            "allowed_evidence_ids": [row for row in evidence if row in traceable],
            "required_evidence_ids_if_resolved": [row for row in evidence if row in required],
        })
    return bindings


def _set_array_item_enum(schema: dict, definition: str, field: str, values: list[str]) -> None:
    if values:
        schema["$defs"][definition]["properties"][field]["items"]["enum"] = values


def _constrained_role_schema(role: RoleName, allowed: Mapping[str, list[str]]) -> dict:
    """Bind structured decoding to IDs actually present in this review round."""
    schema = role_schema(role)
    evidence_ids = list(allowed["evidence_ids"])
    claim_ids = list(allowed["claim_ids"])
    objection_ids = list(allowed["objection_ids"])
    rebuttal_ids = list(allowed["rebuttal_ids"])
    if role == "researcher":
        _set_array_item_enum(schema, "ReviewClaim", "evidence_ids", evidence_ids)
    elif role == "critic":
        objection = schema["$defs"]["Objection"]["properties"]
        if claim_ids:
            objection["claim_id"]["enum"] = claim_ids
        _set_array_item_enum(schema, "Objection", "counterevidence_ids", evidence_ids)
        if not claim_ids:
            schema["properties"]["objections"]["maxItems"] = 0
    elif role == "defender":
        rebuttal = schema["$defs"]["Rebuttal"]["properties"]
        if objection_ids:
            rebuttal["objection_id"]["enum"] = objection_ids
        _set_array_item_enum(schema, "Rebuttal", "evidence_ids", evidence_ids)
        _set_array_item_enum(schema, "ReviewClaim", "evidence_ids", evidence_ids)
        if not objection_ids:
            schema["properties"]["rebuttals"]["maxItems"] = 0
    else:
        finding = schema["$defs"]["ControlFinding"]["properties"]
        if objection_ids:
            finding["objection_id"]["enum"] = objection_ids
        _set_array_item_enum(
            schema,
            "ControlFinding",
            "evidence_ids",
            list(allowed.get("control_evidence_ids", evidence_ids)),
        )
        finding["rebuttal_id"]["anyOf"] = (
            [{"type": "string", "enum": rebuttal_ids}, {"type": "null"}]
            if rebuttal_ids else [{"type": "null"}]
        )
        if not objection_ids:
            schema["properties"]["findings"]["maxItems"] = 0
    return schema


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
        replacement_targets = []
        replacement_ids = []
        rebuttal_target_counts: dict[str, int] = {}
        for rebuttal in value.rebuttals:
            objection = objection_by_id.get(rebuttal.objection_id)
            if objection is not None:
                rebuttal_target_counts[objection.claim_id] = (
                    rebuttal_target_counts.get(objection.claim_id, 0) + 1
                )
            if rebuttal.action in {"CORRECT", "NARROW"} and objection is not None:
                replacement_targets.append(objection.claim_id)
                if rebuttal.replacement_claim is not None:
                    replacement_ids.append(rebuttal.replacement_claim.claim_id)
                    if (
                        rebuttal.replacement_claim.claim_id in claim_by_id
                        and rebuttal.replacement_claim.claim_id != objection.claim_id
                    ):
                        return "invalid_role_output"
        if (
            _duplicates(replacement_targets)
            or _duplicates(replacement_ids)
            or any(rebuttal_target_counts[target] > 1 for target in replacement_targets)
        ):
            # Objections are an unordered set. Multiple rewrites of one claim,
            # a rewrite mixed with another action, or two rewrites claiming one
            # effective identity are ambiguous within one review round.
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
            if finding.residual_status == "resolved":
                if rebuttal is None or finding.rebuttal_id != rebuttal.rebuttal_id:
                    return "invalid_citation"
                accepted_ids = set(rebuttal.evidence_ids)
                if rebuttal.replacement_claim is not None:
                    accepted_ids.update(rebuttal.replacement_claim.evidence_ids)
                if not accepted_ids <= set(finding.evidence_ids):
                    return "invalid_citation"
    return None


def _usage_int(usage: Mapping, key: str) -> int | None:
    value = usage.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _usage_is_valid(usage: object) -> bool:
    if not isinstance(usage, Mapping):
        return False
    values = [usage.get(key) for key in ("prompt_tokens", "completion_tokens", "total_tokens")]
    if not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in values):
        return False
    prompt_tokens, completion_tokens, total_tokens = values
    return total_tokens >= prompt_tokens + completion_tokens


def validated_model_id(value: object) -> str | None:
    """Return a compact route identifier, never URL/prose-shaped metadata."""
    return value if isinstance(value, str) and _MODEL_ID.fullmatch(value) else None


def validated_provider_id(value: object) -> str | None:
    """Return a compact provider identifier suitable for public attribution."""
    return value if isinstance(value, str) and _PROVIDER_ID.fullmatch(value) else None


def _public_provider_policy(value: object) -> dict:
    """Retain only the two policy fields that are safe and decision-relevant."""
    if not isinstance(value, Mapping):
        return {}
    public = {}
    if isinstance(value.get("zdr"), bool):
        public["zdr"] = value["zdr"]
    data_collection = value.get("data_collection")
    if isinstance(data_collection, str) and data_collection in {"allow", "deny"}:
        public["data_collection"] = data_collection
    return public


def _nonnegative_float(value: object) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    converted = float(value)
    return converted if math.isfinite(converted) and converted >= 0 else None


def review_event_id(
    run_id: str,
    sequence: int,
    role: str,
    input_hash: str,
    output_hash: str,
) -> str:
    return "review-" + review_hash([run_id, sequence, role, input_hash, output_hash])[:40]


def _provenance(rows: Sequence[EvidenceItem]) -> tuple[dict, ...]:
    return tuple({
        "evidence_id": row.evidence_id,
        "provenance": row.provenance,
        "snapshot_ref": row.snapshot_ref,
        "origin_group_id": row.origin_group_id,
        "url_hash": hashlib.sha256(row.url.encode()).hexdigest(),
    } for row in rows)


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
        except Exception:  # noqa: BLE001 - retrieval failures become typed HOLD events
            rows = []
            retrieved_error = "evidence_provider_invalid"
        unique_rows = []
        role_evidence_ids: set[str] = set()
        for row in rows:
            if row.evidence_id in role_evidence_ids:
                retrieved_error = "evidence_provider_invalid"
                continue
            role_evidence_ids.add(row.evidence_id)
            prior = evidence_by_id.get(row.evidence_id)
            if prior is not None and prior != row:
                retrieved_error = "evidence_identity_conflict"
                continue
            evidence_by_id[row.evidence_id] = row
            unique_rows.append(row)
        rows = unique_rows
        input_payload = _input_payload(role, candidate, rows, outputs, budget, run_id)
        allowed_references = _allowed_references(evidence_by_id, outputs)
        input_payload["allowed_references"] = allowed_references
        input_payload["reference_bindings"] = _reference_bindings(
            role,
            evidence_by_id,
            outputs,
        )
        input_payload["citation_rules"] = {
            "copy_ids_exactly": True,
            "never_invent_references": True,
            "verified_requires_preserved_primary_snapshot": True,
            "otherwise_use_supported_or_unknown": True,
        }
        input_hash = review_hash(input_payload)
        raw_output: object = None
        parsed: StrictContract | None = None
        result: RoleCallResult | None = None
        state = "succeeded"
        error_code = retrieved_error
        if retrieved_error is None:
            try:
                requested_model = models.for_role(role)
                candidate_result = gateway.call(
                    role,
                    build_messages(role, input_payload),
                    _constrained_role_schema(role, allowed_references),
                    budget,
                    requested_model,
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
        else:
            state, error_code = "invalid", retrieved_error

        elapsed_s = monotonic() - started
        usage = result.usage if result is not None and isinstance(result.usage, Mapping) else {}
        provider_policy = _public_provider_policy(
            result.provider_policy if result is not None else None,
        )
        model_id = validated_model_id(result.model_id) if result is not None else None
        provider = validated_provider_id(result.provider) if result is not None else None
        requested_model = models.for_role(role)
        route_valid = False
        if result is not None and model_id is not None and provider is not None:
            validator = getattr(gateway, "route_is_valid", None)
            if callable(validator):
                try:
                    route_valid = bool(validator(
                        requested_model,
                        model_id,
                        provider,
                    ))
                except Exception:  # noqa: BLE001 - route attestation fails closed
                    route_valid = False
        claimed_latency = _nonnegative_float(result.latency_s) if result is not None else None
        if result is not None and (
            claimed_latency is None
            or model_id is None
            or provider is None
            or model_id != requested_model
            or not route_valid
            or not _usage_is_valid(result.usage)
        ) and state == "succeeded":
            state, error_code, parsed = "invalid", "provider_metadata_invalid", None
        if result is not None and (
            not route_valid or model_id != requested_model
        ):
            model_id = None
            provider = None
        if (
            result is not None
            and (
                not isinstance(result.provider_policy, Mapping)
                or dict(result.provider_policy) != MANDATORY_PROVIDER_POLICY
                or provider_policy != MANDATORY_PROVIDER_POLICY
            )
            and state == "succeeded"
        ):
            state, error_code, parsed = "invalid", "provider_policy_invalid", None
        if claimed_latency is not None:
            elapsed_s = max(elapsed_s, claimed_latency)
        completion_tokens = _usage_int(usage, "completion_tokens")
        cost_usd = _nonnegative_float(result.cost_usd) if result is not None else None
        if state == "succeeded" and elapsed_s > budget.time_seconds:
            state, error_code, parsed = "timeout", "role_timeout", None
        if state == "succeeded" and (
            completion_tokens is None
            or completion_tokens > budget.max_output_tokens
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

        typed_payload = _typed_payload(parsed)
        output_hash = review_hash(typed_payload if state == "succeeded" else raw_output)
        finished_at = datetime.now(UTC)
        events.append(ReviewEventRecord(
            event_id=review_event_id(run_id, sequence, role, input_hash, output_hash),
            sequence=sequence,
            role=role,
            state=state,
            input_hash=input_hash,
            output_hash=output_hash,
            template_version=REVIEW_PROMPT_VERSION,
            template_hash=template_hash(role),
            model_id=model_id,
            provider=provider,
            provider_policy=provider_policy,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=max(0, round(elapsed_s * 1000)),
            prompt_tokens=_usage_int(usage, "prompt_tokens"),
            completion_tokens=completion_tokens,
            total_tokens=_usage_int(usage, "total_tokens"),
            cost_usd=cost_usd,
            evidence_ids=tuple(row.evidence_id for row in rows),
            provenance=_provenance(rows),
            budget=budget,
            error_code=error_code,
            payload=typed_payload,
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
    ledger_revision = review_hash(semantic_ledger)
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
    arbiter_input_hash = review_hash(semantic_ledger)
    arbiter_output = decision.model_dump(mode="json")
    arbiter_output_hash = review_hash(arbiter_output)
    now = datetime.now(UTC)
    events.append(ReviewEventRecord(
        event_id=review_event_id(run_id, 5, "arbiter", arbiter_input_hash, arbiter_output_hash),
        sequence=5,
        role="arbiter",
        state="succeeded",
        input_hash=arbiter_input_hash,
        output_hash=arbiter_output_hash,
        template_version=decision.rule_version,
        template_hash=review_hash(decision.rule_version),
        model_id=None,
        provider=None,
        provider_policy={},
        started_at=now,
        finished_at=now,
        duration_ms=0,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        cost_usd=0.0,
        evidence_ids=tuple(sorted(evidence_by_id)),
        provenance=_provenance([evidence_by_id[key] for key in sorted(evidence_by_id)]),
        budget=budget,
        error_code=None,
        payload=arbiter_output,
    ))
    return ReviewRound(
        run_id=run_id,
        candidate_hash=review_candidate_hash(candidate),
        decision=decision,
        events=tuple(events),
        ledger_revision=ledger_revision,
    )
