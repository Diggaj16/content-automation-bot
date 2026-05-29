"""Smoke tests for scoring_agent_task."""
import pytest
from unittest.mock import MagicMock, patch


def _make_ctx() -> dict:
    settings = MagicMock()
    settings.anthropic_api_key = "test-key"
    settings.voyage_api_key = None
    settings.claude_model_heavy = "claude-sonnet-4-5"
    settings.daily_cost_alert_usd = 5.0
    settings.slack_webhook_url = None

    supabase = MagicMock()
    # No unprocessed articles
    supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    supabase.table.return_value.insert.return_value.execute.return_value.data = [{"id": "log-id"}]
    supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

    return {"settings": settings, "supabase": supabase}


@pytest.mark.asyncio
async def test_scoring_task_returns_done_with_no_articles():
    ctx = _make_ctx()
    with patch("app.queue.tasks.Anthropic"):
        from app.queue.tasks import scoring_agent_task
        result = await scoring_agent_task(ctx)
    assert result["status"] == "done"
    assert result["processed"] == 0
    assert result["ideas_created"] == 0
    assert "duration_seconds" in result


@pytest.mark.asyncio
async def test_scoring_task_writes_run_log():
    ctx = _make_ctx()
    with patch("app.queue.tasks.Anthropic"):
        from app.queue.tasks import scoring_agent_task
        await scoring_agent_task(ctx)
    table_calls = [str(c) for c in ctx["supabase"].table.call_args_list]
    assert any("run_logs" in c for c in table_calls)


@pytest.mark.asyncio
async def test_scoring_task_skips_voyage_when_key_is_none():
    ctx = _make_ctx()
    ctx["settings"].voyage_api_key = None
    with patch("app.queue.tasks.Anthropic"):
        from app.queue.tasks import scoring_agent_task
        result = await scoring_agent_task(ctx)
    assert result["status"] == "done"
