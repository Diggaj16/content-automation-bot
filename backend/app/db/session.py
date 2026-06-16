"""
SQLAlchemy engine and session management (synchronous).

The agents and routers call the DB synchronously (async tasks wrap DB work in
asyncio.to_thread), so a sync engine + Session matches the existing concurrency
model with no event-loop complications.

Usage:
    # context manager (agents, scripts, background work)
    from app.db.session import session_scope
    with session_scope() as db:
        db.add(obj)            # commit happens on clean exit

    # FastAPI dependency
    from app.db.session import get_db
    def route(db: Session = Depends(get_db)): ...
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine():
    """Lazily build the singleton Engine from settings.database_url."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,      # drop dead connections instead of erroring
            pool_size=10,
            max_overflow=20,
            future=True,
        )
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, rollback on exception, always close."""
    db = get_sessionmaker()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency — yields a session and closes it after the request.

    Does NOT auto-commit; routers commit explicitly when they mutate.
    """
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()


def reset_engine() -> None:
    """Drop the cached engine/sessionmaker (tests, or after a config change)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
