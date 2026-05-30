# Email Subscriber Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CRUD endpoints for email subscribers and a token-based `/unsubscribe` public URL, then build a dedicated frontend page for managing subscribers.

**Architecture:** A new FastAPI router `subscribers.py` handles subscriber CRUD and the public unsubscribe route. The DB gets an `unsubscribe_token` column via a SQL migration run once in Supabase. A new Next.js page at `/subscribers` replaces the generic table browser for this table. `python-multipart` is not needed here (no file upload). The `unsubscribe_token` is a UUID auto-generated at insert time.

**Tech Stack:** Python 3.11, FastAPI, supabase-py, pytest + pytest-mock; Next.js 16, React 19, Tailwind 4.

---

## File Map

| Action | Path |
|--------|------|
| Create (SQL) | `backend/app/db/migrations/002_subscribers_token.sql` |
| Create | `backend/app/api/routers/subscribers.py` |
| Modify | `backend/app/api/main.py` |
| Create | `backend/tests/test_subscribers.py` |
| Create | `frontend/app/subscribers/page.tsx` |
| Modify | `frontend/app/lib/api.ts` |
| Modify | `frontend/app/layout.tsx` |

---

### Task 1 — DB migration

**Files:**
- Create: `backend/app/db/migrations/002_subscribers_token.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
-- backend/app/db/migrations/002_subscribers_token.sql
ALTER TABLE email_subscribers
ADD COLUMN IF NOT EXISTS unsubscribe_token TEXT UNIQUE DEFAULT gen_random_uuid()::TEXT;

UPDATE email_subscribers
SET unsubscribe_token = gen_random_uuid()::TEXT
WHERE unsubscribe_token IS NULL;
```

- [ ] **Step 2: Run in Supabase SQL Editor**

Open the Supabase dashboard → SQL Editor → paste the file content → Run.

Expected: `ALTER TABLE` success, `UPDATE 0` (or N if rows already exist).

- [ ] **Step 3: Verify the column exists**

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'email_subscribers' AND column_name = 'unsubscribe_token';
```

Expected: one row with `data_type = 'text'`, `is_nullable = 'YES'`.

---

### Task 2 — `subscribers.py` router

**Files:**
- Create: `backend/app/api/routers/subscribers.py`
- Create: `backend/tests/test_subscribers.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_subscribers.py
"""Tests for subscriber CRUD and token-based unsubscribe."""
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient


def _make_app(sb_mock):
    """Build a minimal FastAPI test app with subscriber router and overridden supabase dep."""
    from fastapi import FastAPI
    from app.api.routers.subscribers import router
    from app.api.deps import get_supabase

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_supabase] = lambda: sb_mock
    return TestClient(app)


# ── GET /subscribers ──────────────────────────────────────────────────────────

def test_list_subscribers_returns_rows():
    sb = MagicMock()
    sb.table.return_value.select.return_value.execute.return_value.data = [
        {"id": "aaa", "email": "a@b.com", "active": True}
    ]
    client = _make_app(sb)
    r = client.get("/subscribers")
    assert r.status_code == 200
    assert r.json()[0]["email"] == "a@b.com"


def test_list_subscribers_active_filter():
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    client = _make_app(sb)
    r = client.get("/subscribers?active=true")
    assert r.status_code == 200
    sb.table.return_value.select.return_value.eq.assert_called_once_with("active", True)


# ── POST /subscribers ─────────────────────────────────────────────────────────

def test_add_subscriber_success():
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "bbb", "email": "new@x.com", "active": True, "unsubscribe_token": "tok123"}
    ]
    client = _make_app(sb)
    r = client.post("/subscribers", json={"email": "new@x.com"})
    assert r.status_code == 201
    assert r.json()["email"] == "new@x.com"


def test_add_subscriber_duplicate_returns_409():
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "existing"}
    ]
    client = _make_app(sb)
    r = client.post("/subscribers", json={"email": "dup@x.com"})
    assert r.status_code == 409


# ── PATCH /subscribers/{id} ───────────────────────────────────────────────────

def test_update_subscriber_toggles_active():
    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {"id": "ccc", "active": False}
    ]
    client = _make_app(sb)
    r = client.patch("/subscribers/ccc", json={"active": False})
    assert r.status_code == 200
    assert r.json()["active"] is False


def test_update_subscriber_not_found_returns_404():
    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    client = _make_app(sb)
    r = client.patch("/subscribers/missing-id", json={"active": False})
    assert r.status_code == 404


# ── DELETE /subscribers/{id} ──────────────────────────────────────────────────

def test_delete_subscriber_soft_deletes():
    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {"id": "ddd", "active": False}
    ]
    client = _make_app(sb)
    r = client.delete("/subscribers/ddd")
    assert r.status_code == 200
    call_args = sb.table.return_value.update.call_args[0][0]
    assert call_args["active"] is False


