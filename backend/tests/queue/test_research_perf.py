import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_ctx(articles_per_site=2):
    settings = MagicMock()
    settings.anthropic_api_key = "test"
    settings.google_api_key = None
    settings.local_embedding_model = "BAAI/bge-base-en-v1.5"
    settings.claude_model_heavy = "claude-sonnet-4-5"
    settings.claude_model_light = "claude-haiku-4-5"
    settings.article_min_words = 400
    settings.article_max_age_days = 7
    settings.site_failure_pause_threshold = 5
    settings.daily_cost_alert_usd = 5.0
    settings.slack_webhook_url = None
    settings.browser_sessions_dir = "~/.config/contentautomation/browser_sessions"
    settings.articles_per_site = articles_per_site
    settings.default_pre_score_threshold = 4.0

    supabase = MagicMock()
    # No active sites → task exits cleanly
    supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    supabase.table.return_value.insert.return_value.execute.return_value.data = [{"id": "log-1"}]
    supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    return {"settings": settings, "supabase": supabase}


@pytest.mark.asyncio
async def test_research_task_runs_with_articles_per_site_setting():
    """research_agent_task reads articles_per_site from settings without error."""
    ctx = _make_ctx(articles_per_site=3)
    with patch("app.queue.tasks.Anthropic"), \
         patch("app.agents.embedding.client.make_embed_client"):
        from app.queue.tasks import research_agent_task
        result = await research_agent_task(ctx)
    assert result["status"] == "done"
