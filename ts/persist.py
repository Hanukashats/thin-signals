"""Write a finished run to PostgreSQL. A repeat of the same idempotency key returns the stored row.

Run status (`succeeded`) is not the signal label (TS-INV-03).
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ts.db.models import Candidate, Decision, Run
from ts.harness import RunReport
from ts.nearest import build_nearest


def save_report(session: Session, report: RunReport) -> str:
    existing = session.scalar(select(Run).where(Run.idempotency_key == report.idempotency_key))
    if existing is not None:
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


def latest_succeeded(session: Session) -> dict | None:
    """Newest finished run, for the viewer. Does not score."""
    row = session.scalar(
        select(Run).where(Run.status == "succeeded").order_by(Run.finished_at.desc(), Run.created_at.desc())
    )
    if row is None:
        return None
    stats = dict(row.stats or {})
    stats.setdefault("run_id", row.id)
    stats.setdefault("run_status", row.status)
    stats.setdefault("query", row.query)
    return stats


def load_report(session: Session, idempotency_key: str) -> dict | None:
    row = session.scalar(select(Run).where(Run.idempotency_key == idempotency_key))
    if row is None:
        return None
    return {"run_id": row.id, "run_status": row.status, **(row.stats or {})}


def public_report(report: RunReport) -> dict:
    decision_card = report.top[0].get("technology") if report.top else None
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
