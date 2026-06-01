"""Tests for the expanded orchestrator tools (ideas, drafts, brand memory, etc.)."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from app.agents.orchestrator.tools import make_tools


def _make_sb():
    sb = MagicMock()
    return sb


def _get_tool(name: str):
    """Build all tools and return the one with the given name."""
    tools = make_tools(supabase=_make_sb(), arq_pool=None)
    for t in tools:
        if t.name == name:
            return t
    raise KeyError(f"Tool {name!r} not found")


# ── get_ideas ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_ideas_returns_string():
    sb = _make_sb()
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"id": "abc-1", "angle": "GST reform impact", "platform": "linkedin",
         "score": 7.5, "created_at": "2026-06-01T10:00:00+00:00"}
    ]
    tools = make_tools(supabase=sb, arq_pool=None)
    tool = next(t for t in tools if t.name == "get_ideas")
    result = await tool.ainvoke({"status": "pending_approval"})
    assert "GST reform impact" in result
    assert "linkedin" in result


@pytest.mark.asyncio
async def test_get_ideas_empty_returns_message():
    sb = _make_sb()
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
    tools = make_tools(supabase=sb, arq_pool=None)
    tool = next(t for t in tools if t.name == "get_ideas")
    result = await tool.ainvoke({"status": "pending_approval"})
    assert "No" in result or "0" in result


# ── approve_idea ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_approve_idea_updates_status():
    sb = _make_sb()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "abc-1"}]
    tools = make_tools(supabase=sb, arq_pool=None)
    tool = next(t for t in tools if t.name == "approve_idea")
    result = await tool.ainvoke({"idea_id": "abc-1"})
    assert "approved" in result.lower()
    sb.table.assert_any_call("ideas")


# ── reject_idea ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reject_idea_updates_status():
    sb = _make_sb()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "abc-1"}]
    tools = make_tools(supabase=sb, arq_pool=None)
    tool = next(t for t in tools if t.name == "reject_idea")
    result = await tool.ainvoke({"idea_id": "abc-1"})
    assert "rejected" in result.lower()


# ── bulk_reject_ideas ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_reject_ideas_returns_count():
    sb = _make_sb()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "x"}]
    tools = make_tools(supabase=sb, arq_pool=None)
    tool = next(t for t in tools if t.name == "bulk_reject_ideas")
    result = await tool.ainvoke({"idea_ids": ["id-1", "id-2"]})
    assert "2" in result


# ── send_ideas_to_creation ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_ideas_to_creation_requires_arq():
    tools = make_tools(supabase=_make_sb(), arq_pool=None)
    tool = next(t for t in tools if t.name == "send_ideas_to_creation")
    result = await tool.ainvoke({"idea_ids": ["id-1"]})
    # arq_pool is None → should return an error string, not raise
    assert isinstance(result, str)
    assert "Error" in result or "unavailable" in result.lower()
