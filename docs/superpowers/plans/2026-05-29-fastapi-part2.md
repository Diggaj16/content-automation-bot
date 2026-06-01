# FastAPI App Implementation Plan — Part 2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the triggers + status router (POST /trigger/research, POST /trigger/scoring, GET /status) and wire it into the existing FastAPI app.

**Architecture:** Trigger endpoints depend on the arq pool from `app.state`. Pool is injected via `get_arq_pool` dep. If Redis is unavailable (`pool is None`), trigger endpoints return HTTP 503. Tests override `get_arq_pool` dependency with a mock to avoid needing Redis.

**Tech Stack:** FastAPI (existing), arq (existing), Supabase (existing)

**Pre-requisite:** `backend/app/api/main.py`, `backend/app/api/deps.py`, and both routers from Part 1 are already implemented.

---

### Task 28: Triggers and status router

**Files:**
- Create: `backend/app/api/routers/triggers.py`
- Modify: `backend/app/api/main.py` — include triggers router
- Create: `backend/tests/api/test_triggers.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/api/test_triggers.py
"""Tests for trigger and system-status endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.deps import get_supabase, get_arq_pool


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
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/api/test_triggers.py -v
```
Expected: ERRORS — ImportError (triggers.py doesn't exist yet)

- [ ] **Step 3: Create `backend/app/api/routers/triggers.py`**

```python
"""
Agent trigger endpoints and system status.

POST /trigger/research  — manually enqueue research_agent_task
POST /trigger/scoring   — manually enqueue scoring_agent_task
GET  /status            — recent run_logs + daily cost summary
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.api.deps import get_arq_pool, get_supabase

router = APIRouter(tags=["System"])


@router.post("/trigger/research")
async def trigger_research(pool=Depends(get_arq_pool)) -> dict:
    """Manually enqueue the research agent. Returns 503 if Redis is unavailable."""
    if pool is None:
        raise HTTPException(
            status_code=503, detail="Queue unavailable — Redis not connected"
        )
    job = await pool.enqueue_job("research_agent_task")
    return {
        "job_id": job.job_id if job else None,
        "status": "enqueued",
        "agent": "research",
    }


@router.post("/trigger/scoring")
async def trigger_scoring(pool=Depends(get_arq_pool)) -> dict:
    """Manually enqueue the scoring agent. Returns 503 if Redis is unavailable."""
    if pool is None:
        raise HTTPException(
            status_code=503, detail="Queue unavailable — Redis not connected"
        )
    job = await pool.enqueue_job("scoring_agent_task")
    return {
        "job_id": job.job_id if job else None,
        "status": "enqueued",
        "agent": "scoring",
    }


@router.get("/status")
def get_status(
    limit: int = Query(default=10, ge=1, le=100),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Return recent agent run logs and the daily cost summary."""
    try:
        logs_resp = (
            supabase.table("run_logs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        cost_resp = (
            supabase.table("cost_log")
            .select("*")
            .order("date", desc=True)
            .limit(30)
            .execute()
        )
        return {
            "recent_runs": logs_resp.data or [],
            "cost_log": cost_resp.data or [],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
```

- [ ] **Step 4: Include triggers router in `backend/app/api/main.py`**

After the existing drafts_router include, add:
```python
    from app.api.routers.triggers import router as triggers_router
    _app.include_router(triggers_router)
```

The end of `create_app()` now reads:
```python
    from app.api.routers.ideas import router as ideas_router
    _app.include_router(ideas_router)

    from app.api.routers.drafts import router as drafts_router
    _app.include_router(drafts_router)

    from app.api.routers.triggers import router as triggers_router
    _app.include_router(triggers_router)

    return _app
```

- [ ] **Step 5: Run test to verify it passes**

```
pytest tests/api/test_triggers.py -v
```
Expected: 7 PASSED

- [ ] **Step 6: Run full suite**

```
pytest tests/ --ignore=tests/agents/research/test_install.py -q
```
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add app/api/routers/triggers.py app/api/main.py tests/api/test_triggers.py
git commit -m "feat: add triggers and status router"
```
