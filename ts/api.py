"""HTTP API. Parsing and inference stay out of the UI process (TZ-12)."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text


class QueryIn(BaseModel):
    query: str = Field(min_length=2, max_length=400)
    limit: int = Field(default=3, ge=1, le=8)
    extract: bool = False


class ArchiveIn(BaseModel):
    query: str = Field(default="", max_length=400)
    families: list[str] = Field(default_factory=list, max_length=15)
    expected_revision: int = Field(ge=0)


def create_app(runner, latest=None, ready=None, workspace=None, archive=None) -> FastAPI:
    app = FastAPI(title="Thin Signals", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/ready")
    def readiness() -> dict:
        check = ready or default_ready
        try:
            if check() is False:
                raise RuntimeError("readiness check returned false")
        except Exception as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc
        return {"ok": True, "database": "ready"}

    @app.get("/v1/runs/latest")
    def latest_run() -> dict:
        if latest is None:
            return {"run": None}
        return {"run": latest()}

    @app.post("/v1/runs")
    def create_run(body: QueryIn) -> dict:
        return runner(body.query, body.limit, body.extract)

    @app.get("/v1/workspace/latest")
    def latest_workspace() -> dict:
        return (workspace or default_workspace)()

    @app.post("/v1/workspace/archive")
    def archive_search(body: ArchiveIn) -> dict:
        from ts.workspace import WorkspaceConflict, WorkspaceIncompatible
        try:
            return (archive or default_archive)(**body.model_dump())
        except WorkspaceConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except WorkspaceIncompatible as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app


def default_runner(query: str, limit: int, extract: bool) -> dict:
    from ts.live import run_query
    return run_query(query, limit=limit, extract=extract)


def default_latest() -> dict | None:
    from ts.db import session_factory
    from ts.persist import latest_succeeded

    factory = session_factory()
    with factory() as session:
        return latest_succeeded(session)


def default_ready() -> bool:
    from ts.db import session_factory

    factory = session_factory()
    with factory() as session:
        session.execute(text("SELECT 1"))
    return True


def default_workspace() -> dict:
    from ts.db import session_factory
    from ts.workspace import load_workspace
    with session_factory()() as session:
        return load_workspace(session)


def default_archive(**kwargs) -> dict:
    from ts.db import session_factory
    from ts.workspace import save_archive
    with session_factory()() as session:
        return save_archive(session, **kwargs)


app = create_app(default_runner, default_latest)
