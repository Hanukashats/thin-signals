"""Engine/session helpers. URL from ts.settings (password from TS_PG_PASSWORD_FILE)."""
from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from ts.settings import Settings, load

_engine: Engine | None = None


def engine(settings: Settings | None = None) -> Engine:
    global _engine
    if _engine is None:
        s = settings or load()
        _engine = create_engine(s.sqlalchemy_url, pool_pre_ping=True)
    return _engine


def session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    return sessionmaker(engine(settings), expire_on_commit=False)
