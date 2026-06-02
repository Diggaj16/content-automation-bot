"""Unit tests for orchestrator tool factory functions."""
from unittest.mock import AsyncMock, MagicMock
import pytest


def _make_tools(sb_mock=None, pool_mock=None):
    """Build tools with injected mocks."""
    sb = sb_mock or MagicMock()
    pool = pool_mock or AsyncMock()
    from app.agents.orchestrator.tools import make_tools
    return make_tools(sb, pool), sb, pool


# ── trigger_research ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trigger_research_enqueues_job():
    tools, _, pool = _make_tools()
    pool.enqueue_job.return_value = MagicMock(job_id="job-abc")

    trigger_research = next(t for t in tools if t.name == "trigger_research")
    result = await trigger_research.ainvoke({"topic": None})
    pool.enqueue_job.assert_called_once_with("research_agent_task", topic=None)
    assert "enqueued" in result


@pytest.mark.asyncio
async def test_trigger_research_with_topic():
    tools, _, pool = _make_tools()
    pool.enqueue_job.return_value = MagicMock(job_id="job-xyz")

    trigger_research = next(t for t in tools if t.name == "trigger_research")
    result = await trigger_research.ainvoke({"topic": "SEBI update"})
    pool.enqueue_job.assert_called_once_with("research_agent_task", topic="SEBI update")


# ── list_curated_sites ────────────────────────────────────────────────────────

def test_list_curated_sites_returns_data():
    sb = MagicMock()
    sb.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
        {"site_name": "MoneyControl", "active": True, "consecutive_failures": 0}
    ]
    tools, _, _ = _make_tools(sb_mock=sb)
    list_sites = next(t for t in tools if t.name == "list_curated_sites")
    result = list_sites.invoke({})
    assert "MoneyControl" in result


# ── add_curated_site ──────────────────────────────────────────────────────────

def test_add_curated_site_inserts_row():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "new-site-id", "site_name": "ET Markets"}
    ]
    tools, _, _ = _make_tools(sb_mock=sb)
    add_site = next(t for t in tools if t.name == "add_curated_site")
    result = add_site.invoke({"name": "ET Markets", "url": "https://economictimes.com/markets", "threshold": 4.0})
    assert "ET Markets" in result
    sb.table.return_value.insert.assert_called_once()


def test_add_curated_site_rejects_invalid_url():
    tools, _, _ = _make_tools()
    add_site = next(t for t in tools if t.name == "add_curated_site")
    result = add_site.invoke({"name": "Bad", "url": "not-a-url", "threshold": 4.0})
    assert "invalid" in result.lower() or "error" in result.lower()


# ── remove_curated_site ───────────────────────────────────────────────────────

def test_remove_curated_site_soft_deletes():
    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {"site_name": "OldSite"}
    ]
    tools, _, _ = _make_tools(sb_mock=sb)
    remove_site = next(t for t in tools if t.name == "remove_curated_site")
    result = remove_site.invoke({"site_name": "OldSite"})
    assert "OldSite" in result
    call_args = sb.table.return_value.update.call_args[0][0]
    assert call_args["active"] is False


# ── get_run_logs ──────────────────────────────────────────────────────────────

def test_get_run_logs_formats_output():
    sb = MagicMock()
    sb.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {
            "agent_name": "research_agent",
            "trigger_type": "cron",
            "success_count": 5,
            "failure_count": 1,
            "duration_seconds": 42.3,
            "token_cost": {"total_usd": 0.012},
            "created_at": "2026-05-30T06:00:00",
        }
    ]
    tools, _, _ = _make_tools(sb_mock=sb)
    get_logs = next(t for t in tools if t.name == "get_run_logs")
    result = get_logs.invoke({"limit": 5})
    assert "research_agent" in result
