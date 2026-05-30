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
    assert result["cost_usd"] == 0.0


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
    """No topic/url args — task must complete successfully."""
    ctx = _make_ctx()
    with patch("app.queue.tasks.Anthropic"):
        from app.queue.tasks import research_agent_task
        result = await research_agent_task(ctx)

    assert result["status"] == "done"
    assert result["cost_usd"] == 0.0


@pytest.mark.asyncio
async def test_research_task_processes_one_site_one_article():
    """One active site, one article that passes all filters → success_count=1."""
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock

    ctx = _make_ctx()

    # Override supabase to return one active site
    site_data = {
        "id": "11111111-1111-1111-1111-111111111111",
        "site_name": "LiveMint",
        "section_url": "https://www.livemint.com/market",
        "active": True,
        "pre_score_threshold": 5.0,
        "consecutive_failures": 0,
        "last_run_at": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    ctx["supabase"].table.return_value.select.return_value.eq.return_value.execute.return_value.data = [site_data]
    # upsert_raw_content returns a UUID
    ctx["supabase"].table.return_value.insert.return_value.execute.return_value.data = [{"id": "article-uuid"}]
    ctx["supabase"].table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    # is_url_seen returns False (not seen)
    ctx["supabase"].table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

    mock_link = MagicMock()
    mock_link.url = "https://www.livemint.com/market/rbi-rate"
    mock_link.title = "RBI raises repo rate by 25bps"
    mock_link.source_name = "LiveMint"

    mock_content = MagicMock()
    mock_content.url = "https://www.livemint.com/market/rbi-rate"
    mock_content.normalized_url = "https://www.livemint.com/market/rbi-rate"
    mock_content.title = "RBI raises repo rate by 25bps"
    mock_content.full_text = "Full article text " * 100
    mock_content.word_count = 500
    mock_content.paywall_detected = False
    mock_content.publication_date = datetime(2026, 5, 29, tzinfo=timezone.utc)

    mock_summary_result = MagicMock()
    mock_summary_result.input_tokens = 300
    mock_summary_result.output_tokens = 100
    mock_summary_result.summary = MagicMock()

    mock_pre_result = MagicMock()
    mock_pre_result.scores = [7.5]
    mock_pre_result.input_tokens = 50
    mock_pre_result.output_tokens = 10

    with (
        patch("app.queue.tasks.Anthropic"),
        patch("app.agents.research.scraper.scrape_homepage", new=AsyncMock(return_value=[mock_link])),
        patch("app.agents.research.extractor.fetch_article", new=AsyncMock(return_value=mock_content)),
        patch("app.agents.research.prescorer.pre_score_headlines", return_value=mock_pre_result),
        patch("app.agents.research.summariser.summarise_article", return_value=mock_summary_result),
        patch("app.agents.research.filters.is_url_seen", return_value=False),
        patch("app.agents.research.filters.is_article_fresh", return_value=True),
        patch("app.agents.research.filters.is_article_long_enough", return_value=True),
    ):
        from importlib import reload
        import app.queue.tasks as tasks_mod
        reload(tasks_mod)
        result = await tasks_mod.research_agent_task(ctx)

    assert result["status"] == "done"
    assert result["processed"] >= 1
    assert result["success"] >= 1


@pytest.mark.asyncio
async def test_research_task_chains_to_scoring_when_redis_available():
    """research_agent_task should enqueue scoring_agent_task at the end."""
    mock_pool = AsyncMock()
    mock_pool.enqueue_job.return_value = AsyncMock(job_id="job-scoring-001")
    ctx = _make_ctx()
    ctx["redis"] = mock_pool  # arq injects redis pool as "redis" key

    # Empty sites list so the task runs quickly
    ctx["supabase"].table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    with patch("app.queue.tasks.Anthropic"):
        from app.queue.tasks import research_agent_task
        result = await research_agent_task(ctx)

    assert result["status"] == "done"
    mock_pool.enqueue_job.assert_awaited_once_with("scoring_agent_task")
