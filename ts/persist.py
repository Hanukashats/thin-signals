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
    session.commit()
    return report.id


def show_found(body: dict) -> dict:
    """A card with no readable text stays on the list and keeps an empty number."""
    top = [item for item in (body.get("top") or []) if isinstance(item, dict)]
    seen = set()
    for card in top:
        seen.add(_card_key(card))
    wide = _is_wide(body)
    if wide:
        # Wide run: passers first, then papers that failed the checklist
        # (real confidence, marked shown="excluded"), up to 15 on screen.
        for card in body.get("exclusion_registry") or []:
            if len(top) >= 15:
                break
            if not isinstance(card, dict):
                continue
            key = _card_key(card)
            if key in seen:
                continue
            seen.add(key)
            row = dict(card)
            row["shown"] = "excluded"
            top.append(row)
    for card in body.get("unread") or []:
        if wide and len(top) >= 15:
            break
        if not isinstance(card, dict):
            continue
        key = _card_key(card)
        if key in seen:
            continue
        seen.add(key)
        row = dict(card)
        row["confidence"] = None
        top.append(row)
    shown = dict(body)
    shown["top"] = top
    if "shortfall" in shown:
        shown["shortfall"] = max(0, 15 - len(top))
    return shown


def _is_wide(body: dict) -> bool:
    fanout = body.get("fanout")
    if not isinstance(fanout, dict):
        return False
    direction = fanout.get("direction")
    if not isinstance(direction, dict):
        return False
    return direction.get("mode") == "wide"


def _card_key(card: dict) -> tuple:
    urls = tuple(sorted(source.get("url") or "" for source in card.get("sources") or [] if isinstance(source, dict)))
    return (urls, str(card.get("technology") or ""))


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
    return show_found(stats)


def load_report(session: Session, idempotency_key: str) -> dict | None:
    row = session.scalar(select(Run).where(Run.idempotency_key == idempotency_key))
    if row is None:
        return None
    return show_found({"run_id": row.id, "run_status": row.status, **(row.stats or {})})


def public_report(report: RunReport) -> dict:
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
        "model_id": report.model_id,
        "provider": report.provider,
        "rules_version": report.card["rules_version"],
        "chain_link": report.card.get("chain_link"),
        "fanout": report.fanout,
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
    return show_found(body)
