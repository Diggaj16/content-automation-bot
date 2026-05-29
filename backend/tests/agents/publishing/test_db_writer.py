# tests/agents/publishing/test_db_writer.py
"""Tests for publishing db_writer."""
from unittest.mock import MagicMock
from uuid import UUID

from app.agents.publishing.db_writer import write_published_post, update_draft_published

_DRAFT_ID = UUID("00000000-0000-0000-0000-000000000001")


def test_write_published_post_returns_id():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "post-uuid-001"}]
    result = write_published_post(sb, "linkedin", "linkedin-stub-abc123", _DRAFT_ID)
    assert result == "post-uuid-001"


def test_write_published_post_returns_none_on_empty_data():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = []
    result = write_published_post(sb, "twitter", "twitter-stub-xyz", _DRAFT_ID)
    assert result is None


def test_write_published_post_returns_none_on_exception():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.side_effect = RuntimeError("DB error")
    result = write_published_post(sb, "blog", "blog-stub-123", None)
    assert result is None


def test_write_published_post_serialises_draft_id_as_string():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "x"}]
    write_published_post(sb, "linkedin", "post-id", _DRAFT_ID)
    payload = sb.table.return_value.insert.call_args[0][0]
    assert payload["draft_id"] == str(_DRAFT_ID)
    assert isinstance(payload["draft_id"], str)


def test_write_published_post_none_draft_id_passed_as_none():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "x"}]
    write_published_post(sb, "email", "email-id", None)
    payload = sb.table.return_value.insert.call_args[0][0]
    assert payload["draft_id"] is None


def test_update_draft_published_calls_update():
    sb = MagicMock()
    update_draft_published(sb, _DRAFT_ID)
    sb.table.assert_called_with("drafts")
    update_call = sb.table.return_value.update.call_args[0][0]
    assert update_call["approval_status"] == "published"


def test_update_draft_published_never_raises():
    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.side_effect = RuntimeError("DB error")
    update_draft_published(sb, _DRAFT_ID)  # should not raise
