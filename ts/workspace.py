"""Atomic shared result selection over native Run and sealed archive data."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ts.checklist import CHECKLIST_VERSION
from ts.db.models import Run, Workspace
from ts.desk import OLD_TECH_SNAPSHOT, old_tech_board, saved_run_state
from ts.potential import POTENTIAL_VERSION

WORKSPACE_VERSION = "workspace-v1"
ARCHIVE_SEARCH_VERSION = "archive-search-v1"


class WorkspaceConflict(ValueError):
    pass


class WorkspaceIncompatible(ValueError):
    pass


def archive_result(query: str = "", families: list[str] | None = None) -> dict:
    """Evaluate the native archive search and pin its deterministic result."""
    query = query.strip()
    families = sorted(set(families or []))
    whole = old_tech_board()
    if whole["total"] != 15:
        raise WorkspaceIncompatible("research archive unavailable")
    allowed = {card["family"] for card in whole["cards"]}
    if not set(families) <= allowed:
        raise WorkspaceIncompatible("unknown archive family")
    board = old_tech_board(query=query)
    if families:
        board["cards"] = [card for card in board["cards"] if card["family"] in families]
    board.update({
        "families": families,
        "available_families": sorted(allowed),
        "archive_sha256": hashlib.sha256(OLD_TECH_SNAPSHOT.read_bytes()).hexdigest(),
        "search_version": ARCHIVE_SEARCH_VERSION,
        "result_ids": [card["id"] for card in board["cards"]],
    })
    return board


def _descriptor(archive: dict) -> dict:
    return {key: archive[key] for key in (
        "query", "families", "archive_sha256", "search_version", "result_ids",
    )}


def compatible_run(row: Run) -> bool:
    stats = row.stats or {}
    if row.status != "succeeded" or row.finished_at is None:
        return False
    if CHECKLIST_VERSION not in row.corpus_version.split("+"):
        return False  # Includes historical internal fanout children.
    if row.rules_version != "rules-0.1" or not saved_run_state(stats)["safe_to_autoload"]:
        return False
    for card in stats.get("top") or []:
        if (card.get("checklist") or {}).get("version") != CHECKLIST_VERSION:
            return False
    return all(card.get("potential_version") == POTENTIAL_VERSION for card in stats.get("potential") or [])


def healthy_run(row: Run) -> bool:
    health = (row.stats or {}).get("search_health")
    if isinstance(health, dict):
        return health.get("search_ok", 0) > 0 and health.get("countersearch_ok", 0) > 0
    # Explicit bootstrap/replay of pre-workspace runs requires actual retrieved sources.
    return bool((row.stats or {}).get("sources"))


def _locked(session: Session) -> Workspace:
    session.execute(insert(Workspace).values(id=1, revision=0, archive={}).on_conflict_do_nothing())
    return session.scalar(select(Workspace).where(Workspace.id == 1).with_for_update().execution_options(
        populate_existing=True,
    ))


def publish_run(session: Session, run_id: str) -> bool:
    """Publish after completion; caller owns the Run+Decision+workspace transaction."""
    row = session.get(Run, run_id)
    if row is None:
        raise WorkspaceIncompatible("run does not exist")
    if row.status != "succeeded" or row.finished_at is None:
        return False
    if not compatible_run(row):
        raise WorkspaceIncompatible("only a compatible completed top-level run can publish")
    if not healthy_run(row):
        return False
    state = _locked(session)
    if state.run_id == row.id:
        return True
    if not state.archive:
        state.archive = _descriptor(archive_result())
    state.run_id = row.id
    state.revision += 1
    state.updated_at = datetime.now(UTC)
    session.flush()
    return True


def load_workspace(session: Session) -> dict:
    """One read snapshot; never publish or recompute scientific decisions on GET."""
    pair = session.execute(
        select(Workspace, Run).outerjoin(Run, Workspace.run_id == Run.id).where(Workspace.id == 1)
        .execution_options(populate_existing=True)
    ).first()
    state, run = pair if pair else (None, None)
    stored = state.archive if state else {}
    issues = []
    try:
        archive = archive_result(stored.get("query", ""), stored.get("families", []))
        compatible = not stored or _descriptor(archive) == stored
    except (WorkspaceIncompatible, OSError):
        whole = old_tech_board()
        archive = {**whole, **stored,
                   "available_families": sorted({card["family"] for card in whole["cards"]})}
        compatible = False
    if not compatible:
        issues.append("Сохранённый поиск относится к другой версии архива. Выполните поиск по архиву снова.")
        archive["cards"] = []
        archive["result_ids"] = list(stored.get("result_ids", []))
        archive["compatible"] = False
    else:
        archive["compatible"] = True
    payload = None
    if run:
        payload = {**(run.stats or {}), "run_id": run.id, "run_status": run.status,
                   "query": run.query, "corpus_version": run.corpus_version}
        if not compatible_run(run):
            issues.append("Последний результат сохранён, но его версия отличается от текущей. Нужен новый прогон.")
    return {
        "version": WORKSPACE_VERSION,
        "revision": state.revision if state else 0,
        "run": payload,
        "run_compatible": run is None or compatible_run(run),
        "archive": archive,
        "issues": issues,
    }


def save_archive(session: Session, *, query: str, families: list[str], expected_revision: int) -> dict:
    wanted = _descriptor(archive_result(query, families))
    state = _locked(session)
    if state.archive == wanted:
        session.commit()  # Same-intent replay, including a lost response.
        return load_workspace(session)
    if state.revision != expected_revision:
        session.rollback()
        raise WorkspaceConflict("workspace changed; reload before saving")
    state.archive = wanted
    state.revision += 1
    state.updated_at = datetime.now(UTC)
    session.commit()
    return load_workspace(session)


def bootstrap_workspace(session: Session) -> dict:
    """Explicit operator migration of existing compatible history; never called by GET."""
    if session.get(Workspace, 1) is None:
        for row in session.scalars(select(Run).where(Run.status == "succeeded").order_by(
            Run.finished_at.desc().nulls_last(), Run.created_at.desc(), Run.id.desc(),
        )):
            if compatible_run(row) and healthy_run(row):
                publish_run(session, row.id)
                session.commit()
                break
    return load_workspace(session)
