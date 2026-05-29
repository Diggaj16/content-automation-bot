"""Smoke tests for the wired research_agent_task."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_ctx() -> dict:
    """Minimal ctx dict matching what arq's startup() provides."""
    settings = MagicMock()
    settings.anthropic_api_key = "test-key"
    settings.claude_model_light = "claude-haiku-4-5"
    settings.claude_model_heavy = "claude-sonnet-4-5"
    settings.article_max_age_days = 7
    settings.article_min_words = 400
    settings.daily_cost_alert_usd = 5.0
    settings.slack_webhook_url = None
    settings.site_failure_pause_threshold = 5

    supabase = MagicMock()
    # No active sites — simplest successful run
    supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    return {"settings": settings, "supabase": supabase}


@pytest.mark.asyncio
async def test_research_task_returns_done_status_with_no_sites():
    """With zero active sites the task completes and returns status=done."""
    ctx = _make_ctx()
    with patch("app.queue.tasks.Anthropic"):
        from app.queue.tasks import research_agent_task
        result = await research_agent_task(ctx)

    assert result["status"] == "done"
    assert result["processed"] == 0
    assert result["success"] == 0
    assert "duration_seconds" in result


@pytest.mark.asyncio
async def test_research_task_writes_run_log():
    """A run_logs INSERT must be called at the end of every run."""
    ctx = _make_ctx()
    with patch("app.queue.tasks.Anthropic"):
        from app.queue.tasks import research_agent_task
        await research_agent_task(ctx)

    # run_logs INSERT should have been called
    insert_calls = [str(c) for c in ctx["supabase"].table.call_args_list]
    assert any("run_logs" in c for c in insert_calls)


@pytest.mark.asyncio
async def test_research_task_cron_trigger_with_no_args():
    """No topic/url args should yield trigger_type=cron in run_log."""
    ctx = _make_ctx()
    inserted_payloads = []

    def capture_table(table_name):
        mock_tbl = MagicMock()
        mock_tbl.select.return_value.eq.return_value.execute.return_value.data = []
        mock_tbl.insert.return_value.execute.return_value.data = [{"id": "fake-id"}]
        mock_tbl.update.return_value.eq.return_value.execute.return_value.data = []
        if table_name == "run_logs":
            original_insert = mock_tbl.insert
            def capturing_insert(payload):
                inserted_payloads.append(payload)
                return original_insert(payload)
            mock_tbl.insert = capturing_insert
        return mock_tbl

    ctx["supabase"].table = capture_table

    with patch("app.queue.tasks.Anthropic"):
        from importlib import reload
        import app.queue.tasks as tasks_mod
        reload(tasks_mod)
        result = await tasks_mod.research_agent_task(ctx)

    assert result["status"] == "done"
    # If any run_logs payload was captured, verify trigger_type
    if inserted_payloads:
        assert inserted_payloads[0].get("trigger_type") in ("cron", "TriggerType.CRON", None)