# ── GET /unsubscribe ──────────────────────────────────────────────────────────

def test_unsubscribe_valid_token_returns_html():
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "eee", "email": "user@x.com"}
    ]
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{}]
    client = _make_app(sb)
    r = client.get("/unsubscribe?token=valid-token-here")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "unsubscribed" in r.text.lower()


def test_unsubscribe_invalid_token_returns_404_html():
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    client = _make_app(sb)
    r = client.get("/unsubscribe?token=bad-token")
    assert r.status_code == 404
    assert "text/html" in r.headers["content-type"]
```

- [ ] **Step 2: Run tests — expect ImportError**

```powershell
cd D:\Intern\content-automation-bot\backend
pytest tests/test_subscribers.py -v 2>&1 | Select-Object -First 20
```

Expected: `ModuleNotFoundError: No module named 'app.api.routers.subscribers'`

- [ ] **Step 3: Write `subscribers.py`**

```python
# backend/app/api/routers/subscribers.py
"""
Email subscriber management.

GET    /subscribers          — list all subscribers, optional ?active=true/false
POST   /subscribers          — add subscriber; 409 if email already exists
PATCH  /subscribers/{id}     — update name and/or active status
DELETE /subscribers/{id}     — soft-delete (sets active=false)
GET    /unsubscribe           — public token-based unsubscribe (no auth)
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from supabase import Client

from app.api.deps import get_supabase

router = APIRouter(tags=["Subscribers"])


class SubscriberCreate(BaseModel):
    email: str
    name: Optional[str] = None


class SubscriberUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None


@router.get("/subscribers")
def list_subscribers(
    active: Optional[bool] = Query(None),
    supabase: Client = Depends(get_supabase),
) -> list[dict]:
    try:
        q = supabase.table("email_subscribers").select("*")
        if active is not None:
            q = q.eq("active", active)
        resp = q.execute()
        return resp.data or []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/subscribers", status_code=201)
def add_subscriber(
    body: SubscriberCreate,
    supabase: Client = Depends(get_supabase),
) -> dict:
    # Check for duplicate
    try:
        existing = (
            supabase.table("email_subscribers")
            .select("id")
            .eq("email", body.email)
            .execute()
        )
        if existing.data:
            raise HTTPException(status_code=409, detail="Email already subscribed")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    try:
        payload: dict = {
            "email": body.email,
            "unsubscribe_token": str(uuid.uuid4()),
        }
        if body.name:
            payload["name"] = body.name
        resp = supabase.table("email_subscribers").insert(payload).execute()
        if not resp.data:
            raise HTTPException(status_code=500, detail="Insert returned no data")
        return resp.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/subscribers/{sub_id}")
def update_subscriber(
    sub_id: str,
    body: SubscriberUpdate,
    supabase: Client = Depends(get_supabase),
) -> dict:
    update: dict = {}
    if body.name is not None:
        update["name"] = body.name
    if body.active is not None:
        update["active"] = body.active
    if not update:
        raise HTTPException(status_code=422, detail="Nothing to update")
    try:
        resp = (
            supabase.table("email_subscribers")
            .update(update)
            .eq("id", sub_id)
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        return resp.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/subscribers/{sub_id}")
def delete_subscriber(
    sub_id: str,
    supabase: Client = Depends(get_supabase),
) -> dict:
    try:
        resp = (
            supabase.table("email_subscribers")
            .update({"active": False})
            .eq("id", sub_id)
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        return {"deleted": True, "id": sub_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe(
    token: str = Query(...),
    supabase: Client = Depends(get_supabase),
) -> HTMLResponse:
    try:
        resp = (
            supabase.table("email_subscribers")
            .select("id, email")
            .eq("unsubscribe_token", token)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not resp.data:
        return HTMLResponse(
            content=_html("Not Found", "This unsubscribe link is invalid or has already been used."),
            status_code=404,
        )

    sub = resp.data[0]
    try:
        supabase.table("email_subscribers").update({"active": False}).eq("id", sub["id"]).execute()
    except Exception:
        pass

    return HTMLResponse(
        content=_html(
            "Unsubscribed",
            f"<strong>{sub['email']}</strong> has been unsubscribed from all future emails.",
        ),
        status_code=200,
    )


def _html(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:480px;margin:80px auto;text-align:center;color:#1f2937}}
h1{{font-size:1.5rem;font-weight:600}}p{{color:#6b7280;margin-top:.75rem}}</style>
</head>
<body><h1>{title}</h1><p>{body}</p></body>
</html>"""
```

- [ ] **Step 4: Run tests — expect all pass**

```powershell
cd D:\Intern\content-automation-bot\backend
pytest tests/test_subscribers.py -v
```

Expected: `10 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routers/subscribers.py backend/tests/test_subscribers.py
git commit -m "feat: add email subscriber CRUD router with token unsubscribe"
```

---

### Task 3 — Register router in `main.py`

**Files:**
- Modify: `backend/app/api/main.py`

- [ ] **Step 1: Add subscriber router import and registration**

In `backend/app/api/main.py`, inside `create_app()`, after the tables router block, add:

```python
    from app.api.routers.subscribers import router as subscribers_router
    _app.include_router(subscribers_router)
