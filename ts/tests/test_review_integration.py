"""Default-off product integration for the bounded adversarial review."""
from __future__ import annotations

import copy
import hashlib
import json
import uuid
from contextlib import nullcontext
from dataclasses import replace
from time import monotonic

import pytest

from ts.harness import RunReport
from ts.live import _review_bound_fingerprint, _run_wide, run_query
from ts.llm import MANDATORY_PROVIDER_POLICY
from ts.persist import public_report
from ts.review.integration import (
    CandidateEvidenceProvider,
    attach_candidate_review,
    review_configuration_fingerprint,
)
from ts.review.runner import RoleBudget, RoleCallResult
from ts.settings import Settings
from ts.sources.connectors import Hit
from ts.tests.test_harness import Scripted
from ts.tests.test_llm import settings as make_settings
from ts.tests.test_review_runner import CANDIDATE, outputs


def _fresh_child_factory():
    from ts import db

    if db._engine is not None:
        db._engine.dispose(close=False)
    db._engine = None
    return db.session_factory()


def _crash_with_reserved_review(run_id, query, key, ready):
    import os

    from ts.persist import coordinated_report_session, reserve_report

    factory = _fresh_child_factory()
    with coordinated_report_session(factory, key) as (session, coordinated):
        assert coordinated
        owned, stored = reserve_report(
            session,
            run_id=run_id,
            query=query,
            idempotency_key=key,
            corpus_version="crash-test-v1",
            rules_version="rules-0.1",
            review_enabled=True,
            coordinated=True,
        )
        assert owned and stored is None
        ready.set()
        os._exit(73)


def _complete_reserved_review(run_id, query, key, ready, release):
    from datetime import UTC, datetime

    from sqlalchemy import select

    from ts.db.models import Run
    from ts.persist import coordinated_report_session, reserve_report

    factory = _fresh_child_factory()
    with coordinated_report_session(factory, key) as (session, coordinated):
        assert coordinated
        owned, stored = reserve_report(
            session,
            run_id=run_id,
            query=query,
            idempotency_key=key,
            corpus_version="multiprocess-test-v1",
            rules_version="rules-0.1",
            review_enabled=True,
            coordinated=True,
        )
        assert owned and stored is None
        ready.set()
        assert release.wait(10)
        row = session.scalar(select(Run).where(Run.idempotency_key == key))
        row.status = "succeeded"
        row.stats = {
            "run_id": run_id,
            "run_status": "succeeded",
            "query": query,
            "repeated": False,
            "review": {"enabled": True, "status": "completed", "verdict": "PROMOTE"},
        }
        row.finished_at = datetime.now(tz=UTC)
        session.commit()


def _card() -> dict:
    urls = [
        "https://arxiv.org/abs/2601.00001",
        "https://example.edu/papers/replication",
        "https://example.org/registry/experiment",
    ]
    rows = []
    sources = []
    for index, url in enumerate(urls, start=1):
        digest = hashlib.sha256(f"fragment-{index}".encode()).hexdigest()
        rows.append({
            "fragment": index,
            "text": f"Attested primary text for fragment {index}.",
            "url": url,
            "provenance": "preserved_primary",
            "snapshot_ref": f"sha256:{digest}",
        })
        sources.append({
            "url": url,
            "doi": f"10.1234/review-{index}",
            "origin_ids": [f"ror:origin-{index}"],
        })
    return {
        **CANDIDATE,
        "rules_version": "rules-0.1",
        "sources": sources,
        "counter_sources": [],
        "evidence_fragments": rows,
    }


def _report(card: dict | None = None) -> RunReport:
    card = card or _card()
    return RunReport(
        id="review-integration-run",
        query="review integration query",
        idempotency_key="f" * 64,
        repeated=False,
        steps=[],
        sources=list(card["sources"]),
        events=[],
        card=card,
        top=[card],
        shortfall=14,
        exclusion_registry=[],
    )


