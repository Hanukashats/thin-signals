"""HTTP API. Parsing and inference stay out of the UI process (TZ-12)."""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field


class QueryIn(BaseModel):
    query: str = Field(min_length=2, max_length=400)
    limit: int = Field(default=3, ge=1, le=8)
    extract: bool = False


def create_app(runner, latest=None) -> FastAPI:
    app = FastAPI(title="Thin Signals", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/v1/runs/latest")
    def latest_run() -> dict:
        if latest is None:
            return {"run": None}
        return {"run": latest()}

    @app.post("/v1/runs")
    def create_run(body: QueryIn) -> dict:
        return runner(body.query, body.limit, body.extract)

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


app = create_app(default_runner, default_latest)
