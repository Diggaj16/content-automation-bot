# tests/queue/test_publishing_task.py
"""Tests for publishing_agent_task orchestration loop."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.queue.tasks import publishing_agent_task


def _make_ctx(with_redis=True):
    settings = MagicMock()
    supabase = MagicMock()
    ctx = {"settings": settings, "supabase": supabase}
    if with_redis:
        ctx["redis"] = AsyncMock()
    return ctx


def _make_draft_data(draft_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", platform="linkedin"):
    return {
        "id": draft_id,
        "platform": platform,
        "content_text": "LinkedIn post content here.",
        "agent_reasoning": "Good angle.",
        "source_idea_id": None,
        "finance_flags": [],
        "suggested_publish_time": None,
        "scheduled_at": "2026-05-29T00:00:00+00:00",
        "approval_status": "approved",
        "created_at": "2026-05-29T00:00:00+00:00",
        "updated_at": "2026-05-29T00:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_publishing_task_publishes_one_draft():
    ctx = _make_ctx()
    draft_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    ctx["supabase"].table.return_value.select.return_value.eq.return_value \
        .lte.return_value.execute.return_value.data = [_make_draft_data(draft_id)]

    with (
        patch("app.agents.publishing.poster.post_to_platform", return_value="linkedin-stub-abc"),
        patch("app.agents.publishing.db_writer.write_published_post", return_value="post-uuid-001"),
        patch("app.agents.publishing.db_writer.update_draft_published"),
    ):
        result = await publishing_agent_task(ctx)

    assert result["status"] == "done"
    assert result["processed"] == 1
    assert result["published"] == 1
    assert result["failures"] == 0


@pytest.mark.asyncio
async def test_publishing_task_schedules_analytics_jobs():
    ctx = _make_ctx(with_redis=True)
    draft_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    ctx["supabase"].table.return_value.select.return_value.eq.return_value \
        .lte.return_value.execute.return_value.data = [_make_draft_data(draft_id)]

    with (
        patch("app.agents.publishing.poster.post_to_platform", return_value="linkedin-stub-xyz"),
        patch("app.agents.publishing.db_writer.write_published_post", return_value="post-uuid-002"),
        patch("app.agents.publishing.db_writer.update_draft_published"),
    ):
        await publishing_agent_task(ctx)

    # 3 analytics jobs: 24h, 72h, 7d
    assert ctx["redis"].enqueue_job.call_count == 3


@pytest.mark.asyncio
async def test_publishing_task_no_redis_skips_analytics():
    ctx = _make_ctx(with_redis=False)
    draft_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    ctx["supabase"].table.return_value.select.return_value.eq.return_value \
        .lte.return_value.execute.return_value.data = [_make_draft_data(draft_id)]

    with (
        patch("app.agents.publishing.poster.post_to_platform", return_value="linkedin-stub-abc"),
        patch("app.agents.publishing.db_writer.write_published_post", return_value="post-uuid-003"),
        patch("app.agents.publishing.db_writer.update_draft_published"),
    ):
        result = await publishing_agent_task(ctx)

    assert result["status"] == "done"
    assert result["published"] == 1


@pytest.mark.asyncio
async def test_publishing_task_counts_failure_when_post_returns_none():
    ctx = _make_ctx()
    draft_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    ctx["supabase"].table.return_value.select.return_value.eq.return_value \
        .lte.return_value.execute.return_value.data = [_make_draft_data(draft_id)]

    with patch("app.agents.publishing.poster.post_to_platform", return_value=None):
        result = await publishing_agent_task(ctx)

    assert result["status"] == "done"
    assert result["published"] == 0
    assert result["failures"] == 1


@pytest.mark.asyncio
async def test_publishing_task_empty_drafts_returns_done():
    ctx = _make_ctx()
    ctx["supabase"].table.return_value.select.return_value.eq.return_value \
        .lte.return_value.execute.return_value.data = []

    result = await publishing_agent_task(ctx)

    assert result["status"] == "done"
    assert result["processed"] == 0
    assert result["published"] == 0


@pytest.mark.asyncio
async def test_publishing_task_returns_error_on_fetch_failure():
    ctx = _make_ctx()
    ctx["supabase"].table.return_value.select.return_value.eq.return_value \
        .lte.return_value.execute.side_effect = RuntimeError("db down")

    result = await publishing_agent_task(ctx)

    assert result["status"] == "error"
