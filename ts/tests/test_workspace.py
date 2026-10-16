"""The shared result survives sessions, failed work and concurrent operators."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, or_, select

from ts.api import create_app
from ts.checklist import CHECKLIST_VERSION
from ts.db import session_factory
from ts.db.models import Candidate, Decision, Run
from ts.persist import save_report
from ts.tests.test_product import _report


@pytest.fixture
def database():
    from ts.db.models import Workspace

    run_scope = or_(Run.id.like("workspace-%"), Run.id == "unfinished")
    candidate_scope = or_(
        Candidate.id.like("live-workspace-%"),
        Candidate.technology.like("workspace query %"),
    )
    factory = session_factory()
    with factory() as session:
        assert "_test_" in session.bind.url.database, "workspace tests require an isolated database"
        session.execute(delete(Workspace))
        session.execute(delete(Decision).where(Decision.run_id.in_(select(Run.id).where(run_scope))))
        session.execute(delete(Run).where(run_scope))
        session.execute(delete(Candidate).where(candidate_scope))
        session.commit()
    yield factory
    with factory() as session:
        session.execute(delete(Workspace))
        session.execute(delete(Decision).where(Decision.run_id.in_(select(Run.id).where(run_scope))))
        session.execute(delete(Run).where(run_scope))
        session.execute(delete(Candidate).where(candidate_scope))
        session.commit()


def completed(tmp_path, suffix="one"):
    report = _report(tmp_path)
    return replace(
        report, id=f"workspace-{suffix}", idempotency_key=f"workspace-key-{suffix}",
        query=f"workspace query {suffix}", corpus_version=f"live-w18+{CHECKLIST_VERSION}",
        top=[], shortfall=15, potential=[],
    )


def snapshot(factory):
    from ts.workspace import load_workspace

    with factory() as session:
        return load_workspace(session)


def test_empty_workspace_is_read_only(database):
    from ts.db.models import Workspace

    result = snapshot(database)
    assert result["revision"] == 0 and result["run"] is None
    assert len(result["archive"]["cards"]) == 15
    with database() as session:
        assert session.scalar(select(Workspace)) is None


def test_only_completed_parent_replaces_workspace_and_survives_reopen(database, tmp_path):
    report = completed(tmp_path)
    with database() as session:
        save_report(session, report, publish=True)
    first = snapshot(database)
    assert first["run"]["run_id"] == report.id
    assert first["run"]["potential"] == []
    with database() as session:
        child = replace(completed(tmp_path, "child"), corpus_version="live-w18")
        save_report(session, child)
        session.add(Run(id="unfinished", query="pending", idempotency_key="pending", status="running",
                        corpus_version="live-w18", rules_version="rules-0.1", stats={}))
        session.commit()
    assert snapshot(database) == first


def test_archive_search_persists_without_mutating_run_and_replay_is_idempotent(database, tmp_path):
    from ts.workspace import save_archive

    report = completed(tmp_path)
    with database() as session:
        save_report(session, report, publish=True)
        before = session.get(Run, report.id).stats.copy()
    initial = snapshot(database)
    with database() as session:
        saved = save_archive(session, query="Кнудсена", families=[], expected_revision=initial["revision"])
    assert [c["id"] for c in saved["archive"]["cards"]] == ["T01"]
    assert snapshot(database) == saved
    with database() as session:
        repeat = save_archive(session, query="Кнудсена", families=[], expected_revision=initial["revision"])
        assert session.get(Run, report.id).stats == before
    assert repeat == saved


def test_stale_archive_writer_cannot_overwrite_new_run_or_archive(database, tmp_path):
    from ts.workspace import WorkspaceConflict, save_archive

    with database() as session:
        save_report(session, completed(tmp_path), publish=True)
    first = snapshot(database)
    with database() as session:
        save_report(session, completed(tmp_path, "two"), publish=True)
    with database() as session, pytest.raises(WorkspaceConflict):
        save_archive(session, query="Кнудсена", families=[], expected_revision=first["revision"])
    assert snapshot(database)["run"]["run_id"] == "workspace-two"


def test_two_concurrent_archive_writers_have_one_winner(database):
    from ts.workspace import WorkspaceConflict, save_archive

    def attempt(query):
        with database() as session:
            try:
                save_archive(session, query=query, families=[], expected_revision=0)
                return "saved"
            except WorkspaceConflict:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["Кнудсена", "волокно"]))
    assert sorted(results) == ["conflict", "saved"]
    assert snapshot(database)["revision"] == 1


def test_failed_transport_or_incompatible_report_never_replaces_workspace(database, tmp_path):
    from ts.workspace import WorkspaceIncompatible

    with database() as session:
        save_report(session, completed(tmp_path), publish=True)
    good = snapshot(database)
    bad = replace(completed(tmp_path, "offline"), sources=[],
                  steps=[{"name": "search", "status": "failed", "connector": "offline"}])
    with database() as session:
        save_report(session, bad, publish=True)
    assert snapshot(database) == good
    stale = replace(completed(tmp_path, "stale"), corpus_version="live-w18+checklist-v14")
    with database() as session, pytest.raises(WorkspaceIncompatible):
        save_report(session, stale, publish=True)
    assert snapshot(database) == good


def test_publish_failure_rolls_back_run_and_pointer_together(database, tmp_path, monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("archive unavailable")

    monkeypatch.setattr("ts.workspace.archive_result", unavailable)
    with database() as session, pytest.raises(RuntimeError):
        save_report(session, completed(tmp_path), publish=True)
    with database() as session:
        assert session.get(Run, "workspace-one") is None


def test_explicit_cached_run_republishes_without_changing_historical_result(database, tmp_path):
    from ts.workspace import publish_run

    with database() as session:
        save_report(session, completed(tmp_path), publish=True)
        original = session.get(Run, "workspace-one").stats.copy()
    with database() as session:
        save_report(session, completed(tmp_path, "two"), publish=True)
    with database() as session:
        publish_run(session, "workspace-one")
        session.commit()
    assert snapshot(database)["run"]["run_id"] == "workspace-one"
    with database() as session:
        assert session.get(Run, "workspace-one").stats == original


def test_workspace_api_contract_validates_and_reports_conflict():
    from ts.workspace import WorkspaceConflict

    def save(**kwargs):
        raise WorkspaceConflict("workspace changed")

    client = TestClient(create_app(lambda *args: {}, workspace=lambda: {"revision": 3}, archive=save))
    assert client.get("/v1/workspace/latest").json()["revision"] == 3
    assert client.post("/v1/workspace/archive", json={"query": "Кнудсена", "expected_revision": 1}).status_code == 409
    assert client.post("/v1/workspace/archive", json={"query": "x", "expected_revision": -1}).status_code == 422


def test_archive_drift_does_not_hide_saved_live_modules(database, tmp_path):
    from ts.db.models import Workspace

    with database() as session:
        save_report(session, completed(tmp_path), publish=True)
        row = session.get(Workspace, 1)
        row.archive = {**row.archive, "families": ["obsolete family"], "archive_sha256": "older"}
        session.commit()
    result = snapshot(database)
    assert result["run"]["run_id"] == "workspace-one"
    assert result["archive"]["compatible"] is False
    assert result["archive"]["families"] == ["obsolete family"]
    assert result["archive"]["cards"] == []
    assert result["issues"]


def test_archive_response_is_consistent_if_run_publishes_immediately_after_commit(database, tmp_path, monkeypatch):
    from ts.workspace import save_archive

    with database() as session:
        save_report(session, completed(tmp_path), publish=True)
    initial = snapshot(database)
    with database() as session:
        commit = session.commit

        def concurrent_commit():
            commit()
            with database() as other:
                save_report(other, completed(tmp_path, "concurrent"), publish=True)

        monkeypatch.setattr(session, "commit", concurrent_commit)
        result = save_archive(session, query="Кнудсена", families=[], expected_revision=initial["revision"])
    assert result == snapshot(database)
    assert result["revision"] == initial["revision"] + 2
    assert result["run"]["run_id"] == "workspace-concurrent"
