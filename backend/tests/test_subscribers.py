"""Tests for subscriber CRUD and token-based unsubscribe."""
from unittest.mock import MagicMock
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
