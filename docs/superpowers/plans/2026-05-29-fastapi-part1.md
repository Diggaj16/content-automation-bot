# FastAPI App Implementation Plan — Part 1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the FastAPI application foundation with dependency injection, and the Gate 1 (ideas) + Gate 2 (drafts) approval routers.

**Architecture:** FastAPI factory function (`create_app`) with async lifespan for arq pool management. Centralised deps.py for supabase and arq pool injection. Each router is a thin HTTP adapter over Supabase table reads/writes. Dependency overrides used in tests — no real DB or Redis required.

**Tech Stack:** FastAPI 0.111+, uvicorn, Supabase client (existing), arq (existing), httpx (existing, used by TestClient)

---

### Task 25: FastAPI app foundation

**Files:**
- Modify: `backend/pyproject.toml` — add fastapi + uvicorn
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/deps.py`
- Create: `backend/app/api/main.py`
- Create: `backend/tests/api/__init__.py`
- Create: `backend/tests/api/test_main.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/api/test_main.py
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.main import app, create_app


def test_create_app_returns_fastapi_instance():
    assert isinstance(app, FastAPI)


def test_app_title():
    assert app.title == "Content Automation API"


def test_unknown_path_returns_404():
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/nonexistent-path-xyz")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run from `backend/` with venv active:
```
pytest tests/api/test_main.py -v
```
Expected: ERROR — ModuleNotFoundError (app.api.main does not exist yet)

- [ ] **Step 3: Add fastapi + uvicorn to `backend/pyproject.toml`**

In the `dependencies` list, add these two lines after the existing entries:
```
"fastapi>=0.111.0",
"uvicorn[standard]>=0.29.0",
```

Then install:
```
pip install -e ".[dev]"
```

- [ ] **Step 4: Create `backend/app/api/__init__.py`**

Empty file (just a newline).

- [ ] **Step 5: Create `backend/app/api/deps.py`**

```python
"""
FastAPI dependency-injection helpers.
Centralised so tests can override individual deps cleanly via
app.dependency_overrides[original_dep] = lambda: mock_value.
"""
from fastapi import Request
from supabase import Client

from app.config import Settings, get_settings as _get_settings
from app.db.client import get_supabase_client


def get_settings() -> Settings:
    return _get_settings()


def get_supabase() -> Client:
    return get_supabase_client()


def get_arq_pool(request: Request):
    """Returns the arq pool stored in app.state, or None if Redis is unavailable."""
    return getattr(request.app.state, "arq_pool", None)
```

- [ ] **Step 6: Create `backend/app/api/main.py`**

```python
"""
FastAPI application — human approval gates and agent trigger endpoints.

Run locally (from backend/ with venv active):
    uvicorn app.api.main:app --reload --port 8000
"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise shared state on startup; clean up on shutdown."""
    app.state.arq_pool = None
    try:
        import arq
        from app.queue.worker import WorkerSettings
        pool = await arq.create_pool(WorkerSettings.redis_settings)
        app.state.arq_pool = pool
        logger.info("api: arq pool connected")
    except Exception as exc:
        logger.warning(
            f"api: arq pool unavailable — trigger endpoints will return 503 | err={exc}"
        )

    yield

    if app.state.arq_pool is not None:
        await app.state.arq_pool.close()
        logger.info("api: arq pool closed")


def create_app() -> FastAPI:
    """
    Factory function — call this to obtain a configured FastAPI instance.
    Importable without side-effects (lifespan runs only when serving).
    """
    _app = FastAPI(
        title="Content Automation API",
        description="Human approval gates and agent trigger endpoints",
        version="0.1.0",
        lifespan=lifespan,
    )

    _app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],    # tighten in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers included in later tasks (ideas, drafts, triggers)

    return _app


app = create_app()
```

- [ ] **Step 7: Create `backend/tests/api/__init__.py`**

Empty file (just a newline).

- [ ] **Step 8: Run test to verify it passes**

