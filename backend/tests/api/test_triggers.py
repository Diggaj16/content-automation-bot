# tests/api/test_triggers.py
"""Tests for trigger and system-status endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.deps import get_supabase, get_arq_pool

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_sb():
    return MagicMock()


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    job = MagicMock()
    job.job_id = "test-job-123"
    pool.enqueue_job.return_value = job
    return pool


@pytest.fixture
def client_no_pool(mock_sb):
    """Client where arq pool is None (simulates Redis unavailable)."""
    app.dependency_overrides[get_supabase] = lambda: mock_sb
    app.dependency_overrides[get_arq_pool] = lambda: None
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client_with_pool(mock_sb, mock_pool):
    """Client where arq pool is a working mock."""
    app.dependency_overrides[get_supabase] = lambda: mock_sb
    app.dependency_overrides[get_arq_pool] = lambda: mock_pool
    return TestClient(app, raise_server_exceptions=False)


# ─── POST /trigger/research ────────────────────────────────────────────────────

def test_trigger_research_no_pool_returns_503(client_no_pool):
    resp = client_no_pool.post("/trigger/research")
    assert resp.status_code == 503


def test_trigger_research_enqueues_job(client_with_pool):
    resp = client_with_pool.post("/trigger/research")
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == "test-job-123"
    assert body["agent"] == "research"
    assert body["status"] == "enqueued"


# ─── POST /trigger/scoring ─────────────────────────────────────────────────────

def test_trigger_scoring_no_pool_returns_503(client_no_pool):
    resp = client_no_pool.post("/trigger/scoring")
    assert resp.status_code == 503


def test_trigger_scoring_enqueues_job(client_with_pool):
    resp = client_with_pool.post("/trigger/scoring")
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == "test-job-123"
    assert body["agent"] == "scoring"
    assert body["status"] == "enqueued"


# ─── GET /status ──────────────────────────────────────────────────────────────

def test_get_status_returns_runs_and_costs(client_with_pool, mock_sb):
    mock_sb.table.return_value.select.return_value.order.return_value \
        .limit.return_value.execute.return_value.data = [
        {"id": "r1", "agent_name": "research_agent"}
    ]
    resp = client_with_pool.get("/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "recent_runs" in body
    assert "cost_log" in body
    assert isinstance(body["recent_runs"], list)
    assert isinstance(body["cost_log"], list)


def test_get_status_returns_empty_lists_on_none(client_with_pool, mock_sb):
    mock_sb.table.return_value.select.return_value.order.return_value \
        .limit.return_value.execute.return_value.data = None
    resp = client_with_pool.get("/status")
    assert resp.status_code == 200
    assert resp.json()["recent_runs"] == []
    assert resp.json()["cost_log"] == []


def test_get_status_db_error_returns_500(client_with_pool, mock_sb):
    mock_sb.table.return_value.select.return_value.order.return_value \
        .limit.return_value.execute.side_effect = RuntimeError("db error")
    resp = client_with_pool.get("/status")
    assert resp.status_code == 500


# ─── POST /trigger/creation ────────────────────────────────────────────────────

def test_trigger_creation_enqueues_job():
    mock_pool = AsyncMock()
    mock_pool.enqueue_job.return_value = AsyncMock(job_id="job-creation-001")
    app.dependency_overrides[get_arq_pool] = lambda: mock_pool
    try:
        resp = client.post(
            "/trigger/creation",
            json={"idea_ids": ["idea-uuid-001", "idea-uuid-002"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent"] == "creation"
        assert data["idea_count"] == 2
        assert data["status"] == "enqueued"
    finally:
        app.dependency_overrides.pop(get_arq_pool, None)


def test_trigger_creation_returns_503_when_pool_none():
    app.dependency_overrides[get_arq_pool] = lambda: None
    try:
        resp = client.post(
            "/trigger/creation",
            json={"idea_ids": ["idea-uuid-001"]},
        )
        assert resp.status_code == 503
    finally:
        app.dependency_overrides.pop(get_arq_pool, None)


def test_trigger_creation_returns_422_when_empty_idea_ids():
    mock_pool = AsyncMock()
    app.dependency_overrides[get_arq_pool] = lambda: mock_pool
    try:
        resp = client.post("/trigger/creation", json={"idea_ids": []})
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_arq_pool, None)