```

- [ ] **Step 2: Smoke test**

```powershell
cd D:\Intern\content-automation-bot\backend
python -c "from app.api.main import app; routes = [r.path for r in app.routes]; print([r for r in routes if 'subscriber' in r or 'unsubscribe' in r])"
```

Expected: `['/subscribers', '/subscribers/{sub_id}', '/unsubscribe']` (or similar — must include all 5 paths).

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/main.py
git commit -m "feat: register subscribers router in main app"
```

---

### Task 4 — Frontend api.ts additions

**Files:**
- Modify: `frontend/app/lib/api.ts`

- [ ] **Step 1: Add subscriber type and functions**

In `frontend/app/lib/api.ts`, append before the `// --- Generic table browser ---` comment:

```typescript
// --- Subscribers ---

export interface Subscriber {
  id: string;
  email: string;
  name: string | null;
  subscribed_date: string;
  source: string;
  active: boolean;
  unsubscribe_token: string | null;
  created_at: string;
}

export async function getSubscribers(active?: boolean) {
  const qs = active !== undefined ? `?active=${active}` : "";
  return apiFetch<Subscriber[]>(`/subscribers${qs}`);
}

export async function addSubscriber(data: { email: string; name?: string }) {
  return apiFetch<Subscriber>("/subscribers", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateSubscriber(
  id: string,
  data: { name?: string; active?: boolean }
) {
  return apiFetch<Subscriber>(`/subscribers/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteSubscriber(id: string) {
  return apiFetch<{ deleted: boolean; id: string }>(`/subscribers/${id}`, {
    method: "DELETE",
  });
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```powershell
cd D:\Intern\content-automation-bot\frontend
npx tsc --noEmit 2>&1 | Select-Object -First 20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/lib/api.ts
git commit -m "feat: add subscriber API functions to frontend api.ts"
```

---

### Task 5 — Frontend subscribers page

**Files:**
- Create: `frontend/app/subscribers/page.tsx`

- [ ] **Step 1: Write the page**

```tsx
// frontend/app/subscribers/page.tsx
"use client";

import { useState, useEffect } from "react";
import {
  getSubscribers,
  addSubscriber,
  updateSubscriber,
  deleteSubscriber,
  type Subscriber,
} from "../lib/api";

export default function SubscribersPage() {
  const [subscribers, setSubscribers] = useState<Subscriber[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // Add form state
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const fetchSubscribers = async () => {
    setLoading(true);
    setError(null);
    try {
      setSubscribers(await getSubscribers());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSubscribers();
  }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setAdding(true);
    setAddError(null);
    try {
      const sub = await addSubscriber({ email: email.trim(), name: name.trim() || undefined });
      setSubscribers((prev) => [sub, ...prev]);
      setEmail("");
      setName("");
      showToast("Subscriber added.");
    } catch (e: unknown) {
      setAddError(e instanceof Error ? e.message : "Failed to add");
    } finally {
      setAdding(false);
    }
  };

  const handleToggle = async (sub: Subscriber) => {
    try {
      const updated = await updateSubscriber(sub.id, { active: !sub.active });
      setSubscribers((prev) => prev.map((s) => (s.id === sub.id ? updated : s)));
      showToast(`${sub.email} ${updated.active ? "activated" : "deactivated"}.`);
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "Failed to update");
    }
  };

  const handleDelete = async (sub: Subscriber) => {
    try {
      await deleteSubscriber(sub.id);
      setSubscribers((prev) => prev.filter((s) => s.id !== sub.id));
      showToast(`${sub.email} removed.`);
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "Failed to delete");
    }
  };

  const unsubscribeLink = (token: string | null) => {
    if (!token) return null;
    return `${window.location.origin}/unsubscribe?token=${token}`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Email Subscribers</h1>
          <p className="text-sm text-gray-500 mt-1">
            {loading ? "Loading..." : `${subscribers.length} subscriber${subscribers.length !== 1 ? "s" : ""}`}
          </p>
        </div>
        <button
          onClick={fetchSubscribers}
          disabled={loading}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          Refresh
        </button>
      </div>

      {toast && (
        <div className="px-4 py-3 rounded-md text-sm bg-green-50 text-green-700 border border-green-200">
          {toast}
        </div>
      )}

      {/* Add subscriber form */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Add Subscriber</h2>
        <form onSubmit={handleAdd} className="flex gap-3 flex-wrap items-end">
          <div className="flex-1 min-w-48">
            <label className="block text-xs text-gray-600 mb-1">Email *</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="someone@example.com"
            />
          </div>
          <div className="flex-1 min-w-36">
            <label className="block text-xs text-gray-600 mb-1">Name (optional)</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Rahul"
            />
          </div>
          <button
            type="submit"
            disabled={adding}
            className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {adding ? "Adding..." : "Add"}
          </button>
        </form>
        {addError && <p className="text-xs text-red-600 mt-2">{addError}</p>}
      </div>

      {/* Subscribers table */}
      {error && (
        <div className="px-4 py-3 rounded-md text-sm bg-red-50 text-red-700 border border-red-200">
          {error}
        </div>
      )}

      {!loading && !error && subscribers.length === 0 && (
        <div className="text-center py-12 text-gray-500 text-sm">No subscribers yet.</div>
      )}

      {subscribers.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Email</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Name</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Subscribed</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Unsubscribe Link</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {subscribers.map((sub) => {
                const link = unsubscribeLink(sub.unsubscribe_token);
                return (
                  <tr key={sub.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-900 font-medium">{sub.email}</td>
                    <td className="px-4 py-3 text-gray-600">{sub.name ?? "—"}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                          sub.active
                            ? "bg-green-100 text-green-700"
                            : "bg-gray-100 text-gray-500"
                        }`}
                      >
                        {sub.active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {sub.subscribed_date
                        ? new Date(sub.subscribed_date).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {link ? (
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(link);
                            showToast("Link copied!");
                          }}
                          className="text-blue-600 hover:underline"
                        >
                          Copy link
                        </button>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleToggle(sub)}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          {sub.active ? "Deactivate" : "Activate"}
                        </button>
                        <button
                          onClick={() => handleDelete(sub)}
                          className="text-xs text-red-600 hover:underline"
                        >
                          Remove
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```powershell
cd D:\Intern\content-automation-bot\frontend
npx tsc --noEmit 2>&1 | Select-Object -First 20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/subscribers/page.tsx
git commit -m "feat: add subscribers management page"
```

---

### Task 6 — Add nav link in layout.tsx

**Files:**
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Add Subscribers link under Pipeline and Orchestrator link under Main**

In `frontend/app/layout.tsx`, update the `NAV_SECTIONS` array. Replace the Pipeline section and add the Orchestrator link to Main:

Main section — add before Dashboard:
```typescript
{ href: "/orchestrator", text: "Orchestrator" },
```

Pipeline section — add Subscribers after Published Posts:
```typescript
{ href: "/subscribers", text: "Subscribers" },
```

The updated `NAV_SECTIONS` should look like:
```typescript
const NAV_SECTIONS = [
  {
    label: "Main",
    links: [
      { href: "/orchestrator", text: "Orchestrator" },
      { href: "/", text: "Dashboard" },
      { href: "/ideas", text: "Gate 1 — Ideas" },
      { href: "/drafts", text: "Gate 2 — Drafts" },
    ],
  },
  {
    label: "Pipeline",
    links: [
      { href: "/tables/curated_sites", text: "Curated Sites" },
      { href: "/tables/raw_content", text: "Raw Content" },
      { href: "/tables/ideas", text: "Ideas (all)" },
      { href: "/tables/drafts", text: "Drafts (all)" },
      { href: "/tables/published_posts", text: "Published Posts" },
      { href: "/subscribers", text: "Subscribers" },
    ],
  },
  {
    label: "Analytics & Learning",
    links: [
      { href: "/tables/content_analytics", text: "Content Analytics" },
      { href: "/tables/style_guide", text: "Style Guide" },
      { href: "/tables/topic_performance_model", text: "Topic Model" },
    ],
  },
  {
    label: "Data Stores",
    links: [
      { href: "/tables/brand_memory", text: "Brand Memory" },
      { href: "/knowledge-base", text: "Knowledge Base" },
      { href: "/tables/email_subscribers", text: "Email Subscribers (raw)" },
      { href: "/tables/user_decision_summaries", text: "Decision Summaries" },
    ],
  },
  {
    label: "Ops",
    links: [
      { href: "/tables/run_logs", text: "Run Logs" },
      { href: "/tables/site_health_log", text: "Site Health" },
      { href: "/tables/cost_log", text: "Cost Log" },
    ],
  },
];
```

Note: The Knowledge Base link under Data Stores changes from `/tables/knowledge_base` to `/knowledge-base` (the dedicated upload page created in the KB ingestion plan).

- [ ] **Step 2: Verify TypeScript compiles**

```powershell
cd D:\Intern\content-automation-bot\frontend
npx tsc --noEmit 2>&1 | Select-Object -First 20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/layout.tsx
git commit -m "feat: add Orchestrator, Subscribers, Knowledge Base nav links"
```