```
pytest tests/api/test_main.py -v
```
Expected: 3 PASSED

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml app/api/__init__.py app/api/deps.py app/api/main.py tests/api/__init__.py tests/api/test_main.py
git commit -m "feat: add FastAPI app foundation with deps and lifespan"
```

---

### Task 26: Ideas router (Gate 1)

**Files:**
- Create: `backend/app/api/routers/__init__.py`
- Create: `backend/app/api/routers/ideas.py`
- Modify: `backend/app/api/main.py` — include ideas router
- Create: `backend/tests/api/test_ideas.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/api/test_ideas.py
"""Tests for Gate 1 — ideas approval router."""
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.deps import get_supabase


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_sb():
    return MagicMock()


@pytest.fixture
def client(mock_sb):
    app.dependency_overrides[get_supabase] = lambda: mock_sb
    return TestClient(app, raise_server_exceptions=False)


# ─── GET /ideas ────────────────────────────────────────────────────────────────

def test_list_ideas_default_status_is_pending(client, mock_sb):
    mock_sb.table.return_value.select.return_value.limit.return_value \
        .eq.return_value.execute.return_value.data = [
        {"id": "abc", "approval_status": "pending_approval", "angle": "test"}
    ]
    resp = client.get("/ideas")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["approval_status"] == "pending_approval"


def test_list_ideas_custom_status(client, mock_sb):
    mock_sb.table.return_value.select.return_value.limit.return_value \
        .eq.return_value.execute.return_value.data = []
    resp = client.get("/ideas?status=approved")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_ideas_returns_empty_list_on_none_data(client, mock_sb):
    mock_sb.table.return_value.select.return_value.limit.return_value \
        .eq.return_value.execute.return_value.data = None
    resp = client.get("/ideas")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_ideas_db_error_returns_500(client, mock_sb):
    mock_sb.table.return_value.select.return_value.limit.return_value \
        .eq.return_value.execute.side_effect = RuntimeError("db error")
    resp = client.get("/ideas")
    assert resp.status_code == 500


# ─── PATCH /ideas/{idea_id} ────────────────────────────────────────────────────

def test_approve_idea_returns_updated_row(client, mock_sb):
    mock_sb.table.return_value.update.return_value.eq.return_value.execute \
        .return_value.data = [{"id": "abc", "approval_status": "approved"}]
    resp = client.patch(
        "/ideas/00000000-0000-0000-0000-000000000001",
        json={"approval_status": "approved"},
    )
    assert resp.status_code == 200
    assert resp.json()["approval_status"] == "approved"


def test_approve_idea_with_edited_angle(client, mock_sb):
    mock_sb.table.return_value.update.return_value.eq.return_value.execute \
        .return_value.data = [
        {"id": "abc", "approval_status": "approved", "edited_angle": "new angle"}
    ]
    resp = client.patch(
        "/ideas/00000000-0000-0000-0000-000000000001",
        json={"approval_status": "approved", "edited_angle": "new angle"},
    )
    assert resp.status_code == 200
    assert resp.json()["edited_angle"] == "new angle"


def test_approve_idea_not_found_returns_404(client, mock_sb):
    mock_sb.table.return_value.update.return_value.eq.return_value.execute \
        .return_value.data = []
    resp = client.patch(
        "/ideas/00000000-0000-0000-0000-000000000001",
        json={"approval_status": "rejected"},
    )
    assert resp.status_code == 404


def test_approve_idea_db_error_returns_500(client, mock_sb):
    mock_sb.table.return_value.update.return_value.eq.return_value.execute \
        .side_effect = RuntimeError("db error")
    resp = client.patch(
        "/ideas/00000000-0000-0000-0000-000000000001",
        json={"approval_status": "approved"},
    )
    assert resp.status_code == 500


