"""Write a finished run to PostgreSQL. A repeat of the same idempotency key returns the stored row.

Run status (`succeeded`) is not the signal label (TS-INV-03).
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from ts.db.models import Candidate, Decision, ReviewEvent, Run
from ts.harness import RUN_CONTRACT_VERSION, TOP_N, RunReport
from ts.llm import MANDATORY_PROVIDER_POLICY
from ts.nearest import build_nearest
from ts.review.contracts import ArbiterDecision, parse_role_output
from ts.review.integration import public_review_trace
from ts.review.runner import (
    ReviewRound,
    review_candidate_hash,
    review_event_id,
    review_hash,
    validated_model_id,
    validated_provider_id,
)

_HASH = re.compile(r"^[0-9a-f]{64}$")
_SAFE_LABEL = re.compile(r"^[A-Za-z0-9._:/ -]{1,128}$")
_EVIDENCE_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,63}$")
_ORIGIN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/() -]{0,127}$")
_SNAPSHOT_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
_EXPECTED_ROLES = ("researcher", "critic", "defender", "control_critic", "arbiter")
_ROLE_STATES = frozenset({"succeeded", "timeout", "invalid", "failed", "budget_exceeded"})
_ERROR_CODES = frozenset({
    "defender_no_new_evidence",
    "evidence_identity_conflict",
    "evidence_provider_invalid",
    "invalid_citation",
    "invalid_role_output",
    "provider_metadata_invalid",
    "provider_policy_invalid",
    "role_budget_exceeded",
    "role_call_failed",
    "role_timeout",
})


def _safe_label(value: object, limit: int) -> str | None:
    if not isinstance(value, str) or len(value) > limit or not _SAFE_LABEL.fullmatch(value):
        return None
    return value


def _valid_hash(value: object) -> bool:
    return isinstance(value, str) and bool(_HASH.fullmatch(value)) and value != "0" * 64


def _claim_payload(value: dict) -> dict:
    return {
        key: value[key]
        for key in ("claim_id", "critical", "evidence_ids", "status", "reason_codes")
    }


def _structural_review_payload(role: str, value: dict | None) -> dict | None:
    """Whitelist only fields that drive typed state transitions."""
    if value is None:
        return None
    if role == "researcher":
        return {"claims": [_claim_payload(row) for row in value["claims"]]}
    if role == "critic":
        fields = (
            "objection_id", "claim_id", "failure_mode", "counterevidence_ids",
            "severity", "status",
        )
        return {"objections": [
            {key: row[key] for key in fields} for row in value["objections"]
        ]}
    if role == "defender":
        fields = (
            "rebuttal_id", "objection_id", "action", "evidence_ids", "changed_fields",
        )
        rebuttals = []
        for row in value["rebuttals"]:
            stored = {key: row[key] for key in fields}
            stored["replacement_claim"] = (
                _claim_payload(row["replacement_claim"])
                if row["replacement_claim"] is not None else None
            )
            rebuttals.append(stored)
        return {"rebuttals": rebuttals}
    if role == "control_critic":
        fields = (
            "finding_id", "objection_id", "rebuttal_id", "evidence_ids",
            "evidence_valid", "origin_independent", "residual_status",
        )
        return {"findings": [
            {key: row[key] for key in fields} for row in value["findings"]
        ]}
    fields = ("verdict", "rule_version", "ledger_revision", "blocking_ids", "reason_codes")
    return {key: value[key] for key in fields}


def _validated_payload(event) -> dict | None:
    if event.role == "arbiter":
        if event.state != "succeeded" or event.payload is None:
            raise ValueError("arbiter event must contain a successful typed decision")
        return ArbiterDecision.model_validate(event.payload).model_dump(mode="json")
    if event.state != "succeeded":
        if event.payload is not None:
            raise ValueError("failed review events cannot retain raw model payloads")
        return None
    if event.payload is None:
        raise ValueError("successful review event is missing its typed payload")
    return parse_role_output(event.role, event.payload).model_dump(mode="json")


def _validated_provenance(event) -> list[dict]:
    if not isinstance(event.provenance, (list, tuple)):
        raise TypeError("review provenance must be a bounded sequence")
    if len(event.provenance) != len(event.evidence_ids):
        raise ValueError("review provenance does not match evidence IDs")
    stored = []
    for expected_id, row in zip(event.evidence_ids, event.provenance, strict=True):
        if not isinstance(row, dict) or set(row) != {
            "evidence_id", "provenance", "snapshot_ref", "origin_group_id", "url_hash",
        }:
            raise ValueError("review provenance contains unexpected fields")
        snapshot_ref = row["snapshot_ref"]
        origin_group_id = row["origin_group_id"]
        if (
            row["evidence_id"] != expected_id
            or not isinstance(expected_id, str)
            or not _EVIDENCE_ID.fullmatch(expected_id)
            or row["provenance"] not in {
                "preserved_primary", "preserved_non_primary", "snippet_only",
            }
            or (snapshot_ref is not None and not _SNAPSHOT_REF.fullmatch(snapshot_ref))
            or (origin_group_id is not None and not _ORIGIN_ID.fullmatch(origin_group_id))
            or not _valid_hash(row["url_hash"])
        ):
            raise ValueError("review provenance is invalid")
        stored.append({
            "evidence_id": expected_id,
            "provenance": row["provenance"],
            "snapshot_ref": snapshot_ref,
            "origin_group_id": origin_group_id,
            "url_hash": row["url_hash"],
        })
    return stored


def _validated_policy(event) -> dict:
    policy = event.provider_policy
    if not isinstance(policy, dict) or not set(policy) <= {"zdr", "data_collection"}:
        raise ValueError("review provider policy contains unexpected fields")
    if "zdr" in policy and not isinstance(policy["zdr"], bool):
        raise ValueError("review provider ZDR policy is invalid")
    if "data_collection" in policy:
        data_collection = policy["data_collection"]
        if not isinstance(data_collection, str) or data_collection not in {"allow", "deny"}:
            raise ValueError("review provider data policy is invalid")
    if event.role == "arbiter" and policy:
        raise ValueError("deterministic arbiter cannot have a provider policy")
    if event.role != "arbiter" and event.state == "succeeded" and policy != MANDATORY_PROVIDER_POLICY:
        raise ValueError("successful review event lacks the mandatory provider policy")
    return dict(policy)


def _persist_review(session: Session, report: RunReport, candidate_id: str) -> str | None:
    review = report.review
    if review is None:
        if report.review_status == "completed":
            raise ValueError("completed review status lacks a review round")
        return None
    if not report.review_enabled or report.review_status != "completed":
        raise ValueError("review round must be explicitly enabled and completed")
    if not isinstance(review, ReviewRound):
        raise TypeError("report review must be a validated ReviewRound")
    events = list(review.events)
    if (
        review.run_id != report.id
        or review.candidate_hash != review_candidate_hash(report.card)
        or len(events) != 5
        or [event.sequence for event in events] != [1, 2, 3, 4, 5]
        or tuple(event.role for event in events) != _EXPECTED_ROLES
        or events[-1].payload != review.decision.model_dump(mode="json")
        or review.decision.ledger_revision != review.ledger_revision
        or events[-1].input_hash != review.ledger_revision
    ):
        raise ValueError("review round is incomplete or inconsistent")
    for event in events:
        if (
            event.state not in _ROLE_STATES
            or not _valid_hash(event.input_hash)
            or not _valid_hash(event.output_hash)
            or not _valid_hash(event.template_hash)
            or event.event_id != review_event_id(
                report.id, event.sequence, event.role, event.input_hash, event.output_hash,
            )
        ):
            raise ValueError("review event hashes are invalid")
        if (event.state == "succeeded") != (event.error_code is None):
            raise ValueError("review event state and error code disagree")
        if event.error_code is not None and event.error_code not in _ERROR_CODES:
            raise ValueError("review event error code is invalid")
        if _safe_label(event.template_version, 64) != event.template_version:
            raise ValueError("review template version is invalid")
        if event.model_id is not None and validated_model_id(event.model_id) != event.model_id:
            raise ValueError("review model ID is invalid")
        if event.provider is not None and validated_provider_id(event.provider) != event.provider:
            raise ValueError("review provider is invalid")
        if event.state == "succeeded" and event.role != "arbiter" and (
            event.model_id is None or event.provider is None
        ):
            raise ValueError("successful model event lacks route attribution")
        if len(event.evidence_ids) != len(set(event.evidence_ids)):
            raise ValueError("review evidence IDs must be unique")
        if (
            not isinstance(event.duration_ms, int)
            or isinstance(event.duration_ms, bool)
            or event.duration_ms < 0
            or event.finished_at < event.started_at
            or any(
                value is not None
                and (not isinstance(value, int) or isinstance(value, bool) or value < 0)
                for value in (event.prompt_tokens, event.completion_tokens, event.total_tokens)
            )
            or (
                event.state == "succeeded"
                and (
                    event.prompt_tokens is None
                    or event.completion_tokens is None
                    or event.total_tokens is None
                    or event.total_tokens < event.prompt_tokens + event.completion_tokens
                )
            )
            or (
                event.cost_usd is not None
                and (
                    not isinstance(event.cost_usd, (int, float))
                    or isinstance(event.cost_usd, bool)
                    or not math.isfinite(float(event.cost_usd))
                    or event.cost_usd < 0
                )
            )
        ):
            raise ValueError("review event accounting is invalid")
        payload = _validated_payload(event)
        if event.state == "succeeded" and event.output_hash != review_hash(payload):
            raise ValueError("review event output hash does not match its typed payload")
        provenance = _validated_provenance(event)
        provider_policy = _validated_policy(event)
        session.add(ReviewEvent(
            id=event.event_id,
            run_id=report.id,
            candidate_id=candidate_id,
            round_no=1,
            sequence=event.sequence,
            role=event.role,
            state=event.state,
            input_hash=event.input_hash,
            output_hash=event.output_hash,
            template_version=event.template_version,
            template_hash=event.template_hash,
            model_id=validated_model_id(event.model_id),
            provider=validated_provider_id(event.provider),
            provider_policy=provider_policy,
            started_at=event.started_at,
            finished_at=event.finished_at,
            duration_ms=event.duration_ms,
            prompt_tokens=event.prompt_tokens,
            completion_tokens=event.completion_tokens,
            total_tokens=event.total_tokens,
            cost_usd=event.cost_usd,
            evidence_ids=list(event.evidence_ids),
            provenance=provenance,
            budget=event.budget.public(),
            error_code=event.error_code,
            payload=_structural_review_payload(event.role, payload),
        ))
    session.flush()
    return events[-1].event_id


def _reservation_stats(
    *,
    run_id: str,
    query: str,
    rules_version: str,
    review_enabled: bool,
    interrupted: bool = False,
) -> dict:
    review_status = "interrupted" if interrupted else (
        "pending" if review_enabled else "disabled"
    )
    review = {"enabled": review_enabled, "status": review_status}
    if interrupted:
        review.update({
            "verdict": "HOLD",
            "blocking_ids": [],
            "reason_codes": ["run_interrupted"],
            "events": [],
        })
    return {
        "run_id": run_id,
        "run_status": "failed" if interrupted else "running",
        "run_contract_version": RUN_CONTRACT_VERSION,
        "query": query,
        "repeated": False,
        "signal_label": None,
        "confidence": None,
        "policy_action": "HOLD",
        "policy_reason": "run_interrupted" if interrupted else "run_in_progress",
        "reason_codes": ["run_interrupted"] if interrupted else [],
        "predictors": [],
        "sources": [],
        "events": 0,
        "top": [],
        "shortfall": TOP_N,
        "exclusion_registry": [],
        "unread": [],
        "near_miss": [],
        "potential": [],
        "model_id": None,
        "provider": None,
        "review": review,
        "rules_version": rules_version,
        "chain_link": None,
        "fanout": None,
        "retrieval": {
            "fingerprint": None,
            "connectors": [],
            "stages": [],
            "failures": 0,
            "theme_failures": 0,
            "theme_degraded": 0,
            "deadline_skipped_themes": [],
            "deadline_exhausted": False,
            "funnel": None,
        },
        "decision_scope": "run_empty",
        "decision_card": None,
        "counters": {
            "sources": 0,
            "admitted": 0,
            "excluded": 0,
            "unread": 0,
            "confident": 0,
        },
        "nearest": [],
    }


def reserve_report(
    session: object,
    *,
    run_id: str,
    query: str,
    idempotency_key: str,
    corpus_version: str,
    rules_version: str,
    review_enabled: bool,
    coordinated: bool = False,
) -> tuple[bool, dict | None]:
    """Commit a durable pre-spend reservation; unsupported test sessions opt out."""
    if not isinstance(session, Session):
        return False, None
    if not coordinated:
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
            {"scope": f"thin-signals:run:{idempotency_key}"},
        )
    existing = session.scalar(select(Run).where(Run.idempotency_key == idempotency_key))
    if existing is not None:
        if coordinated and existing.status == "running" and existing.finished_at is None:
            existing.status = "failed"
            existing.stats = _reservation_stats(
                run_id=existing.id,
                query=existing.query,
                rules_version=existing.rules_version,
                review_enabled=review_enabled,
                interrupted=True,
            )
            existing.finished_at = datetime.now(tz=UTC)
            session.commit()
        stored = {"run_id": existing.id, "run_status": existing.status, **(existing.stats or {})}
        return False, stored
    session.add(Run(
        id=run_id,
        query=query,
        corpus_version=corpus_version,
        rules_version=rules_version,
        model_id=None,
        provider=None,
        idempotency_key=idempotency_key,
        status="running",
        stats=_reservation_stats(
            run_id=run_id,
            query=query,
            rules_version=rules_version,
            review_enabled=review_enabled,
        ),
        finished_at=None,
    ))
    session.commit()
    return True, None


def fail_reserved_report(
    session: object,
    *,
    idempotency_key: str,
    review_enabled: bool,
    coordinated: bool = False,
) -> dict | None:
    """Close an interrupted reservation as a stable HOLD without raw errors."""
    if not isinstance(session, Session):
        return None
    if not coordinated:
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
            {"scope": f"thin-signals:run:{idempotency_key}"},
        )
    row = session.scalar(select(Run).where(Run.idempotency_key == idempotency_key))
    if row is None:
        return None
    if row.status == "running" and row.finished_at is None:
        row.status = "failed"
        row.stats = _reservation_stats(
            run_id=row.id,
            query=row.query,
            rules_version=row.rules_version,
            review_enabled=review_enabled,
            interrupted=True,
        )
        row.finished_at = datetime.now(tz=UTC)
        session.commit()
    return {"run_id": row.id, "run_status": row.status, **(row.stats or {})}


def acquire_report_lock(session: object, idempotency_key: str) -> bool:
    """Hold a PostgreSQL session lock until explicit release or process death."""
    if not isinstance(session, Session):
        return False
    session.execute(
        text("SELECT pg_advisory_lock(hashtextextended(:scope, 0))"),
        {"scope": f"thin-signals:run:{idempotency_key}"},
    )
    return True


def release_report_lock(session: object, idempotency_key: str) -> None:
    """Release a lock acquired by :func:`acquire_report_lock`."""
    if not isinstance(session, Session):
        return
    session.execute(
        text("SELECT pg_advisory_unlock(hashtextextended(:scope, 0))"),
        {"scope": f"thin-signals:run:{idempotency_key}"},
    )


@contextmanager
def coordinated_report_session(factory, idempotency_key: str) -> Iterator[tuple[object, bool]]:
    """Pin one connection for the session lock and every coordinated write."""
    initial = factory()
    if not isinstance(initial, Session):
        with initial as session:
            yield session, False
        return

    bind = initial.get_bind()
    if isinstance(bind, Connection):
        with initial as session:
            held = acquire_report_lock(session, idempotency_key)
            try:
                yield session, held
            finally:
                if held:
                    release_report_lock(session, idempotency_key)
        return

    initial.close()
    if not isinstance(bind, Engine):
        raise TypeError("report session must be bound to a SQLAlchemy engine or connection")
    with bind.connect() as connection, Session(
        bind=connection,
        expire_on_commit=False,
    ) as session:
        held = acquire_report_lock(session, idempotency_key)
        try:
            yield session, held
        finally:
            if held:
                release_report_lock(session, idempotency_key)


def save_report(
    session: Session,
    report: RunReport,
    *,
    reserved: bool = False,
    publish: bool = False,
) -> str:
    # Serialize all persistence for one live candidate. This covers both the
    # idempotency key and the candidate's (origin, technology) uniqueness.
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
        {"scope": f"thin-signals:live:{report.query}"},
    )
    existing = session.scalar(select(Run).where(Run.idempotency_key == report.idempotency_key))
    finalizing_reservation = bool(
        reserved
        and existing is not None
        and existing.id == report.id
        and existing.status == "running"
        and existing.finished_at is None
    )
    if existing is not None and not finalizing_reservation:
        report.repeated = True
        if publish:
            from ts.workspace import publish_run

            publish_run(session, existing.id)
            session.commit()
        return existing.id
    candidate = session.scalar(
        select(Candidate).where(Candidate.origin == "live", Candidate.technology == report.query)
    )
    if candidate is None:
        candidate_id = f"live-{report.id}"
        session.add(Candidate(
            id=candidate_id,
            technology=report.query,
            origin="live",
            status="live",
            source_urls=[s["url"] for s in report.sources],
        ))
        session.flush()
    else:
        candidate_id = candidate.id
    if finalizing_reservation:
        existing.query = report.query
        existing.corpus_version = report.corpus_version
        existing.rules_version = report.card["rules_version"]
        existing.model_id = report.model_id
        existing.provider = report.provider
        existing.status = report.status
        existing.stats = public_report(report)
        existing.finished_at = datetime.now(tz=UTC)
    else:
        session.add(Run(
            id=report.id,
            query=report.query,
            corpus_version=report.corpus_version,
            rules_version=report.card["rules_version"],
            model_id=report.model_id,
            provider=report.provider,
            idempotency_key=report.idempotency_key,
            status=report.status,
            stats=public_report(report),
            finished_at=datetime.now(tz=UTC),
        ))
    session.flush()
    review_event_id = _persist_review(session, report, candidate_id)
    session.add(Decision(
        id=f"dec-{report.id}",
        candidate_id=candidate_id,
        run_id=report.id,
        as_of=datetime.now(tz=UTC).date(),
        rules_version=report.card["rules_version"],
        action=report.card["policy_action"],
        label=report.card["label"],
        confidence=report.card["confidence"],
        reason_codes=report.card["reason_codes"],
        predictors=report.card["predictors"],
        review_event_id=review_event_id,
    ))
    if publish:
        from ts.workspace import publish_run
        publish_run(session, report.id)
    session.commit()
    return report.id


def latest_finished(session: Session) -> dict | None:
    """Newest finished run, including explicit degraded/failed outcomes."""
    row = session.scalar(
        select(Run)
        .where(Run.finished_at.is_not(None))
        .order_by(Run.finished_at.desc(), Run.created_at.desc())
    )
    if row is None:
        return None
    stats = dict(row.stats or {})
    stats.setdefault("run_id", row.id)
    stats.setdefault("run_status", row.status)
    stats.setdefault("query", row.query)
    return stats


def latest_succeeded(session: Session) -> dict | None:
    """Compatibility alias; callers now receive the newest finished run."""
    return latest_finished(session)


def load_report(session: Session, idempotency_key: str) -> dict | None:
    row = session.scalar(select(Run).where(Run.idempotency_key == idempotency_key))
    if row is None:
        return None
    return {"run_id": row.id, "run_status": row.status, **(row.stats or {})}


def public_report(report: RunReport) -> dict:
    decision_card = report.top[0].get("technology") if report.top else None
    connector_steps = [
        {
            key: step[key]
            for key in (
                "name", "connector", "status", "error", "n",
                "elapsed_ms", "queued_ms", "theme", "cached",
                "research_id", "reported_cost_usd", "advisory_count", "validated_count",
                "request_count", "request_limit",
                "artifact_refs",
            )
            if key in step and (
                isinstance(step[key], (str, int, float, bool))
                or (
                    key == "artifact_refs"
                    and isinstance(step[key], list)
                    and all(isinstance(item, str) for item in step[key])
                )
            )
        }
        for step in report.steps
        if step.get("name") in {"search", "chain", "countersearch"}
        and step.get("connector")
    ]
    stage_names = list(dict.fromkeys(step["name"] for step in connector_steps))
    retrieval_stages = []
    for name in stage_names:
        rows = [step for step in connector_steps if step["name"] == name]
        has_themes = any(step.get("theme") for step in rows)
        themes = list(dict.fromkeys(
            str(step["theme"])
            for step in rows if step.get("theme") and not step.get("cached")
        ))
        if has_themes:
            wall_ms = sum(max((
                step.get("queued_ms", 0) + step.get("elapsed_ms", 0)
                for step in rows if str(step.get("theme")) == theme
            ), default=0) for theme in themes)
        else:
            wall_ms = max((
                step.get("queued_ms", 0) + step.get("elapsed_ms", 0)
                for step in rows
            ), default=0)
        retrieval_stages.append({
            "name": name,
            "calls": len(rows),
            "succeeded": sum(1 for step in rows if step.get("status") == "ok"),
            "failed": sum(1 for step in rows if step.get("status") == "failed"),
            "executed": sum(1 for step in rows if not step.get("cached")),
            "cached": sum(1 for step in rows if step.get("cached")),
            "items": sum(
                step.get("n", 0) for step in rows
                if isinstance(step.get("n", 0), int) and not isinstance(step.get("n", 0), bool)
            ),
            # A bounded pool can queue work. Queue delay plus call duration is
            # the observable stage wall time; summing concurrent calls would
            # overstate it.
            "wall_ms": wall_ms,
        })
    stage_by_name = {stage["name"]: stage for stage in retrieval_stages}
    fanout = report.fanout if isinstance(report.fanout, dict) else {}
    deadline_skipped = list(fanout.get("deadline_skipped") or [])
    theme_runs = [row for row in (fanout.get("theme_runs") or []) if isinstance(row, dict)]
    retrieval_funnel = None
    if connector_steps:
        retrieval_funnel = {
            "discovery_items": sum(
                stage_by_name.get(name, {}).get("items", 0)
                for name in ("search", "chain")
            ),
            "unique_sources": len({
                source.get("url") for source in report.sources
                if isinstance(source, dict) and source.get("url")
            }),
            "deduplicated_events": (
                max(0, int(fanout.get("discovered_events") or 0))
                if fanout else len(report.events)
            ),
            "countersearch_items": stage_by_name.get("countersearch", {}).get("items", 0),
            "admitted": len(report.top),
            "excluded": len(report.exclusion_registry),
            "unread": len(getattr(report, "unread", None) or []),
        }
    body = {
        "run_id": report.id,
        "run_status": report.status,
        "run_contract_version": report.run_contract_version,
        "query": report.query,
        "repeated": report.repeated,
        "signal_label": report.card["label"],
        "confidence": report.card["confidence"],
        "policy_action": report.card["policy_action"],
        "policy_reason": report.card["policy_reason"],
        "reason_codes": report.card["reason_codes"],
        "predictors": report.card["predictors"],
        "sources": report.sources,
        "events": len(report.events),
        "top": report.top,
        "shortfall": report.shortfall,
        "exclusion_registry": report.exclusion_registry,
        "unread": list(getattr(report, "unread", None) or []),
        "near_miss": list(getattr(report, "near_miss", None) or []),
        "potential": list(getattr(report, "potential", None) or []),
        "model_id": report.model_id,
        "provider": report.provider,
        "review": public_review_trace(report),
        "rules_version": report.card["rules_version"],
        "corpus_version": report.corpus_version,
        "search_health": {
            f"{name}_ok": sum(step.get("name") == name and step.get("status") == "ok"
                              for step in report.steps)
            for name in ("search", "countersearch")
        },
        "chain_link": report.card.get("chain_link"),
        "fanout": report.fanout,
        "retrieval": {
            "fingerprint": report.retrieval_fingerprint,
            "connectors": connector_steps,
            "stages": retrieval_stages,
            "failures": (
                sum(1 for step in connector_steps if step.get("status") == "failed")
            ),
            "theme_failures": (
                sum(1 for row in theme_runs if row.get("status") == "failed")
                + len(deadline_skipped)
            ),
            "theme_degraded": sum(1 for row in theme_runs if row.get("status") == "degraded"),
            "deadline_skipped_themes": deadline_skipped,
            "deadline_exhausted": any(
                step.get("error") == "deadline_exceeded" for step in connector_steps
            ) or bool(deadline_skipped),
            "funnel": retrieval_funnel,
        },
        "decision_scope": "first_admitted_card" if report.top else "run_empty",
        "decision_card": decision_card,
        "counters": {
            "sources": len(report.sources),
            "admitted": len(report.top),
            "excluded": len(report.exclusion_registry),
            "unread": len(getattr(report, "unread", None) or []),
            "confident": sum(
                1 for c in report.top
                if isinstance(c.get("checklist"), dict)
                and c["checklist"].get("status") == "scored"
                and (c.get("confidence") or 0) > 0.75
            ),
        },
    }
    body["nearest"] = build_nearest(body)
    return body
