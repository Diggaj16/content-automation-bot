# tests/api/test_ideas.py
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
