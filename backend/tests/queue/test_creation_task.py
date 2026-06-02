"""Tests for creation_agent_task orchestration loop."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import UUID

from app.queue.tasks import creation_agent_task


def _make_ctx():
    settings = MagicMock()
    settings.anthropic_api_key = "sk-test"
    settings.google_api_key = None
    settings.local_embedding_model = "BAAI/bge-base-en-v1.5"
    settings.claude_model_heavy = "claude-sonnet-4-5"
    settings.daily_cost_alert_usd = 10.0
    settings.slack_webhook_url = None
    settings.browser_sessions_dir = "~/.config/contentautomation/browser_sessions"
    supabase = MagicMock()
    return {"settings": settings, "supabase": supabase}


def _make_idea_data(idea_id="11111111-1111-1111-1111-111111111111", platform="linkedin"):
    return {
        "id": idea_id,
        "platform": platform,
        "angle": "SEBI new circular impacts AMCs",
        "edited_angle": None,
        "source_article_id": None,
        "agent_reasoning": "Relevant to Indian investors",
        "source_article_date": None,
        "approval_status": "approved",
        "score": 8.0,
        "recent_coverage_flag": False,
        "created_at": "2026-05-29T00:00:00+00:00",
        "updated_at": "2026-05-29T00:00:00+00:00",
    }


def _setup_batch_fetch(ctx, idea_data_list):
    """Wire supabase mock so .table().select().in_().execute() returns idea_data_list."""
    ctx["supabase"].table.return_value.select.return_value.in_.return_value.execute.return_value.data = idea_data_list


@pytest.mark.asyncio
async def test_creation_task_processes_one_idea():
    ctx = _make_ctx()
    idea_id = "11111111-1111-1111-1111-111111111111"
    _setup_batch_fetch(ctx, [_make_idea_data(idea_id)])

    with (
        patch("app.queue.tasks.AsyncAnthropic"),
        patch("app.agents.embedding.client.make_embed_client"),
        patch("app.agents.creation.content_generator.async_generate_content") as mock_gen,
        patch("app.agents.creation.finance_flags.detect_finance_flags", return_value=[]),
        patch("app.agents.creation.db_writer.write_draft", return_value="draft-uuid-001"),
        patch("app.agents.creation.db_writer.upsert_cost_log"),
        patch("app.agents.creation.brand_context.get_brand_context", return_value=""),
    ):
        from app.db.models import DraftCreate, Platform
        mock_gen.return_value = MagicMock(
            draft_create=DraftCreate(platform=Platform.LINKEDIN, content_text="Content.", agent_reasoning="Good."),
            input_tokens=100,
            output_tokens=200,
        )
        mock_gen.side_effect = None
        # async_generate_content is awaited — make it an AsyncMock
        mock_gen.side_effect = AsyncMock(return_value=MagicMock(
            draft_create=DraftCreate(platform=Platform.LINKEDIN, content_text="Content.", agent_reasoning="Good."),
            input_tokens=100,
            output_tokens=200,
        ))
        result = await creation_agent_task(ctx, idea_ids=[idea_id])

    assert result["status"] == "done"
    assert result["processed"] == 1
    assert result["drafts_created"] == 1
    assert result["failures"] == 0


@pytest.mark.asyncio
async def test_creation_task_counts_failure_when_draft_write_fails():
    ctx = _make_ctx()
    idea_id = "22222222-2222-2222-2222-222222222222"
    _setup_batch_fetch(ctx, [_make_idea_data(idea_id)])

    with (
        patch("app.queue.tasks.AsyncAnthropic"),
        patch("app.agents.embedding.client.make_embed_client"),
        patch("app.agents.creation.content_generator.async_generate_content") as mock_gen,
        patch("app.agents.creation.finance_flags.detect_finance_flags", return_value=[]),
        patch("app.agents.creation.db_writer.write_draft", return_value=None),
        patch("app.agents.creation.db_writer.upsert_cost_log"),
        patch("app.agents.creation.brand_context.get_brand_context", return_value=""),
    ):
        from app.db.models import DraftCreate, Platform
        mock_gen.side_effect = AsyncMock(return_value=MagicMock(
            draft_create=DraftCreate(platform=Platform.LINKEDIN, content_text="Content.", agent_reasoning="Good."),
            input_tokens=50,
            output_tokens=100,
        ))
        result = await creation_agent_task(ctx, idea_ids=[idea_id])

    assert result["status"] == "done"
    assert result["drafts_created"] == 0
    assert result["failures"] == 1


@pytest.mark.asyncio
async def test_creation_task_skips_idea_not_found():
    ctx = _make_ctx()
    # Batch-fetch returns empty — idea not found
    _setup_batch_fetch(ctx, [])

    with patch("app.queue.tasks.AsyncAnthropic"):
        result = await creation_agent_task(ctx, idea_ids=["nonexistent-id"])

    assert result["status"] == "done"
    assert result["processed"] == 1
    assert result["drafts_created"] == 0
    assert result["failures"] == 1


@pytest.mark.asyncio
async def test_creation_task_skips_when_generate_returns_none():
    ctx = _make_ctx()
    idea_id = "33333333-3333-3333-3333-333333333333"
    _setup_batch_fetch(ctx, [_make_idea_data(idea_id)])

    with (
        patch("app.queue.tasks.AsyncAnthropic"),
        patch("app.agents.embedding.client.make_embed_client"),
        patch("app.agents.creation.content_generator.async_generate_content") as mock_gen,
        patch("app.agents.creation.db_writer.upsert_cost_log"),
        patch("app.agents.creation.brand_context.get_brand_context", return_value=""),
    ):
        mock_gen.side_effect = AsyncMock(return_value=MagicMock(
            draft_create=None, input_tokens=20, output_tokens=5,
        ))
        result = await creation_agent_task(ctx, idea_ids=[idea_id])

    assert result["status"] == "done"
    assert result["drafts_created"] == 0
    assert result["failures"] == 1


@pytest.mark.asyncio
async def test_creation_task_handles_batch_fetch_exception():
    ctx = _make_ctx()
    # Batch-fetch itself raises — task returns error status
    ctx["supabase"].table.return_value.select.return_value.in_.return_value.execute.side_effect = RuntimeError("db down")

    with patch("app.queue.tasks.AsyncAnthropic"):
        result = await creation_agent_task(ctx, idea_ids=["some-id"])

    assert result["status"] == "error"
    assert result["failures"] == 1


@pytest.mark.asyncio
async def test_creation_task_empty_idea_ids_returns_done():
    ctx = _make_ctx()
    with patch("app.queue.tasks.AsyncAnthropic"):
        result = await creation_agent_task(ctx, idea_ids=[])

    assert result["status"] == "done"
    assert result["processed"] == 0
    assert result["drafts_created"] == 0
