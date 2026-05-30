# backend/tests/queue/test_analytics_task.py
"""Tests for analytics_agent_task orchestration loop."""
import pytest
from unittest.mock import MagicMock, patch

from app.queue.tasks import analytics_agent_task


def _make_ctx():
    settings = MagicMock()
    supabase = MagicMock()
    return {"settings": settings, "supabase": supabase}


def _make_post_data(post_id="post-uuid-001", platform="linkedin"):
    return {
        "id": post_id,
        "platform": platform,
        "post_identifier": f"{platform}-stub-abc123",
        "published_at": "2026-05-28T10:00:00+00:00",
        "draft_id": None,
        "created_at": "2026-05-28T10:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_analytics_task_stores_24h_metrics():
    ctx = _make_ctx()
    post_id = "post-uuid-001"
    ctx["supabase"].table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        _make_post_data(post_id)
    ]

    with (
        patch("app.agents.analytics.metrics_fetcher.fetch_metrics", return_value={"impressions": 500, "reactions": 25, "comments": 5, "shares": 2}),
        patch("app.agents.analytics.metrics_fetcher.calculate_performance_score", return_value=6.5),
        patch("app.agents.analytics.db_writer.write_analytics", return_value="analytics-001"),
        patch("app.agents.analytics.db_writer.update_style_guide"),
    ):
        result = await analytics_agent_task(ctx, post_id=post_id, measurement_period="24h")

    assert result["status"] == "done"
    assert result["measurement_period"] == "24h"


@pytest.mark.asyncio
async def test_analytics_task_updates_style_guide_at_7d():
    ctx = _make_ctx()
    post_id = "post-uuid-002"
    ctx["supabase"].table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        _make_post_data(post_id)
    ]

    with (
        patch("app.agents.analytics.metrics_fetcher.fetch_metrics", return_value={}),
        patch("app.agents.analytics.metrics_fetcher.calculate_performance_score", return_value=7.0),
        patch("app.agents.analytics.db_writer.write_analytics", return_value="analytics-002"),
        patch("app.agents.analytics.db_writer.update_style_guide") as mock_update,
    ):
        result = await analytics_agent_task(ctx, post_id=post_id, measurement_period="7d")

    assert result["status"] == "done"
    mock_update.assert_called_once()


@pytest.mark.asyncio
async def test_analytics_task_does_not_update_style_guide_at_24h():
    ctx = _make_ctx()
    post_id = "post-uuid-003"
    ctx["supabase"].table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        _make_post_data(post_id)
    ]

    with (
        patch("app.agents.analytics.metrics_fetcher.fetch_metrics", return_value={}),
        patch("app.agents.analytics.metrics_fetcher.calculate_performance_score", return_value=5.0),
        patch("app.agents.analytics.db_writer.write_analytics", return_value="analytics-003"),
        patch("app.agents.analytics.db_writer.update_style_guide") as mock_update,
    ):
        await analytics_agent_task(ctx, post_id=post_id, measurement_period="24h")

    mock_update.assert_not_called()


@pytest.mark.asyncio
async def test_analytics_task_returns_error_when_post_not_found():
    ctx = _make_ctx()
    ctx["supabase"].table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    result = await analytics_agent_task(ctx, post_id="nonexistent", measurement_period="24h")

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_analytics_task_handles_fetch_failure():
    ctx = _make_ctx()
    ctx["supabase"].table.return_value.select.return_value.eq.return_value.execute.side_effect = RuntimeError("db down")

    result = await analytics_agent_task(ctx, post_id="post-uuid-005", measurement_period="72h")

    assert result["status"] == "error"
