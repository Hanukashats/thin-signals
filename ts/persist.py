"""Write a finished run to PostgreSQL. A repeat of the same idempotency key returns the stored row.

Run status (`succeeded`) is not the signal label (TS-INV-03).
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ts.db.models import Candidate, Decision, Run
from ts.harness import RunReport
from ts.nearest import build_nearest


def save_report(session: Session, report: RunReport) -> str:
    # Serialize all persistence for one live candidate. This covers both the
    # idempotency key and the candidate's (origin, technology) uniqueness.
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
        {"scope": f"thin-signals:live:{report.query}"},
    )
    existing = session.scalar(select(Run).where(Run.idempotency_key == report.idempotency_key))
    if existing is not None:
        report.repeated = True
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
    ))
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
            )
            if key in step and isinstance(step[key], (str, int, float, bool))
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
        "rules_version": report.card["rules_version"],
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
