"""Default-off product integration for the bounded adversarial review."""
from __future__ import annotations

import copy
import hashlib
import json
import uuid
from contextlib import nullcontext
from dataclasses import replace
from time import monotonic

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

    assert len({base, enabled, changed_budget, changed_model}) == 4
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
