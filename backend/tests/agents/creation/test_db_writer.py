# tests/agents/creation/test_db_writer.py
"""Tests for creation db_writer."""
from unittest.mock import MagicMock
from uuid import UUID

from app.agents.creation.db_writer import write_draft
from app.db.models import DraftCreate, Platform


def _make_draft_create(platform: str = "linkedin") -> DraftCreate:
    return DraftCreate(
        platform=Platform(platform),
        content_text="Test draft content for LinkedIn.",
        agent_reasoning="Strong angle for the platform.",
        source_idea_id=UUID("00000000-0000-0000-0000-000000000042"),
        finance_flags=[],
    )


def test_write_draft_returns_id_on_success():
    sb = MagicMock()
    sb.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "draft-uuid-001"}]
    result = write_draft(sb, _make_draft_create())
    assert result == "draft-uuid-001"


def test_write_draft_returns_none_on_empty_data():
    sb = MagicMock()
    sb.table.return_value.upsert.return_value.execute.return_value.data = []
    result = write_draft(sb, _make_draft_create())
    assert result is None


def test_write_draft_returns_none_on_exception():
    sb = MagicMock()
    sb.table.return_value.upsert.return_value.execute.side_effect = RuntimeError("DB error")
    result = write_draft(sb, _make_draft_create("twitter"))
    assert result is None


def test_write_draft_serialises_platform_as_string():
    sb = MagicMock()
    sb.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "x"}]
    write_draft(sb, _make_draft_create("twitter"))
    payload = sb.table.return_value.upsert.call_args[0][0]
    assert payload["platform"] == "twitter"
    assert isinstance(payload["platform"], str)


def test_write_draft_serialises_finance_flags_as_list():
    from app.db.models import FinanceFlag
    draft = DraftCreate(
        platform=Platform.LINKEDIN,
        content_text="Post with flags.",
        agent_reasoning="Test.",
        finance_flags=[FinanceFlag(flag_type="investment_advice", content="buy now", context="you should buy now")],
    )
    sb = MagicMock()
    sb.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "y"}]
    write_draft(sb, draft)
    payload = sb.table.return_value.upsert.call_args[0][0]
    assert isinstance(payload["finance_flags"], list)
    assert payload["finance_flags"][0]["flag_type"] == "investment_advice"


def test_write_draft_none_idea_id_serialised_as_none():
    draft = DraftCreate(
        platform=Platform.BLOG,
        content_text="Blog content here.",
        agent_reasoning="Blog angle.",
        source_idea_id=None,
    )
    sb = MagicMock()
    sb.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "z"}]
    write_draft(sb, draft)
    payload = sb.table.return_value.upsert.call_args[0][0]
    assert payload["source_idea_id"] is None
