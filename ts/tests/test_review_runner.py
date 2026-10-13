"""One bounded role round and deterministic fail-closed arbitration."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from ts.llm import MANDATORY_PROVIDER_POLICY
from ts.review.arbiter import arbitrate
from ts.review.contracts import (
    ControlOutput,
    CriticOutput,
    DefenderOutput,
    EvidenceItem,
    ResearcherOutput,
)
from ts.review.runner import (
    OpenRouterRoleGateway,
    ReviewModels,
    RoleBudget,
    RoleCallResult,
    run_review,
)


def evidence(evidence_id: str, origin: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        quote=f"Attested primary text for {evidence_id}.",
        url=f"https://arxiv.org/abs/{evidence_id}",
        provenance="preserved_primary",
        snapshot_ref="sha256:" + evidence_id[-1] * 64,
        origin_group_id=origin,
    )


EVIDENCE = [
    evidence("evidence-1", "ror:origin-a"),
    evidence("evidence-2", "ror:origin-c"),
    evidence("evidence-3", "ror:origin-b"),
]

CANDIDATE = {
    "technology": "Novel cell mechanism",
    "label": "weak_signal",
    "confidence": 0.72,
    "policy_action": "RANK_ELIGIBLE",
    "policy_reason": "evidence_gates_passed",
    "reason_codes": ["P01"],
    "predictors": [{"code": "P01", "value": "verified"}],
}


def outputs():
    return {
        "researcher": {
            "claims": [{
                "claim_id": "claim-1",
                "statement": "The primary experiment reports a novel cell mechanism.",
                "critical": True,
                "evidence_ids": ["evidence-1"],
                "status": "verified",
                "reason_codes": ["P01"],
            }],
            "promotion_hypothesis": "The mechanism is a qualified weak signal.",
            "uncertainties": ["Independent deployment remains unverified."],
        },
        "critic": {
            "objections": [{
                "objection_id": "objection-1",
                "claim_id": "claim-1",
                "failure_mode": "single_origin",
                "counterevidence_ids": ["evidence-2"],
                "severity": "critical",
                "status": "supported",
                "statement": "The original claim has only one origin.",
            }],
        },
        "defender": {
            "rebuttals": [{
                "rebuttal_id": "rebuttal-1",
                "objection_id": "objection-1",
                "action": "ADD_EVIDENCE",
                "evidence_ids": ["evidence-3"],
                "replacement_claim": None,
                "changed_fields": [],
                "statement": "A second origin independently reports the mechanism.",
            }],
        },
        "control_critic": {
            "findings": [{
                "finding_id": "control-1",
                "objection_id": "objection-1",
                "rebuttal_id": "rebuttal-1",
                "evidence_ids": ["evidence-3"],
                "evidence_valid": True,
                "origin_independent": True,
                "residual_status": "resolved",
                "statement": "The second attested origin resolves the objection.",
            }],
        },
    }


class Provider:
    def __init__(self, rows=EVIDENCE):
        self.rows = rows
        self.calls = []

    def retrieve(self, role, candidate, budget):
        self.calls.append((role, candidate["technology"], budget))
        return list(self.rows)


class Gateway:
    def __init__(self, scripted=None, *, role_costs=None, role_tokens=None, role_latency=None):
        self.scripted = scripted or outputs()
        self.role_costs = role_costs or {}
        self.role_tokens = role_tokens or {}
        self.role_latency = role_latency or {}
        self.calls = []

    def call(self, role, messages, schema, budget, model):
        self.calls.append((role, messages, schema, budget, model))
        return RoleCallResult(
            payload=self.scripted[role],
            model_id=model,
            provider="FixtureZDR",
            usage={
                "prompt_tokens": 100,
                "completion_tokens": self.role_tokens.get(role, 100),
                "total_tokens": 200,
            },
            latency_s=self.role_latency.get(role, 0.01),
            cost_usd=self.role_costs.get(role, 0.001),
            provider_policy=dict(MANDATORY_PROVIDER_POLICY),
        )

    def route_is_valid(self, requested_model, response_model, provider):
        return requested_model == response_model and provider == "FixtureZDR"


def review(gateway=None, provider=None, budget=None):
    return run_review(
        run_id="run-1",
        candidate=CANDIDATE,
        gateway=gateway or Gateway(),
        evidence_provider=provider or Provider(),
        budget=budget or RoleBudget(
            time_seconds=5,
            max_output_tokens=500,
            max_cost_usd=0.02,
            evidence_limit=3,
        ),
        models=ReviewModels(primary="model-primary", judge="model-judge"),
    )


def test_one_equal_budget_call_per_role_and_valid_evidence_can_promote():
    gateway, provider = Gateway(), Provider()
    result = review(gateway, provider)

    assert [call[0] for call in gateway.calls] == [
        "researcher", "critic", "defender", "control_critic",
    ]
    assert [call[0] for call in provider.calls] == [
        "researcher", "critic", "defender", "control_critic",
    ]
    assert len({call[3] for call in gateway.calls}) == 1
    assert len({call[2] for call in provider.calls}) == 1
    assert [call[4] for call in gateway.calls] == [
        "model-primary", "model-judge", "model-primary", "model-judge",
    ]
    assert result.decision.verdict == "PROMOTE"
    assert result.decision.rule_version == "review-arbiter-0.2"
    assert [event.role for event in result.events] == [
        "researcher", "critic", "defender", "control_critic", "arbiter",
    ]
    assert all(event.state == "succeeded" for event in result.events)


def test_gateway_attestation_cannot_override_requested_model_equality():
    class WrongApprovedModelGateway(Gateway):
        def call(self, role, messages, schema, budget, model):
            return replace(
                super().call(role, messages, schema, budget, model),
                model_id="other-approved-model",
            )

        def route_is_valid(self, *_args):
            return True

    result = review(WrongApprovedModelGateway())

    assert result.decision.verdict == "HOLD"
    assert all(event.error_code == "provider_metadata_invalid" for event in result.events[:4])
    assert all(event.model_id is None and event.provider is None for event in result.events[:4])


def test_native_gateway_wrong_approved_model_is_sanitized_and_holds():
    scripted = iter(outputs().values())

    class Response:
        model_id = "other-approved-model"
        provider = "FixtureZDR"
        latency_s = 0.01

        def __init__(self, payload):
            self._payload = payload
            self.usage = {
                "prompt_tokens": 100,
                "completion_tokens": 100,
                "total_tokens": 200,
                "cost": 0.001,
            }

        def json(self):
            return self._payload

    class Client:
        def chat(self, *_args, **_kwargs):
            return Response(next(scripted))

    result = review(OpenRouterRoleGateway(Client()))

    assert result.decision.verdict == "HOLD"
    assert all(event.error_code == "provider_metadata_invalid" for event in result.events[:4])
    assert all(event.model_id is None and event.provider is None for event in result.events[:4])


def test_unknown_evidence_reference_fails_closed_but_all_roles_still_run_once():
    scripted = outputs()
    scripted["researcher"]["claims"][0]["evidence_ids"] = ["evidence-unknown"]
    gateway = Gateway(scripted)

    result = review(gateway)

    assert result.decision.verdict == "HOLD"
    assert "invalid_citation" in result.decision.reason_codes
    assert len(gateway.calls) == 4
    assert result.events[0].state == "invalid"


def test_supported_claims_with_only_non_primary_evidence_cannot_promote():
    scripted = outputs()
    scripted["researcher"]["claims"][0].update({
        "evidence_ids": ["evidence-1", "evidence-2"],
        "status": "supported",
    })
    scripted["critic"]["objections"] = []
    scripted["defender"]["rebuttals"] = []
    scripted["control_critic"]["findings"] = []
    rows = [
        row.model_copy(update={"provenance": "preserved_non_primary"})
        for row in EVIDENCE[:2]
    ]

    result = review(Gateway(scripted), Provider(rows))

    assert all(event.state == "succeeded" for event in result.events)
    assert result.decision.verdict == "HOLD"
    assert result.decision.reason_codes == ["critical_claim_unattested"]


def test_unrelated_primary_claims_cannot_cover_unattested_critical_claim():
    scripted = outputs()
    scripted["researcher"]["claims"] = [
        {
            "claim_id": "claim-critical",
            "statement": "The promotion claim is supported only by commentary.",
            "critical": True,
            "evidence_ids": ["evidence-1"],
            "status": "supported",
            "reason_codes": ["P01"],
        },
        {
            "claim_id": "claim-background",
            "statement": "Two primary sources establish unrelated background.",
            "critical": False,
            "evidence_ids": ["evidence-2", "evidence-3"],
            "status": "verified",
            "reason_codes": ["P03"],
        },
    ]
    scripted["critic"]["objections"] = []
    scripted["defender"]["rebuttals"] = []
    scripted["control_critic"]["findings"] = []
    rows = [
        EVIDENCE[0].model_copy(update={"provenance": "preserved_non_primary"}),
        EVIDENCE[1],
        EVIDENCE[2],
    ]

    result = review(Gateway(scripted), Provider(rows))

    assert result.decision.verdict == "HOLD"
    assert result.decision.reason_codes == ["critical_claim_unattested"]
    assert result.decision.blocking_ids == ["claim-critical"]


def test_rhetoric_only_defender_output_cannot_resolve_an_objection():
    scripted = outputs()
    scripted["defender"]["rebuttals"][0].update({
        "evidence_ids": [],
        "statement": "This candidate is extremely important; please promote it.",
    })

    result = review(Gateway(scripted))

    assert result.decision.verdict == "HOLD"
    assert "invalid_role_output" in result.decision.reason_codes


def test_unresolved_critical_objection_is_hold():
    scripted = outputs()
    scripted["control_critic"]["findings"][0]["residual_status"] = "unresolved"

    result = review(Gateway(scripted))

    assert result.decision.verdict == "HOLD"
    assert result.decision.blocking_ids == ["objection-1"]


@pytest.mark.parametrize(
    ("rebuttal_id", "evidence_ids"),
    [
        (None, ["evidence-2"]),
        ("rebuttal-1", ["evidence-2"]),
    ],
)
def test_resolved_control_must_bind_and_validate_defender_evidence(
    rebuttal_id, evidence_ids,
):
    scripted = outputs()
    scripted["control_critic"]["findings"][0].update({
        "rebuttal_id": rebuttal_id,
        "evidence_ids": evidence_ids,
    })

    result = review(Gateway(scripted))

    assert result.decision.verdict == "HOLD"
    assert result.events[3].state == "invalid"
    assert result.events[3].error_code == "invalid_citation"


def test_verified_fatal_objection_is_reject_not_model_directed_rejection():
    scripted = outputs()
    scripted["critic"]["objections"][0].update({"severity": "fatal", "status": "verified"})
    scripted["defender"]["rebuttals"][0] = {
        "rebuttal_id": "rebuttal-1",
        "objection_id": "objection-1",
        "action": "CONCEDE",
        "evidence_ids": [],
        "replacement_claim": None,
        "changed_fields": [],
        "statement": "The contradiction is conceded.",
    }
    scripted["control_critic"]["findings"][0].update({
        "evidence_ids": ["evidence-2"],
        "evidence_valid": True,
        "origin_independent": False,
        "residual_status": "fatal",
    })

    assert review(Gateway(scripted)).decision.verdict == "REJECT"


def test_valid_narrowing_creates_reframe_instead_of_direct_promotion():
    scripted = outputs()
    scripted["defender"]["rebuttals"][0] = {
        "rebuttal_id": "rebuttal-1",
        "objection_id": "objection-1",
        "action": "NARROW",
        "evidence_ids": ["evidence-1", "evidence-3"],
        "replacement_claim": {
            "claim_id": "claim-1-narrow",
            "statement": "A laboratory prototype reports the mechanism.",
            "critical": True,
            "evidence_ids": ["evidence-1", "evidence-3"],
            "status": "verified",
            "reason_codes": ["P01"],
        },
        "changed_fields": ["statement", "scope", "evidence_ids"],
        "statement": "Deployment language is removed.",
    }
    scripted["control_critic"]["findings"][0]["evidence_ids"] = [
        "evidence-1", "evidence-3",
    ]

    assert review(Gateway(scripted)).decision.verdict == "REFRAME"


@pytest.mark.parametrize("action", ["NARROW", "CORRECT"])
def test_reframe_does_not_inherit_superseded_claim_evidence(action):
    scripted = outputs()
    scripted["defender"]["rebuttals"][0] = {
        "rebuttal_id": "rebuttal-1",
        "objection_id": "objection-1",
        "action": action,
        "evidence_ids": ["evidence-3"],
        "replacement_claim": {
            "claim_id": f"claim-1-{action.lower()}",
            "statement": "A laboratory prototype reports the mechanism.",
            "critical": True,
            "evidence_ids": ["evidence-3"],
            "status": "verified",
            "reason_codes": ["P01"],
        },
        "changed_fields": ["statement", "scope", "evidence_ids"],
        "statement": "Deployment language and the old citation are removed.",
    }

    result = review(Gateway(scripted))

    assert result.decision.verdict == "HOLD"
    assert result.decision.reason_codes == ["insufficient_origin_diversity"]


def test_multiple_replacements_for_the_same_claim_fail_closed():
    scripted = outputs()
    scripted["critic"]["objections"].append({
        "objection_id": "objection-2",
        "claim_id": "claim-1",
        "failure_mode": "unsupported_transition",
        "counterevidence_ids": ["evidence-2"],
        "severity": "critical",
        "status": "supported",
        "statement": "The deployment scope also needs correction.",
    })
    scripted["defender"]["rebuttals"] = [
        {
            "rebuttal_id": f"rebuttal-{index}",
            "objection_id": f"objection-{index}",
            "action": "NARROW",
            "evidence_ids": ["evidence-1", "evidence-3"],
            "replacement_claim": {
                "claim_id": f"claim-1-narrow-{index}",
                "statement": statement,
                "critical": True,
                "evidence_ids": ["evidence-1", "evidence-3"],
                "status": "verified",
                "reason_codes": ["P01"],
            },
            "changed_fields": ["statement", "scope", "evidence_ids"],
            "statement": "The original claim is replaced.",
        }
        for index, statement in enumerate((
            "Only a laboratory prototype is supported.",
            "Only a field prototype is supported.",
        ), start=1)
    ]
    scripted["control_critic"]["findings"] = [
        {
            "finding_id": f"control-{index}",
            "objection_id": f"objection-{index}",
            "rebuttal_id": f"rebuttal-{index}",
            "evidence_ids": ["evidence-1", "evidence-3"],
            "evidence_valid": True,
            "origin_independent": True,
            "residual_status": "resolved",
            "statement": "The replacement is attested.",
        }
        for index in (1, 2)
    ]

    result = review(Gateway(scripted))

    assert result.decision.verdict == "HOLD"
    defender_event = next(event for event in result.events if event.role == "defender")
    assert defender_event.state == "invalid"
    assert defender_event.error_code == "invalid_role_output"


@pytest.mark.parametrize("action", ["NARROW", "CORRECT"])
@pytest.mark.parametrize("critic_reverse", [False, True])
@pytest.mark.parametrize("defender_reverse", [False, True])
def test_replacement_mixed_with_add_evidence_is_order_independent_hold(
    action, critic_reverse, defender_reverse,
):
    scripted = outputs()
    scripted["defender"]["rebuttals"][0] = {
        "rebuttal_id": "rebuttal-1",
        "objection_id": "objection-1",
        "action": action,
        "evidence_ids": ["evidence-3"],
        "replacement_claim": {
            "claim_id": f"claim-1-{action.lower()}",
            "statement": "Only a laboratory prototype is supported.",
            "critical": True,
            "evidence_ids": ["evidence-3"],
            "status": "verified",
            "reason_codes": ["P01"],
        },
        "changed_fields": ["statement", "scope", "evidence_ids"],
        "statement": "The original claim is replaced.",
    }
    scripted["critic"]["objections"].append({
        "objection_id": "objection-2",
        "claim_id": "claim-1",
        "failure_mode": "unsupported_transition",
        "counterevidence_ids": ["evidence-2"],
        "severity": "critical",
        "status": "supported",
        "statement": "A second objection requests independent evidence.",
    })
    scripted["defender"]["rebuttals"].append({
        "rebuttal_id": "rebuttal-2",
        "objection_id": "objection-2",
        "action": "ADD_EVIDENCE",
        "evidence_ids": ["evidence-4"],
        "replacement_claim": None,
        "changed_fields": [],
        "statement": "A new independent origin is added.",
    })
    scripted["control_critic"]["findings"].append({
        "finding_id": "control-2",
        "objection_id": "objection-2",
        "rebuttal_id": "rebuttal-2",
        "evidence_ids": ["evidence-4"],
        "evidence_valid": True,
        "origin_independent": True,
        "residual_status": "resolved",
        "statement": "The additional evidence is attested.",
    })
    if critic_reverse:
        scripted["critic"]["objections"].reverse()
    if defender_reverse:
        scripted["defender"]["rebuttals"].reverse()
    rows = [*EVIDENCE, evidence("evidence-4", "ror:origin-d")]
    budget = RoleBudget(
        time_seconds=5,
        max_output_tokens=500,
        max_cost_usd=0.02,
        evidence_limit=4,
    )

    result = review(Gateway(scripted), Provider(rows), budget)

    assert result.decision.verdict == "HOLD"
    defender_event = next(event for event in result.events if event.role == "defender")
    assert defender_event.state == "invalid"
    assert defender_event.error_code == "invalid_role_output"

    direct = arbitrate(
        candidate=CANDIDATE,
        researcher=ResearcherOutput.model_validate(scripted["researcher"]),
        critic=CriticOutput.model_validate(scripted["critic"]),
        defender=DefenderOutput.model_validate(scripted["defender"]),
        control=ControlOutput.model_validate(scripted["control_critic"]),
        evidence={row.evidence_id: row for row in rows},
        failures=[],
        ledger_revision="0" * 64,
    )
    assert direct.verdict == "HOLD"
    assert direct.reason_codes == ["ambiguous_claim_rewrite"]


@pytest.mark.parametrize(
    ("field", "value"),
    [("status", "unknown"), ("critical", False)],
)
def test_reframe_requires_a_resolved_critical_replacement(field, value):
    scripted = outputs()
    replacement = {
        "claim_id": "claim-1-narrow",
        "statement": "A laboratory prototype reports the mechanism.",
        "critical": True,
        "evidence_ids": ["evidence-3"],
        "status": "verified",
        "reason_codes": ["P01"],
    }
    replacement[field] = value
    scripted["defender"]["rebuttals"][0] = {
        "rebuttal_id": "rebuttal-1",
        "objection_id": "objection-1",
        "action": "NARROW",
        "evidence_ids": ["evidence-3"],
        "replacement_claim": replacement,
        "changed_fields": ["statement", "scope"],
        "statement": "Deployment language is removed.",
    }

    result = review(Gateway(scripted))

    assert result.decision.verdict == "HOLD"
    assert result.decision.reason_codes == ["unresolved_critical"]


def test_reframe_cannot_hide_another_unknown_critical_claim():
    scripted = outputs()
    scripted["researcher"]["claims"].append({
        "claim_id": "claim-2",
        "statement": "A second critical deployment claim remains unknown.",
        "critical": True,
        "evidence_ids": ["evidence-2"],
        "status": "unknown",
        "reason_codes": ["P03"],
    })
    scripted["defender"]["rebuttals"][0] = {
        "rebuttal_id": "rebuttal-1",
        "objection_id": "objection-1",
        "action": "NARROW",
        "evidence_ids": ["evidence-3"],
        "replacement_claim": {
            "claim_id": "claim-1-narrow",
            "statement": "A laboratory prototype reports the mechanism.",
            "critical": True,
            "evidence_ids": ["evidence-3"],
            "status": "verified",
            "reason_codes": ["P01"],
        },
        "changed_fields": ["statement", "scope"],
        "statement": "Deployment language is removed.",
    }

    result = review(Gateway(scripted))

    assert result.decision.verdict == "HOLD"
    assert result.decision.reason_codes == ["critical_claim_unknown"]
    assert result.decision.blocking_ids == ["claim-2"]


def test_time_token_and_cost_overruns_each_hold():
    budget = RoleBudget(
        time_seconds=0.1,
        max_output_tokens=50,
        max_cost_usd=0.01,
        evidence_limit=3,
    )
    cases = [
        Gateway(role_latency={"critic": 0.2}),
        Gateway(role_tokens={"critic": 51}),
        Gateway(role_costs={"critic": 0.011}),
    ]
    expected_states = ["timeout", "budget_exceeded", "budget_exceeded"]
    for gateway, state in zip(cases, expected_states, strict=True):
        result = review(gateway, budget=budget)
        assert result.decision.verdict == "HOLD"
        assert result.events[1].state == state
        assert len(gateway.calls) == 4


def test_replay_has_the_same_semantic_ledger_revision_and_verdict():
    first = review()
    second = review()

    assert first.decision == second.decision
    assert first.ledger_revision == second.ledger_revision
    assert [event.input_hash for event in first.events] == [
        event.input_hash for event in second.events
    ]


def test_evidence_provider_is_hard_capped_even_if_it_returns_more():
    provider = Provider(EVIDENCE + [evidence("evidence-4", "ror:origin-d")])
    result = review(provider=provider)

    assert all(len(event.evidence_ids) <= 3 for event in result.events[:-1])
    assert result.decision.verdict == "PROMOTE"


def test_openrouter_gateway_passes_schema_token_and_transport_caps():
    seen = {}

    class Response:
        model_id = "model-primary"
        provider = "FixtureZDR"
        latency_s = 0.01

        def __init__(self):
            self.usage = {"completion_tokens": 10, "cost": 0.002}

        def json(self):
            return outputs()["researcher"]

    class Client:
        def chat(self, messages, model, **options):
            seen.update({"messages": messages, "model": model, **options})
            return Response()

    budget = RoleBudget(3.5, 321, 0.02, 3)
    result = OpenRouterRoleGateway(Client()).call(
        "researcher", [{"role": "user", "content": "data"}], {"type": "object"},
        budget, "model-primary",
    )

    assert result.cost_usd == 0.002
    assert result.provider_policy == MANDATORY_PROVIDER_POLICY
    assert seen["max_tokens"] == 321
    assert seen["timeout_seconds"] == 3.5
    assert seen["json_schema"] == {"type": "object"}
    assert seen["require_parameters"] is True


def test_openrouter_gateway_retains_accounting_when_json_is_malformed():
    class Response:
        model_id = "model-primary"
        provider = "FixtureZDR"
        latency_s = 0.02
        content = '{"claims":'

        def __init__(self):
            self.usage = {
                "prompt_tokens": 7,
                "completion_tokens": 3,
                "total_tokens": 10,
                "cost": 0.004,
            }

        def json(self):
            return json.loads(self.content)

    class Client:
        def chat(self, *_args, **_options):
            return Response()

    result = OpenRouterRoleGateway(Client()).call(
        "researcher", [], {"type": "object"}, RoleBudget(3.5, 321, 0.02, 3),
        "model-primary",
    )

    assert result.payload == Response.content
    assert result.model_id == "model-primary"
    assert result.provider == "FixtureZDR"
    assert result.usage["total_tokens"] == 10
    assert result.cost_usd == 0.004


def test_malformed_role_json_holds_but_retains_route_usage_cost_and_unique_hashes():
    class Response:
        provider = "FixtureZDR"
        latency_s = 0.02

        def __init__(self, model, index):
            self.model_id = model
            self.content = f'{{"malformed":{index}'
            self.usage = {
                "prompt_tokens": 7,
                "completion_tokens": 3,
                "total_tokens": 10,
                "cost": 0.004,
            }

        def json(self):
            return json.loads(self.content)

    class Client:
        calls = 0

        def chat(self, _messages, model, **_options):
            self.calls += 1
            return Response(model, self.calls)

    result = review(OpenRouterRoleGateway(Client()))
    model_events = result.events[:4]

    assert result.decision.verdict == "HOLD"
    assert all(event.state == "invalid" for event in model_events)
    assert all(event.error_code == "invalid_role_output" for event in model_events)
    assert all(event.provider == "FixtureZDR" for event in model_events)
    assert all(event.total_tokens == 10 and event.cost_usd == 0.004 for event in model_events)
    assert all(event.payload is None for event in model_events)
    assert len({event.output_hash for event in model_events}) == 4


def test_control_cannot_resolve_with_evidence_outside_its_typed_pair():
    scripted = outputs()
    scripted["control_critic"]["findings"][0]["evidence_ids"] = ["evidence-1"]

    result = review(Gateway(scripted))

    assert result.decision.verdict == "HOLD"
    assert result.events[3].state == "invalid"
    assert result.events[3].error_code == "invalid_citation"


def test_duplicate_rebuttals_for_one_objection_fail_closed():
    scripted = outputs()
    duplicate = dict(scripted["defender"]["rebuttals"][0])
    duplicate["rebuttal_id"] = "rebuttal-2"
    scripted["defender"]["rebuttals"].append(duplicate)

    result = review(Gateway(scripted))

    assert result.decision.verdict == "HOLD"
    assert result.events[2].error_code == "invalid_role_output"


def test_non_finite_provider_accounting_fails_closed_without_crashing():
    result = review(Gateway(role_costs={"critic": float("nan")}))

    assert result.decision.verdict == "HOLD"
    assert result.events[1].state == "budget_exceeded"
    assert result.events[1].cost_usd is None


def test_weakened_provider_policy_fails_closed():
    class WeakenedPolicyGateway(Gateway):
        def call(self, role, messages, schema, budget, model):
            result = super().call(role, messages, schema, budget, model)
            if role == "critic":
                return replace(
                    result,
                    provider_policy={"zdr": False, "data_collection": "allow"},
                )
            return result

    result = review(WeakenedPolicyGateway())

    assert result.decision.verdict == "HOLD"
    assert result.events[1].state == "invalid"
    assert result.events[1].error_code == "provider_policy_invalid"


def test_provider_policy_extra_fields_fail_closed_and_are_not_retained():
    class ExtraPolicyGateway(Gateway):
        def call(self, role, messages, schema, budget, model):
            return replace(
                super().call(role, messages, schema, budget, model),
                provider_policy={**MANDATORY_PROVIDER_POLICY, "api_key": "must-not-persist"},
            )

    result = review(ExtraPolicyGateway())

    assert result.decision.verdict == "HOLD"
    assert all(event.error_code == "provider_policy_invalid" for event in result.events[:4])
    assert all("api_key" not in event.provider_policy for event in result.events)


def test_malformed_provider_policy_value_holds_without_crashing_or_retaining_it():
    class MalformedPolicyGateway(Gateway):
        def call(self, role, messages, schema, budget, model):
            return replace(
                super().call(role, messages, schema, budget, model),
                provider_policy={"zdr": True, "data_collection": {"secret": "drop-me"}},
            )

    result = review(MalformedPolicyGateway())

    assert result.decision.verdict == "HOLD"
    assert all(event.error_code == "provider_policy_invalid" for event in result.events[:4])
    assert all(event.provider_policy == {"zdr": True} for event in result.events[:4])


def test_integer_one_cannot_impersonate_boolean_zdr_attestation():
    class IntegerZdrGateway(Gateway):
        def call(self, role, messages, schema, budget, model):
            return replace(
                super().call(role, messages, schema, budget, model),
                provider_policy={"zdr": 1, "data_collection": "deny"},
            )

    result = review(IntegerZdrGateway())

    assert result.decision.verdict == "HOLD"
    assert all(event.error_code == "provider_policy_invalid" for event in result.events[:4])
    assert all(event.provider_policy == {"data_collection": "deny"} for event in result.events[:4])


@pytest.mark.parametrize(
    "budget",
    [
        (float("nan"), 100, 0.01, 3),
        (5.0, True, 0.01, 3),
        (5.0, 100, float("inf"), 3),
        (5.0, 100, 0.01, False),
    ],
)
def test_role_budget_rejects_non_finite_or_boolean_limits(budget):
    with pytest.raises(ValueError):
        RoleBudget(*budget)
