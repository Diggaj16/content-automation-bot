"""
Shared pytest fixtures.

Tests run against a real Postgres (CI: a pgvector/pgvector:pg16 service
container; locally: point DATABASE_URL at a disposable test database). Real
Postgres is used deliberately — pgvector columns, JSONB defaults, and
ON CONFLICT upserts don't behave the same against SQLite or a mock, and bugs
like the embedding-column numpy-truthiness issue only show up against the
real thing.

_clean_tables truncates every table before each test, so tests never depend
on ordering and never leak state into each other.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import app.db.orm  # noqa: F401 — registers all models on Base.metadata
from app.config import get_settings
from app.db.base import Base
from app.db.session import get_engine, get_sessionmaker, reset_engine


@pytest.fixture(scope="session", autouse=True)
def _require_test_database():
    """
    Refuse to run if DATABASE_URL doesn't look like a test database.

    _clean_tables truncates every table before every test — pointing this at
    a real dev/prod database would silently wipe it.
    """
    url = get_settings().database_url
    db_name = url.rsplit("/", 1)[-1].split("?", 1)[0]
    if "test" not in db_name.lower():
        pytest.exit(
            f"DATABASE_URL ({db_name!r}) does not look like a test database. "
            "Tests truncate every table before each run — set DATABASE_URL to "
            "a database with 'test' in its name before running pytest.",
            returncode=1,
        )


@pytest.fixture(scope="session", autouse=True)
def _schema(_require_test_database):
    """Create the pgvector extension + full schema once per test session."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    yield
    reset_engine()


@pytest.fixture(autouse=True)
def _clean_tables(_schema):
    """Truncate every table before each test for isolation."""
    engine = get_engine()
    table_names = [t.name for t in Base.metadata.sorted_tables]
    with engine.begin() as conn:
        conn.execute(
            text(f"TRUNCATE TABLE {', '.join(table_names)} RESTART IDENTITY CASCADE")
        )
    yield


@pytest.fixture
def db_session(_clean_tables):
    """A real, committable Session bound to the test database."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient wired to the test DB session via dependency override."""
    from app.api.deps import get_db
    from app.api.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)