def test_approve_idea_invalid_uuid_returns_422(client, mock_sb):
    resp = client.patch(
        "/ideas/not-a-valid-uuid",
        json={"approval_status": "approved"},
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/api/test_ideas.py -v
```
Expected: ERRORS — ImportError (routers/ doesn't exist yet)

- [ ] **Step 3: Create `backend/app/api/routers/__init__.py`**

Empty file (just a newline).

- [ ] **Step 4: Create `backend/app/api/routers/ideas.py`**

```python
"""
Gate 1 — Ideas approval router.

GET  /ideas            — list ideas filtered by approval_status (default: pending_approval)
PATCH /ideas/{idea_id} — approve or reject an idea, optionally with an edited angle
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.api.deps import get_supabase
from app.db.models import ApprovalStatus, IdeaApproval

router = APIRouter(prefix="/ideas", tags=["Gate 1 — Ideas"])


@router.get("")
def list_ideas(
    status: Optional[str] = Query(
        default=ApprovalStatus.PENDING.value,
        description="Filter by approval_status. Pass empty string to skip filter.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    supabase: Client = Depends(get_supabase),
) -> list[dict]:
    """Return ideas filtered by approval status."""
    try:
        query = supabase.table("ideas").select("*").limit(limit)
        if status:
            query = query.eq("approval_status", status)
        resp = query.execute()
        return resp.data or []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/{idea_id}")
def approve_idea(
    idea_id: UUID,
    payload: IdeaApproval,
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Approve or reject an idea. Optionally supply an edited_angle."""
    update: dict = {"approval_status": payload.approval_status.value}
    if payload.edited_angle is not None:
        update["edited_angle"] = payload.edited_angle

    try:
        resp = (
            supabase.table("ideas")
            .update(update)
            .eq("id", str(idea_id))
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Idea not found")
        return resp.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
```

- [ ] **Step 5: Include ideas router in `backend/app/api/main.py`**

Add these two lines at the end of `create_app()`, just before `return _app`:

```python
    from app.api.routers.ideas import router as ideas_router
    _app.include_router(ideas_router)
```

The `create_app` function body now ends with:
```python
    # ...existing middleware...

    from app.api.routers.ideas import router as ideas_router
    _app.include_router(ideas_router)

    return _app
```

- [ ] **Step 6: Run test to verify it passes**

```
pytest tests/api/test_ideas.py -v
```
Expected: 9 PASSED

- [ ] **Step 7: Run full suite to check nothing regressed**

```
pytest tests/ --ignore=tests/agents/research/test_install.py -q
```
Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add app/api/routers/__init__.py app/api/routers/ideas.py app/api/main.py tests/api/test_ideas.py
git commit -m "feat: add ideas approval router (Gate 1)"
```

---

### Task 27: Drafts router (Gate 2)

**Files:**
- Create: `backend/app/api/routers/drafts.py`
- Modify: `backend/app/api/main.py` — include drafts router
- Create: `backend/tests/api/test_drafts.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/api/test_drafts.py
"""Tests for Gate 2 — drafts approval router."""
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.deps import get_supabase


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_sb():
    return MagicMock()


@pytest.fixture
def client(mock_sb):
    app.dependency_overrides[get_supabase] = lambda: mock_sb
    return TestClient(app, raise_server_exceptions=False)


# ─── GET /drafts ───────────────────────────────────────────────────────────────

def test_list_drafts_default_status_is_pending(client, mock_sb):
    mock_sb.table.return_value.select.return_value.limit.return_value \
        .eq.return_value.execute.return_value.data = [
        {"id": "d1", "approval_status": "pending_approval", "content_text": "draft..."}
    ]
    resp = client.get("/drafts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["approval_status"] == "pending_approval"


def test_list_drafts_custom_status(client, mock_sb):
    mock_sb.table.return_value.select.return_value.limit.return_value \
        .eq.return_value.execute.return_value.data = []
    resp = client.get("/drafts?status=approved")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_drafts_returns_empty_list_on_none_data(client, mock_sb):
    mock_sb.table.return_value.select.return_value.limit.return_value \
        .eq.return_value.execute.return_value.data = None
    resp = client.get("/drafts")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_drafts_db_error_returns_500(client, mock_sb):
    mock_sb.table.return_value.select.return_value.limit.return_value \
        .eq.return_value.execute.side_effect = RuntimeError("db error")
    resp = client.get("/drafts")
    assert resp.status_code == 500


# ─── PATCH /drafts/{draft_id} ─────────────────────────────────────────────────

def test_approve_draft_returns_updated_row(client, mock_sb):
    mock_sb.table.return_value.update.return_value.eq.return_value.execute \
        .return_value.data = [{"id": "d1", "approval_status": "approved"}]
    resp = client.patch(
        "/drafts/00000000-0000-0000-0000-000000000001",
        json={"approval_status": "approved"},
    )
    assert resp.status_code == 200
    assert resp.json()["approval_status"] == "approved"


def test_approve_draft_with_edited_content(client, mock_sb):
    mock_sb.table.return_value.update.return_value.eq.return_value.execute \
        .return_value.data = [
        {"id": "d1", "approval_status": "approved", "content_text": "edited content"}
    ]
    resp = client.patch(
        "/drafts/00000000-0000-0000-0000-000000000001",
        json={"approval_status": "approved", "content_text": "edited content"},
    )
    assert resp.status_code == 200
    assert resp.json()["content_text"] == "edited content"


def test_approve_draft_with_scheduled_at(client, mock_sb):
    mock_sb.table.return_value.update.return_value.eq.return_value.execute \
        .return_value.data = [
        {"id": "d1", "approval_status": "approved", "scheduled_at": "2026-06-01T09:00:00+00:00"}
    ]
    resp = client.patch(
        "/drafts/00000000-0000-0000-0000-000000000001",
        json={"approval_status": "approved", "scheduled_at": "2026-06-01T09:00:00Z"},
    )
    assert resp.status_code == 200


def test_approve_draft_not_found_returns_404(client, mock_sb):
    mock_sb.table.return_value.update.return_value.eq.return_value.execute \
        .return_value.data = []
    resp = client.patch(
        "/drafts/00000000-0000-0000-0000-000000000001",
        json={"approval_status": "rejected"},
    )
    assert resp.status_code == 404


def test_approve_draft_db_error_returns_500(client, mock_sb):
    mock_sb.table.return_value.update.return_value.eq.return_value.execute \
        .side_effect = RuntimeError("db error")
    resp = client.patch(
        "/drafts/00000000-0000-0000-0000-000000000001",
        json={"approval_status": "approved"},
    )
    assert resp.status_code == 500


def test_approve_draft_invalid_uuid_returns_422(client, mock_sb):
    resp = client.patch(
        "/drafts/not-a-valid-uuid",
        json={"approval_status": "approved"},
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/api/test_drafts.py -v
```
Expected: ERRORS — ImportError (drafts.py doesn't exist yet)

- [ ] **Step 3: Create `backend/app/api/routers/drafts.py`**

```python
"""
Gate 2 — Drafts approval router.

GET  /drafts             — list drafts filtered by approval_status (default: pending_approval)
PATCH /drafts/{draft_id} — approve or reject a draft, optionally with edited content + schedule
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.api.deps import get_supabase
from app.db.models import DraftApproval, DraftStatus

router = APIRouter(prefix="/drafts", tags=["Gate 2 — Drafts"])


@router.get("")
def list_drafts(
    status: Optional[str] = Query(
        default=DraftStatus.PENDING.value,
        description="Filter by approval_status. Pass empty string to skip filter.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    supabase: Client = Depends(get_supabase),
) -> list[dict]:
    """Return drafts filtered by approval status."""
    try:
        query = supabase.table("drafts").select("*").limit(limit)
        if status:
            query = query.eq("approval_status", status)
        resp = query.execute()
        return resp.data or []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/{draft_id}")
def approve_draft(
    draft_id: UUID,
    payload: DraftApproval,
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Approve or reject a draft. Optionally supply edited content_text and/or scheduled_at."""
    update: dict = {"approval_status": payload.approval_status.value}
    if payload.content_text is not None:
        update["content_text"] = payload.content_text
    if payload.scheduled_at is not None:
        update["scheduled_at"] = payload.scheduled_at.isoformat()

    try:
        resp = (
            supabase.table("drafts")
            .update(update)
            .eq("id", str(draft_id))
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Draft not found")
        return resp.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
```

- [ ] **Step 4: Include drafts router in `backend/app/api/main.py`**

After the existing ideas_router include, add:
```python
    from app.api.routers.drafts import router as drafts_router
    _app.include_router(drafts_router)
```

The end of `create_app()` now reads:
```python
    from app.api.routers.ideas import router as ideas_router
    _app.include_router(ideas_router)

    from app.api.routers.drafts import router as drafts_router
    _app.include_router(drafts_router)

    return _app
```

- [ ] **Step 5: Run test to verify it passes**

```
pytest tests/api/test_drafts.py -v
```
Expected: 9 PASSED

- [ ] **Step 6: Run full suite**

```
pytest tests/ --ignore=tests/agents/research/test_install.py -q
```
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add app/api/routers/drafts.py app/api/main.py tests/api/test_drafts.py
git commit -m "feat: add drafts approval router (Gate 2)"
```
