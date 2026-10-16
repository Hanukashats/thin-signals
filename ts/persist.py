"""Write a finished run to PostgreSQL. A repeat of the same idempotency key returns the stored row.

Run status (`succeeded`) is not the signal label (TS-INV-03).
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ts.db.models import Candidate, Decision, Run
from ts.harness import RunReport
from ts.nearest import build_nearest


def save_report(session: Session, report: RunReport, *, publish: bool = False) -> str:
    # Serialize same-intent saves, including a concurrent explicit cached replay.
    session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                    {"key": report.idempotency_key})
    existing = session.scalar(select(Run).where(Run.idempotency_key == report.idempotency_key))
    if existing is not None:
        if publish:
            from ts.workspace import publish_run
            publish_run(session, existing.id)
        session.commit()
        return existing.id
    session.execute(insert(Candidate).values(
        id=f"live-{report.id}", technology=report.query, origin="live", status="live",
        source_urls=[s["url"] for s in report.sources],
    ).on_conflict_do_nothing(index_elements=[Candidate.origin, Candidate.technology]))
    candidate_id = session.scalar(select(Candidate.id).where(
        Candidate.origin == "live", Candidate.technology == report.query,
    ))
    session.add(Run(
        id=report.id,
        query=report.query,
        corpus_version=report.corpus_version,
        rules_version=report.card["rules_version"],
        model_id=report.model_id,
        provider=report.provider,
        idempotency_key=report.idempotency_key,
        status="succeeded",
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
    if publish:
        from ts.workspace import publish_run
        publish_run(session, report.id)
    session.commit()
    return report.id


def latest_succeeded(session: Session) -> dict | None:
    """Compatibility endpoint for the shared, explicitly published result."""
    from ts.workspace import load_workspace
    return load_workspace(session)["run"]


def load_report(session: Session, idempotency_key: str) -> dict | None:
    row = session.scalar(select(Run).where(Run.idempotency_key == idempotency_key))
    if row is None:
        return None
    return {"run_id": row.id, "run_status": row.status, **(row.stats or {})}


def public_report(report: RunReport) -> dict:
    decision_card = report.top[0].get("technology") if report.top else None
    body = {
        "run_id": report.id,
        "run_status": "succeeded",
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
        "corpus_version": report.corpus_version,
        "search_health": {
            f"{name}_ok": sum(step.get("name") == name and step.get("status") == "ok"
                              for step in report.steps)
            for name in ("search", "countersearch")
        },
        "chain_link": report.card.get("chain_link"),
        "fanout": report.fanout,
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
