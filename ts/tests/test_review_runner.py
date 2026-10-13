"""One bounded role round and deterministic fail-closed arbitration."""
from __future__ import annotations

from ts.review.contracts import EvidenceItem
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
        )


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
    assert [event.role for event in result.events] == [
        "researcher", "critic", "defender", "control_critic", "arbiter",
    ]
    assert all(event.state == "succeeded" for event in result.events)


def test_unknown_evidence_reference_fails_closed_but_all_roles_still_run_once():
    scripted = outputs()
    scripted["researcher"]["claims"][0]["evidence_ids"] = ["evidence-unknown"]
    gateway = Gateway(scripted)

    result = review(gateway)

    assert result.decision.verdict == "HOLD"
    assert "invalid_citation" in result.decision.reason_codes
    assert len(gateway.calls) == 4
    assert result.events[0].state == "invalid"


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

    assert review(Gateway(scripted)).decision.verdict == "REFRAME"


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
    assert seen["max_tokens"] == 321
    assert seen["timeout_seconds"] == 3.5
    assert seen["json_schema"] == {"type": "object"}
    assert seen["require_parameters"] is True


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