class AdaptiveGateway:
    def __init__(self, *, fail: bool = False):
        self.calls = []
        self.fail = fail

    def call(self, role, messages, schema, budget, model):
        self.calls.append((role, budget, model))
        if self.fail:
            raise RuntimeError("provider unavailable")
        body = messages[1]["content"].split("\n", 1)[1].rsplit("\n", 1)[0]
        evidence_ids = [row["evidence_id"] for row in json.loads(body)["evidence"]]
        assert len(evidence_ids) >= 3
        mapped = json.dumps(outputs())
        for old, new in zip(
            ("evidence-1", "evidence-2", "evidence-3"),
            evidence_ids,
            strict=True,
        ):
            mapped = mapped.replace(old, new)
        return RoleCallResult(
            payload=json.loads(mapped)[role],
            model_id=model,
            provider="FixtureZDR",
            usage={"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200},
            latency_s=0.01,
            cost_usd=0.001,
            provider_policy=dict(MANDATORY_PROVIDER_POLICY),
        )

    def route_is_valid(self, requested_model, response_model, provider):
        return requested_model == response_model and provider == "FixtureZDR"


class MaliciousRouteGateway(AdaptiveGateway):
    def call(self, role, messages, schema, budget, model):
        result = super().call(role, messages, schema, budget, model)
        return replace(
            result,
            model_id="https://example.org/private-prompt",
            provider="raw secret marker and hidden reasoning",
        )


class WrongApprovedModelGateway(AdaptiveGateway):
    def call(self, role, messages, schema, budget, model):
        result = super().call(role, messages, schema, budget, model)
        return replace(result, model_id="openai/gpt-4.1")


class CompactUntrustedRouteGateway(AdaptiveGateway):
    def call(self, role, messages, schema, budget, model):
        result = super().call(role, messages, schema, budget, model)
        return replace(
            result,
            model_id="private-prompt-fragment",
            provider="private-reasoning-marker",
        )


class BrokenEvidenceProvider:
    def retrieve(self, *_args, **_kwargs):
        raise OSError("private filesystem location and secret marker")


def _enabled(settings: Settings) -> Settings:
    return replace(settings, adversarial_review_enabled=True)


def test_review_defaults_off_and_configuration_changes_repeat_identity(tmp_path):
    settings = make_settings(tmp_path)

    assert settings.adversarial_review_enabled is False
    base = review_configuration_fingerprint(settings)
    enabled = review_configuration_fingerprint(_enabled(settings))
    changed_budget = review_configuration_fingerprint(replace(
        settings,
        review_max_cost_usd=settings.review_max_cost_usd + 0.01,
    ))
    changed_model = review_configuration_fingerprint(replace(
        settings,
        llm_judge="openai/gpt-4.1",
    ))
    changed_policy = review_configuration_fingerprint(replace(
        settings,
        llm_provider_policy={**settings.llm_provider_policy, "allow_fallbacks": False},
    ))
    changed_allowlist = review_configuration_fingerprint(replace(
        settings,
        allowed_models=(*settings.allowed_models, "fixture/reserve"),
    ))
    changed_url = review_configuration_fingerprint(replace(
        settings,
        openrouter_url="https://alternate.test/api/v1",
    ))

    assert len({
        base,
        enabled,
        changed_budget,
        changed_model,
        changed_policy,
        changed_allowlist,
        changed_url,
    }) == 7
    assert _review_bound_fingerprint("retrieval-v1", settings, enabled=False) == "retrieval-v1"
    assert _review_bound_fingerprint(
        "retrieval-v1", _enabled(settings), enabled=True,
    ) != "retrieval-v1"


def test_candidate_provider_uses_only_attested_fragments_and_explicit_origins():
    card = _card()
    provider = CandidateEvidenceProvider(card)
    rows = list(provider.retrieve("researcher", card, RoleBudget(5, 500, 0.02, 3)))

    assert len(rows) == 3
    assert all(row.provenance == "preserved_primary" for row in rows)
    assert [row.origin_group_id for row in rows] == [
        "ror:origin-1", "ror:origin-2", "ror:origin-3",
    ]
    assert all(row.snapshot_ref and row.snapshot_ref.startswith("sha256:") for row in rows)
    assert all("fragment" not in row.model_dump(mode="json") for row in rows)


def test_attach_review_is_default_off_and_enabled_trace_excludes_prose(tmp_path):
    settings = make_settings(tmp_path)
    untouched_gateway = AdaptiveGateway()
    disabled = attach_candidate_review(_report(), settings, gateway=untouched_gateway)

    assert disabled.review is None
    assert disabled.review_enabled is False
    assert disabled.review_status == "disabled"
    assert untouched_gateway.calls == []

    gateway = AdaptiveGateway()
    enabled = attach_candidate_review(_report(), _enabled(settings), gateway=gateway)
    body = public_report(enabled)

    assert [call[0] for call in gateway.calls] == [
        "researcher", "critic", "defender", "control_critic",
    ]
    assert body["review"]["enabled"] is True
    assert body["review"]["status"] == "completed"
    assert body["review"]["verdict"] == "PROMOTE"
    assert len(body["review"]["events"]) == 5
    trace = repr(body["review"])
    for forbidden in (
        "statement", "promotion_hypothesis", "uncertainties", "system_prompt",
        "chain_of_thought", "Attested primary text",
    ):
        assert forbidden not in trace


def test_review_failure_is_a_structured_hold_not_a_product_exception(tmp_path):
    gateway = AdaptiveGateway(fail=True)
    reviewed = attach_candidate_review(
        _report(), _enabled(make_settings(tmp_path)), gateway=gateway,
    )

    assert reviewed.review.decision.verdict == "HOLD"
    assert reviewed.review_status == "completed"
    assert [event.state for event in reviewed.review.events[:4]] == ["failed"] * 4
    assert all(event.error_code == "role_call_failed" for event in reviewed.review.events[:4])


def test_enabled_review_skips_empty_run_without_model_calls(tmp_path):
    gateway = AdaptiveGateway()
    empty = replace(_report(), top=[])

    reviewed = attach_candidate_review(
        empty, _enabled(make_settings(tmp_path)), gateway=gateway,
    )

    assert reviewed.review is None
    assert reviewed.review_enabled is True
    assert reviewed.review_status == "skipped_no_candidate"
    assert gateway.calls == []


def test_enabled_review_skips_candidate_without_citable_evidence(tmp_path):
    gateway = AdaptiveGateway()
    card = {**_card(), "evidence_fragments": []}

    reviewed = attach_candidate_review(
        _report(card), _enabled(make_settings(tmp_path)), gateway=gateway,
    )

    assert reviewed.review is None
    assert reviewed.review_enabled is True
    assert reviewed.review_status == "skipped_no_evidence"
    assert gateway.calls == []


def test_untrusted_route_metadata_is_rejected_without_public_echo(tmp_path):
    reviewed = attach_candidate_review(
        _report(), _enabled(make_settings(tmp_path)), gateway=MaliciousRouteGateway(),
    )

    trace = repr(public_report(reviewed)["review"])
    assert reviewed.review.decision.verdict == "HOLD"
    assert "https://example.org" not in trace
    assert "secret marker" not in trace
    assert all(event.model_id is None for event in reviewed.review.events[:4])
    assert all(event.provider is None for event in reviewed.review.events[:4])


def test_response_route_must_match_the_requested_approved_model(tmp_path):
    reviewed = attach_candidate_review(
        _report(),
        _enabled(make_settings(tmp_path)),
        gateway=WrongApprovedModelGateway(),
    )

    assert reviewed.review.decision.verdict == "HOLD"
    assert [event.error_code for event in reviewed.review.events[:4]] == [
        "provider_metadata_invalid",
    ] * 4
    assert all(event.model_id is None for event in reviewed.review.events[:4])
    assert all(event.provider is None for event in reviewed.review.events[:4])


def test_compact_untrusted_route_is_neither_public_nor_persisted(tmp_path):
    from sqlalchemy import select

    from ts.db import session_factory
    from ts.db.models import ReviewEvent
    from ts.persist import save_report

    suffix = uuid.uuid4().hex[:12]
    base = replace(
        _report(),
        id=f"compact-route-{suffix}",
        query=f"compact-route-{suffix}",
        idempotency_key=hashlib.sha256(f"compact-{suffix}".encode()).hexdigest(),
    )
    reviewed = attach_candidate_review(
        base,
        _enabled(make_settings(tmp_path)),
        gateway=CompactUntrustedRouteGateway(),
    )
    public = public_report(reviewed)
    factory = session_factory()
    with factory() as session:
        save_report(session, reviewed)
    with factory() as session:
        events = list(session.scalars(
            select(ReviewEvent)
            .where(ReviewEvent.run_id == reviewed.id, ReviewEvent.role != "arbiter")
            .order_by(ReviewEvent.sequence)
        ))

    assert reviewed.review.decision.verdict == "HOLD"
    assert "private-prompt-fragment" not in repr(public)
    assert "private-reasoning-marker" not in repr(public)
    assert all(event.model_id is None and event.provider is None for event in events)


def test_unexpected_evidence_provider_failure_becomes_hold_without_leak(tmp_path):
    gateway = AdaptiveGateway()
    reviewed = attach_candidate_review(
        _report(),
        _enabled(make_settings(tmp_path)),
        gateway=gateway,
        evidence_provider=BrokenEvidenceProvider(),
    )

    trace = repr(public_report(reviewed)["review"])
    assert reviewed.review.decision.verdict == "HOLD"
    assert [event.error_code for event in reviewed.review.events[:4]] == [
        "evidence_provider_invalid",
    ] * 4
    assert gateway.calls == []
    assert "private filesystem" not in trace


@pytest.mark.parametrize("error", [OSError("filesystem unavailable"), ValueError("bad URL")])
def test_client_construction_failure_becomes_hold(tmp_path, monkeypatch, error):
    from ts.review import integration

    def fail_client(_settings):
        raise error

    monkeypatch.setattr(integration, "OpenRouterClient", fail_client)
    reviewed = attach_candidate_review(_report(), _enabled(make_settings(tmp_path)))

    assert reviewed.review.decision.verdict == "HOLD"
    assert [event.error_code for event in reviewed.review.events[:4]] == [
        "role_call_failed",
    ] * 4


def test_invalid_review_budget_becomes_hold(tmp_path):
    settings = replace(
        _enabled(make_settings(tmp_path)),
        review_time_seconds=float("nan"),
    )

    reviewed = attach_candidate_review(_report(), settings)

    assert reviewed.review.decision.verdict == "HOLD"
    assert [event.error_code for event in reviewed.review.events[:4]] == [
        "role_call_failed",
    ] * 4


def test_enabled_review_persists_and_reloads_safe_trace_across_sessions(tmp_path):
    from sqlalchemy import func, select

    from ts.db import session_factory
    from ts.db.models import ReviewEvent, Run
    from ts.persist import load_report, save_report

    suffix = uuid.uuid4().hex[:12]
    base = replace(
        _report(),
        id=f"review-integration-{suffix}",
        query=f"review-integration-{suffix}",
        idempotency_key=hashlib.sha256(suffix.encode()).hexdigest(),
    )
    reviewed = attach_candidate_review(
        base, _enabled(make_settings(tmp_path)), gateway=AdaptiveGateway(),
    )
    factory = session_factory()
    with factory() as session:
        save_report(session, reviewed)
    with factory() as session:
        loaded = load_report(session, reviewed.idempotency_key)
        stored = session.scalar(select(Run).where(Run.id == reviewed.id))
        event_count = session.scalar(
            select(func.count()).select_from(ReviewEvent).where(ReviewEvent.run_id == reviewed.id)
        )

    assert loaded["review"]["verdict"] == "PROMOTE"
    assert loaded["review"]["status"] == "completed"
    assert stored.stats["review"] == loaded["review"]
    assert event_count == 5
    assert "Attested primary text" not in repr(loaded["review"])


def test_narrow_product_path_reviews_once_and_replay_does_not_call_roles(tmp_path, monkeypatch):
    from ts import live

    card = _card()
    settings = _enabled(make_settings(tmp_path))
    gateway = AdaptiveGateway()
    stored = {}

    monkeypatch.setattr(live, "annotate_checklist", lambda *_args, **_kwargs: {
        "top": [card], "excluded": [], "overflow": [], "unread": [], "stats": {},
    })
    monkeypatch.setattr(live, "_near_miss", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(live, "_potential", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        live,
        "load_report",
        lambda _session, key: copy.deepcopy(stored.get(key)),
    )
    monkeypatch.setattr(
        live,
        "save_report",
        lambda _session, report: stored.__setitem__(report.idempotency_key, public_report(report)),
    )
    connector = Scripted("arxiv", [Hit(
        "arxiv", "https://arxiv.org/abs/2601.99999", "Review candidate",
        "prototype", "paper", doi="10.1234/review",
    )])

    first = run_query(
        "review integration query",
        settings=settings,
        connectors=[connector],
        session_factory=lambda: nullcontext(None),
        _day="2026-10-13",
        _review_gateway=gateway,
    )
    call_count = len(gateway.calls)
    second = run_query(
        "review integration query",
        settings=settings,
        connectors=[connector],
        session_factory=lambda: nullcontext(None),
        _day="2026-10-13",
        _review_gateway=gateway,
    )

    assert first["review"]["verdict"] == "PROMOTE"
    assert call_count == 4
    assert second["repeated"] is True
    assert len(gateway.calls) == call_count


def test_wide_parent_is_reviewed_but_theme_children_are_not(tmp_path, monkeypatch):
    from ts import live

    card = _card()
    settings = _enabled(make_settings(tmp_path))
    gateway = AdaptiveGateway()
    plan = {
        "version": "review-wide-test",
        "frame": [],
        "themes": [{"id": "a", "title": "Alpha", "query": "alpha cell"}],
    }
    monkeypatch.setattr(live, "load_report", lambda *_args: None)
    monkeypatch.setattr(live, "save_report", lambda *_args: None)
    monkeypatch.setattr(live, "annotate_checklist", lambda *_args, **_kwargs: {
        "top": [card], "excluded": [], "overflow": [], "unread": [], "stats": {},
    })
    monkeypatch.setattr(live, "annotate_scopes", lambda cards, _settings: cards)
    monkeypatch.setattr(live, "annotate_reach", lambda cards, _settings: cards)
    monkeypatch.setattr(live, "_near_miss", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(live, "_potential", lambda *_args, **_kwargs: [])

    out = _run_wide(
        "wide review mission",
        plan,
        limit=1,
        extract=False,
        settings=settings,
        connectors=[Scripted("arxiv", [Hit(
            "arxiv", "https://arxiv.org/abs/2601.11111", "Alpha cell",
            "prototype", "paper", doi="10.1234/alpha",
        )])],
        session_factory=lambda: nullcontext(None),
        day="2026-10-13",
        deadline_at=monotonic() + 10,
        _review_gateway=gateway,
    )

    assert out["review"]["verdict"] == "PROMOTE"
    assert len(gateway.calls) == 4


def test_concurrent_enabled_request_reuses_durable_pre_spend_reservation(
    tmp_path,
    monkeypatch,
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from ts.db import session_factory

    card = _card()
    settings = _enabled(make_settings(tmp_path))
    query = f"concurrent-review-{uuid.uuid4().hex}"
    entered = Event()
    release = Event()

    class BlockingGateway(AdaptiveGateway):
        def call(self, role, messages, schema, budget, model):
            if not self.calls:
                entered.set()
                assert release.wait(10)
            return super().call(role, messages, schema, budget, model)

    gateway = BlockingGateway()
    monkeypatch.setattr("ts.live.annotate_checklist", lambda *_args, **_kwargs: {
        "top": [card], "excluded": [], "overflow": [], "unread": [], "stats": {},
    })
    monkeypatch.setattr("ts.live._near_miss", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("ts.live._potential", lambda *_args, **_kwargs: [])
    connector = Scripted("arxiv", [Hit(
        "arxiv",
        f"https://arxiv.org/abs/{uuid.uuid4().hex}",
        "Concurrent review candidate",
        "prototype",
        "paper",
        doi=f"10.1234/{uuid.uuid4().hex}",
    )])

    def execute():
        return run_query(
            query,
            settings=settings,
            connectors=[connector],
            session_factory=session_factory(),
            _day="2026-10-13",
            _review_gateway=gateway,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(execute)
        assert entered.wait(10)
        concurrent_result = pool.submit(execute)
        release.set()
        completed = owner.result(timeout=20)
        concurrent = concurrent_result.result(timeout=20)

    replay = execute()

    assert concurrent["run_id"] == completed["run_id"] == replay["run_id"]
    assert concurrent["run_status"] == "succeeded"
    assert concurrent["repeated"] is True
    assert completed["review"]["verdict"] == "PROMOTE"
    assert replay["review"]["verdict"] == "PROMOTE"
    assert replay["repeated"] is True
    assert len(gateway.calls) == 4


def test_interrupted_reserved_save_becomes_stable_hold_without_respend(
    tmp_path,
    monkeypatch,
):
    from ts import live
    from ts.db import session_factory

    card = _card()
    settings = _enabled(make_settings(tmp_path))
    query = f"interrupted-review-{uuid.uuid4().hex}"
    gateway = AdaptiveGateway()
    monkeypatch.setattr(live, "annotate_checklist", lambda *_args, **_kwargs: {
        "top": [card], "excluded": [], "overflow": [], "unread": [], "stats": {},
    })
    monkeypatch.setattr(live, "_near_miss", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(live, "_potential", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        live,
        "save_report",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("private disk path")),
    )
    connector = Scripted("arxiv", [Hit(
        "arxiv",
        f"https://arxiv.org/abs/{uuid.uuid4().hex}",
        "Interrupted review candidate",
        "prototype",
        "paper",
        doi=f"10.1234/{uuid.uuid4().hex}",
    )])

    def execute():
        return run_query(
            query,
            settings=settings,
            connectors=[connector],
            session_factory=session_factory(),
            _day="2026-10-13",
            _review_gateway=gateway,
        )

    first = execute()
    replay = execute()

    assert first["run_status"] == replay["run_status"] == "failed"
    assert first["policy_action"] == "HOLD"
    assert first["review"]["status"] == "interrupted"
    assert first["review"]["verdict"] == "HOLD"
    assert replay["repeated"] is True
    assert len(gateway.calls) == 4
    assert "private disk path" not in repr(first)


def test_hard_process_death_recovers_running_reservation_as_stable_hold():
    import multiprocessing

    from ts.db import session_factory
    from ts.live import _settle_reserved_report

    suffix = uuid.uuid4().hex
    run_id = f"crash-{suffix[:16]}"
    query = f"crash-review-{suffix}"
    key = hashlib.sha256(query.encode()).hexdigest()
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    process = context.Process(
        target=_crash_with_reserved_review,
        args=(run_id, query, key, ready),
    )
    process.start()
    assert ready.wait(10)
    process.join(10)

    assert process.exitcode == 73
    factory = session_factory()
    recovered = _settle_reserved_report(factory, key)
    replay = _settle_reserved_report(factory, key)
    assert recovered["run_status"] == replay["run_status"] == "failed"
    assert recovered["policy_action"] == "HOLD"
    assert recovered["review"]["status"] == "interrupted"
    assert recovered["review"]["verdict"] == "HOLD"


def test_separate_process_waiter_receives_owner_canonical_result():
    import multiprocessing
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from ts.db import session_factory
    from ts.live import _settle_reserved_report

    suffix = uuid.uuid4().hex
    run_id = f"owner-{suffix[:16]}"
    query = f"multiprocess-review-{suffix}"
    key = hashlib.sha256(query.encode()).hexdigest()
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    owner = context.Process(
        target=_complete_reserved_review,
        args=(run_id, query, key, ready, release),
    )
    owner.start()
    assert ready.wait(10)
    waiter_started = Event()

    def wait_for_owner():
        waiter_started.set()
        return _settle_reserved_report(session_factory(), key)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(wait_for_owner)
        assert waiter_started.wait(5)
        assert not future.done()
        release.set()
        result = future.result(timeout=15)
    owner.join(10)

    assert owner.exitcode == 0
    assert result["run_id"] == run_id
    assert result["run_status"] == "succeeded"
    assert result["review"]["verdict"] == "PROMOTE"


def test_distinct_review_locks_do_not_exhaust_their_own_connection_pool():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from ts.persist import (
        coordinated_report_session,
        fail_reserved_report,
        reserve_report,
    )
    from ts.settings import load

    engine = create_engine(
        load().sqlalchemy_url,
        pool_size=2,
        max_overflow=0,
        pool_timeout=0.3,
    )
    factory = sessionmaker(engine, expire_on_commit=False)
    barrier = Barrier(2)

    def reserve_distinct(index: int):
        suffix = uuid.uuid4().hex
        key = hashlib.sha256(f"pool-{suffix}".encode()).hexdigest()
        with coordinated_report_session(factory, key) as (session, coordinated):
            assert coordinated is True
            barrier.wait(timeout=5)
            owned, stored = reserve_report(
                session,
                run_id=f"pool-{index}-{suffix[:12]}",
                query=f"pool-review-{suffix}",
                idempotency_key=key,
                corpus_version="pool-test-v1",
                rules_version="rules-0.1",
                review_enabled=True,
                coordinated=True,
            )
            assert owned and stored is None
            return fail_reserved_report(
                session,
                idempotency_key=key,
                review_enabled=True,
                coordinated=True,
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve_distinct, range(2)))
    finally:
        engine.dispose()

    assert all(result["run_status"] == "failed" for result in results)
