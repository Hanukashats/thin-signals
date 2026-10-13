"""Append-only PostgreSQL ledger for structured review events."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import replace

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import DBAPIError

from ts.db import session_factory
from ts.db.models import Decision, ReviewEvent
from ts.harness import RunReport
from ts.persist import save_report
from ts.review.runner import (
    ReviewModels,
    RoleBudget,
    review_event_id,
    review_hash,
    run_review,
)
from ts.tests.test_review_runner import CANDIDATE, Gateway, Provider


def _reviewed_report(gateway=None) -> RunReport:
    suffix = uuid.uuid4().hex[:12]
    run_id = f"review-persist-{suffix}"
    card = {
        **CANDIDATE,
        "rules_version": "rules-0.1",
        "sources": [],
    }
    round_ = run_review(
        run_id=run_id,
        candidate=card,
        gateway=gateway or Gateway(),
        evidence_provider=Provider(),
        budget=RoleBudget(5, 500, 0.02, 3),
        models=ReviewModels("model-primary", "model-judge"),
    )
    return RunReport(
        id=run_id,
        query=f"review-persistence-{suffix}",
        idempotency_key=hashlib.sha256(suffix.encode()).hexdigest(),
        repeated=False,
        steps=[],
        sources=[],
        events=[],
        card=card,
        top=[card],
        shortfall=14,
        exclusion_registry=[],
        corpus_version="review-persistence-0.1",
        review=round_,
        review_enabled=True,
        review_status="completed",
    )


def test_review_events_are_structured_idempotent_and_linked_to_decision():
    report = _reviewed_report()
    factory = session_factory()

    with factory() as session:
        assert save_report(session, report) == report.id
    with factory() as session:
        events = list(session.scalars(
            select(ReviewEvent)
            .where(ReviewEvent.run_id == report.id)
            .order_by(ReviewEvent.sequence)
        ))
        decision = session.scalar(select(Decision).where(Decision.run_id == report.id))

    assert [event.role for event in events] == [
        "researcher", "critic", "defender", "control_critic", "arbiter",
    ]
    assert decision.review_event_id == events[-1].id
    assert all(len(event.input_hash) == len(event.output_hash) == 64 for event in events)
    assert events[0].provider_policy == {"zdr": True, "data_collection": "deny"}
    assert events[-1].provider_policy == {}
    assert events[0].provenance[0]["snapshot_ref"].startswith("sha256:")
    assert events[0].budget == {
        "time_seconds": 5,
        "max_output_tokens": 500,
        "max_cost_usd": 0.02,
        "evidence_limit": 3,
    }
    stored = json.dumps([event.payload for event in events], sort_keys=True)
    for forbidden in (
        "statement", "promotion_hypothesis", "uncertainties", "messages",
        "system_prompt", "chain_of_thought", "Attested primary text",
    ):
        assert forbidden not in stored

    with factory() as session:
        assert save_report(session, report) == report.id
        assert session.scalar(
            select(func.count()).select_from(ReviewEvent).where(ReviewEvent.run_id == report.id)
        ) == 5


def test_database_rejects_review_event_update_and_delete():
    report = _reviewed_report()
    factory = session_factory()
    with factory() as session:
        save_report(session, report)

    with factory() as session, pytest.raises(DBAPIError):
        session.execute(
            update(ReviewEvent)
            .where(ReviewEvent.run_id == report.id)
            .values(state="tampered")
        )
        session.commit()
    with factory() as session, pytest.raises(DBAPIError):
        session.execute(delete(ReviewEvent).where(ReviewEvent.run_id == report.id))
        session.commit()


def _replace_event(report: RunReport, index: int, **changes) -> RunReport:
    review = report.review
    events = list(review.events)
    changed = replace(events[index], **changes)
    changed = replace(
        changed,
        event_id=review_event_id(
            review.run_id,
            changed.sequence,
            changed.role,
            changed.input_hash,
            changed.output_hash,
        ),
    )
    events[index] = changed
    return replace(report, review=replace(review, events=tuple(events)))


def test_persistence_rejects_cross_run_binding_role_hash_and_extra_payload():
    factory = session_factory()
    cases = []

    report = _reviewed_report()
    cases.append(replace(report, review=replace(report.review, run_id="other-run")))

    report = _reviewed_report()
    cases.append(replace(report, review=replace(report.review, candidate_hash="f" * 64)))

    report = _reviewed_report()
    cases.append(_replace_event(report, 0, role="critic"))

    report = _reviewed_report()
    cases.append(_replace_event(report, 0, input_hash="0" * 64))

    report = _reviewed_report()
    payload = json.loads(json.dumps(report.review.events[0].payload))
    payload["claims"][0]["unexpected_freeform"] = "must never persist"
    output_hash = review_hash(payload)
    cases.append(_replace_event(report, 0, payload=payload, output_hash=output_hash))

    for tampered in cases:
        with factory() as session, pytest.raises(ValueError):
            save_report(session, tampered)


def test_incomplete_provider_usage_is_persisted_as_a_failed_accounting_event():
    class MissingTotalGateway(Gateway):
        def call(self, role, messages, schema, budget, model):
            result = super().call(role, messages, schema, budget, model)
            return replace(result, usage={"prompt_tokens": 100, "completion_tokens": 20})

    report = _reviewed_report(MissingTotalGateway())
    factory = session_factory()
    with factory() as session:
        save_report(session, report)
    with factory() as session:
        events = list(session.scalars(
            select(ReviewEvent)
            .where(ReviewEvent.run_id == report.id)
            .order_by(ReviewEvent.sequence)
        ))

    assert all(event.state == "invalid" for event in events[:4])
    assert all(event.error_code == "provider_metadata_invalid" for event in events[:4])
    assert all(event.prompt_tokens == 100 for event in events[:4])
    assert all(event.completion_tokens == 20 for event in events[:4])
    assert all(event.total_tokens is None for event in events[:4])
