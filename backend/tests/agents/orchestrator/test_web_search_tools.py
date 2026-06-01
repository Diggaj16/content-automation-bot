"""Tests for web search and on-demand generation tools."""
import pytest
from unittest.mock import MagicMock, patch
from app.agents.orchestrator.tools import make_tools


def _make_sb():
    sb = MagicMock()
    return sb


def _get_tool(name: str, tavily_key=None, anthropic_key=None):
    tools = make_tools(
        supabase=_make_sb(),
        arq_pool=None,
        tavily_api_key=tavily_key,
        anthropic_api_key=anthropic_key,
    )
    for t in tools:
        if t.name == name:
            return t
    raise KeyError(f"Tool {name!r} not found")


# ── search_web ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_web_uses_duckduckgo_when_no_tavily_key():
    """Without TAVILY_API_KEY, search_web falls back to DuckDuckGo."""
    mock_results = [
        {"url": "https://example.com/article1", "title": "SEBI announces new rules", "snippet": "SEBI has..."},
    ]
    with patch("app.agents.orchestrator.tools._duckduckgo_search", return_value=mock_results):
        tool = _get_tool("search_web", tavily_key=None)
        result = await tool.ainvoke({"query": "SEBI new rules 2026"})
    assert "SEBI announces new rules" in result
    assert "example.com" in result


@pytest.mark.asyncio
async def test_search_web_returns_empty_on_no_results():
    with patch("app.agents.orchestrator.tools._duckduckgo_search", return_value=[]):
        tool = _get_tool("search_web", tavily_key=None)
        result = await tool.ainvoke({"query": "completely obscure topic xyz"})
    assert "No" in result and ("results" in result or "found" in result)


# ── search_and_scrape ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_and_scrape_returns_article_text():
    mock_search = [{"url": "https://example.com/a1", "title": "GST reform", "snippet": "GST..."}]
    mock_content = MagicMock()
    mock_content.full_text = "Full article text about GST reform with details."
    mock_content.paywall_detected = False
    mock_content.word_count = 50

    with patch("app.agents.orchestrator.tools._duckduckgo_search", return_value=mock_search), \
         patch("app.agents.orchestrator.tools._fetch_article_sync", return_value=mock_content):
        tool = _get_tool("search_and_scrape", tavily_key=None)
        result = await tool.ainvoke({"query": "GST reform India"})
    assert "GST reform" in result
    assert "Full article text" in result


@pytest.mark.asyncio
async def test_search_and_scrape_skips_paywalled():
    mock_search = [{"url": "https://example.com/a1", "title": "Paywall article", "snippet": "..."}]
    mock_content = MagicMock()
    mock_content.full_text = "Subscribe to read"
    mock_content.paywall_detected = True
    mock_content.word_count = 5

    with patch("app.agents.orchestrator.tools._duckduckgo_search", return_value=mock_search), \
         patch("app.agents.orchestrator.tools._fetch_article_sync", return_value=mock_content):
        tool = _get_tool("search_and_scrape", tavily_key=None)
        result = await tool.ainvoke({"query": "test"})
    assert "paywall" in result.lower() or "No usable" in result or "0 article" in result.lower()


# ── save_draft ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_draft_inserts_row():
    sb = _make_sb()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "draft-new-1"}]
    tools = make_tools(supabase=sb, arq_pool=None, tavily_api_key=None, anthropic_api_key="sk-test")
    tool = next(t for t in tools if t.name == "save_draft")
    result = await tool.ainvoke({"content": "Great post about SEBI.", "platform": "linkedin"})
    assert "saved" in result.lower() or "draft" in result.lower()
    sb.table.assert_any_call("drafts")
