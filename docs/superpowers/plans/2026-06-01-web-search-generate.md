# Web Search + On-Demand Post Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The orchestrator can search the web for current information and generate a LinkedIn/Twitter/blog post on demand, grounded in real scraped content and the brand's voice — without going through the full research pipeline.

**Architecture:** Four new tools added to `make_tools()`: `search_web` (Tavily primary / DuckDuckGo fallback), `search_and_scrape` (calls `fetch_article` on each result URL for full article body), `generate_post` (search + brand context + Claude direct call → returns draft text), `save_draft` (persists generated text to DB). `TAVILY_API_KEY` is optional; if absent, DuckDuckGo is used silently.

**Tech Stack:** Python, tavily-python, duckduckgo-search, Crawl4AI (existing), Anthropic SDK (direct call, not via arq)

---

## File Map

- Modify: `backend/pyproject.toml` — add tavily-python, duckduckgo-search
- Modify: `backend/app/config.py` — add `tavily_api_key` field
- Modify: `backend/app/agents/orchestrator/tools.py` — 4 new tools
- Modify: `backend/app/agents/orchestrator/agent.py` — update system prompt to mention new tools
- Test: `backend/tests/agents/orchestrator/test_web_search_tools.py`

---

### Task 1: Add dependencies and config

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add deps to `pyproject.toml`**

In `backend/pyproject.toml`, inside the `dependencies` list, add:
```toml
    "tavily-python>=0.3.0",
    "duckduckgo-search>=6.0.0",
```

- [ ] **Step 2: Install the new packages**

```powershell
cd D:\Intern\content-automation-bot\backend
pip install tavily-python duckduckgo-search
```
Expected: both install without errors

- [ ] **Step 3: Add `tavily_api_key` to Settings**

In `backend/app/config.py`, add after `google_api_key`:
```python
    tavily_api_key: Optional[str] = Field(None, alias="TAVILY_API_KEY")
```

The block should look like:
```python
    # Embeddings — Gemini primary, local fastembed fallback
    google_api_key: Optional[str] = Field(None, alias="GOOGLE_API_KEY")
    local_embedding_model: str = Field("BAAI/bge-base-en-v1.5", alias="LOCAL_EMBEDDING_MODEL")

    # Web search — Tavily primary (optional), DuckDuckGo fallback (no key needed)
    tavily_api_key: Optional[str] = Field(None, alias="TAVILY_API_KEY")
```

- [ ] **Step 4: Run config test**

```powershell
python -m pytest tests/test_config.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```powershell
git add backend/pyproject.toml backend/app/config.py
git commit -m "feat: add tavily-python + duckduckgo-search deps and TAVILY_API_KEY config"
```

---

### Task 2: `search_web` tool — Tavily + DuckDuckGo fallback

**Files:**
- Modify: `backend/app/agents/orchestrator/tools.py`
- Test: `backend/tests/agents/orchestrator/test_web_search_tools.py`

- [ ] **Step 1: Write tests**

Create `backend/tests/agents/orchestrator/test_web_search_tools.py`:

```python
"""Tests for web search and on-demand generation tools."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
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
    assert "No results" in result or "0" in result


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
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/agents/orchestrator/test_web_search_tools.py -v 2>&1 | Select-Object -Last 15
```
Expected: FAIL — tools not found, signature mismatch

- [ ] **Step 3: Update `make_tools` signature to accept `tavily_api_key` and `anthropic_api_key`**

The current `make_tools` only takes `supabase` and `arq_pool`. Update the signature:

```python
def make_tools(supabase: Client, arq_pool, tavily_api_key: str | None = None, anthropic_api_key: str | None = None) -> list:
    """Build and return all orchestrator tool callables."""
```

Also update all callers:
- `backend/app/agents/orchestrator/agent.py`: `build_orchestrator_agent` passes these from settings
- `backend/app/api/routers/orchestrator.py`: passes from `settings.tavily_api_key` and `settings.anthropic_api_key`

In `backend/app/agents/orchestrator/agent.py`:
```python
def build_orchestrator_agent(
    supabase: Client,
    arq_pool,
    anthropic_api_key: str,
    model: str = "claude-sonnet-4-5",
    tavily_api_key: str | None = None,
):
    tools = make_tools(
        supabase=supabase,
        arq_pool=arq_pool,
        tavily_api_key=tavily_api_key,
        anthropic_api_key=anthropic_api_key,
    )
    ...
```

In `backend/app/api/routers/orchestrator.py`, update `_get_or_build_agent`:
```python
            request.app.state.orchestrator_agent = build_orchestrator_agent(
                supabase=supabase,
                arq_pool=arq_pool,
                anthropic_api_key=settings.anthropic_api_key,
                model=settings.orchestrator_model,
                tavily_api_key=settings.tavily_api_key,
            )
```

- [ ] **Step 4: Add search helper functions and tools to `tools.py`**

At module level (before `make_tools`), add the helper functions:

```python
from typing import Optional


def _duckduckgo_search(query: str, max_results: int = 3) -> list[dict]:
    """Search using DuckDuckGo. Returns list of {url, title, snippet}."""
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "url": r.get("href") or r.get("url", ""),
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                })
        return results
    except Exception as exc:
        logger.warning("_duckduckgo_search failed", extra={"query": query, "error": str(exc)})
        return []


def _tavily_search(query: str, api_key: str, max_results: int = 3) -> list[dict]:
    """Search using Tavily API. Returns list of {url, title, snippet}."""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        resp = client.search(query=query, max_results=max_results, search_depth="advanced")
        return [
            {
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "snippet": r.get("content", ""),
            }
            for r in resp.get("results", [])
        ]
    except Exception as exc:
        logger.warning("_tavily_search failed", extra={"query": query, "error": str(exc)})
        return []


def _fetch_article_sync(url: str, sessions_dir: str | None = None):
    """Synchronous wrapper around async fetch_article for use inside tools."""
    import asyncio
    from app.agents.research.extractor import fetch_article
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    fetch_article(url, sessions_dir=sessions_dir)
                )
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(fetch_article(url, sessions_dir=sessions_dir))
    except Exception as exc:
        logger.warning("_fetch_article_sync failed", extra={"url": url, "error": str(exc)})
        return None
```

Then inside `make_tools()`, add the new tools:

```python
    # ── Web search ───────────────────────────────────────────────────────────

    @tool
    async def search_web(query: str, max_results: int = 3) -> str:
        """Search the web for current information on a topic.
        Uses Tavily (if configured) or DuckDuckGo as fallback.
        Returns URLs, titles, and brief snippets — use search_and_scrape for full content."""
        results = (
            _tavily_search(query, tavily_api_key, max_results)
            if tavily_api_key
            else _duckduckgo_search(query, max_results)
        )
        if not results:
            return f"No search results found for: {query!r}"
        lines = [
            f"{i+1}. {r['title']}\n   {r['url']}\n   {r['snippet'][:120]}"
            for i, r in enumerate(results)
        ]
        return f"Search results for '{query}':\n\n" + "\n\n".join(lines)

    @tool
    async def search_and_scrape(query: str, max_results: int = 3) -> str:
        """Search the web AND scrape full article text from results.
        Use this as the grounding step before generate_post to get current, accurate information.
        Returns combined article text ready to use as source material."""
        results = (
            _tavily_search(query, tavily_api_key, max_results)
            if tavily_api_key
            else _duckduckgo_search(query, max_results)
        )
        if not results:
            return f"No search results found for: {query!r}"

        articles = []
        for r in results:
            url = r.get("url", "")
            if not url:
                continue
            content = _fetch_article_sync(url)
            if content is None or content.paywall_detected or content.word_count < 50:
                continue
            snippet = content.full_text[:2500]
            articles.append(f"Source: {r['title']} ({url})\n{snippet}")

        if not articles:
            return (
                f"Found {len(results)} search result(s) for '{query}' but "
                f"all were paywalled or empty. Try a different query or provide context manually."
            )
        return (
            f"Scraped {len(articles)} article(s) for '{query}':\n\n"
            + "\n\n---\n\n".join(articles)
        )

    @tool
    async def generate_post(
        topic: str,
        platform: str = "linkedin",
        content_type: str = "news_driven",
    ) -> str:
        """Generate a social media post on demand using web search + brand voice.

        Workflow: (1) search_and_scrape for current info on the topic,
        (2) fetch brand voice examples from brand_memory,
        (3) call Claude to write the post in brand voice.
        The draft is returned in chat — say 'save this' to persist it.

        platform: 'linkedin', 'twitter', 'blog', or 'email'
        content_type: 'news_driven' (use article facts), 'kb_driven' (use KB docs), 'combined'"""
        if not anthropic_api_key:
            return "Error: ANTHROPIC_API_KEY not configured."

        # Step 1 — Get current information
        scraped = (
            _tavily_search(topic, tavily_api_key, 3)
            if tavily_api_key
            else _duckduckgo_search(topic, 3)
        )
        article_text = ""
        for r in scraped:
            url = r.get("url", "")
            if not url:
                continue
            content = _fetch_article_sync(url)
            if content and not content.paywall_detected and content.word_count >= 50:
                article_text += f"\n\nSource: {r['title']}\n{content.full_text[:2000]}"
                break  # one good article is enough for generation

        if not article_text:
            article_text = f"General knowledge about: {topic}"

        # Step 2 — Get brand voice examples
        brand_examples = ""
        try:
            resp = (
                supabase.table("brand_memory")
                .select("content")
                .eq("platform", platform)
                .order("created_at", desc=True)
                .limit(3)
                .execute()
            )
            examples = [r["content"] for r in (resp.data or [])]
            if examples:
                brand_examples = "Brand voice examples (match this style):\n\n" + "\n\n---\n\n".join(examples)
        except Exception:
            pass

        # Step 3 — Generate with Claude
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=anthropic_api_key)
            system = f"""You write educational Indian finance content for {platform}.
Write in the exact style and tone of the brand voice examples provided.
Rules: educational not advisory, no specific investment recommendations, add a disclaimer at the end,
use relevant hashtags for {platform}, keep it concise and engaging."""

            user_prompt = f"""Write a {platform} post about: {topic}

{brand_examples}

Source material (use facts from this, don't fabricate numbers):
{article_text[:3000]}

Write the full post now. Return only the post text, nothing else."""

            message = client.messages.create(
                model="claude-haiku-4-5",  # fast + cheap for generation
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": user_prompt}],
            )
            post_text = message.content[0].text.strip() if message.content else ""
            if not post_text:
                return "Error: Claude returned empty response."
            return (
                f"Generated {platform} post about '{topic}':\n\n"
                f"{post_text}\n\n"
                f"---\nSay 'save this as a draft' to save it, or ask me to revise it."
            )
        except Exception as exc:
            logger.warning("generate_post: Claude call failed", extra={"error": str(exc)})
            return f"Error generating post: {exc}"

    @tool
    async def save_draft(content: str, platform: str) -> str:
        """Save a generated post as a pending draft for review and approval.
        content: the full post text. platform: 'linkedin', 'twitter', 'blog', or 'email'."""
        try:
            resp = supabase.table("drafts").insert({
                "content_text": content,
                "platform": platform,
                "approval_status": "pending_approval",
                "agent_reasoning": "Generated on-demand via orchestrator",
                "finance_flags": [],
            }).execute()
            if resp.data:
                draft_id = resp.data[0].get("id", "?")
                return (
                    f"✓ Saved as pending draft (id={str(draft_id)[:8]}…). "
                    f"Go to Gate 2 (Drafts) to review and approve it for publishing."
                )
            return "Draft saved."
        except Exception as exc:
            logger.warning("save_draft failed", extra={"error": str(exc)})
            return f"Error saving draft: {exc}"
```

- [ ] **Step 5: Add new tools to the return list**

Update the `return` statement in `make_tools()` to include the 4 new tools:
```python
    return [
        # Pipeline triggers
        trigger_research, trigger_scoring, trigger_creation,
        # Ideas (Gate 1)
        get_ideas, approve_idea, reject_idea, bulk_reject_ideas, send_ideas_to_creation,
        # Drafts (Gate 2)
        get_drafts, approve_draft, reject_draft,
        # Brand & subscribers
        add_brand_memory, list_brand_memory,
        list_subscribers, add_email_subscriber, remove_email_subscriber,
        # Analytics & browsing
        get_analytics_summary, get_topic_performance, get_run_logs,
        get_decision_summaries, get_recent_articles, get_published_posts, list_kb_files,
        # Site management
        add_curated_site, remove_curated_site, list_curated_sites,
        # Auth
        login_to_site,
        # Web search & on-demand generation
        search_web, search_and_scrape, generate_post, save_draft,
    ]
```

- [ ] **Step 6: Run web search tests**

```powershell
python -m pytest tests/agents/orchestrator/test_web_search_tools.py -v
```
Expected: all PASS

- [ ] **Step 7: Run full test suite**

```powershell
python -m pytest tests/ -q
```
Expected: all PASS

- [ ] **Step 8: Commit**

```powershell
git add backend/app/agents/orchestrator/tools.py \
        backend/app/agents/orchestrator/agent.py \
        backend/app/api/routers/orchestrator.py \
        backend/tests/agents/orchestrator/test_web_search_tools.py \
        backend/app/config.py \
        backend/pyproject.toml
git commit -m "feat: add web search + on-demand post generation to orchestrator

- search_web: Tavily primary / DuckDuckGo fallback
- search_and_scrape: search + full Crawl4AI article extraction
- generate_post: search + brand voice + Claude Haiku → draft in chat
- save_draft: persist generated post to drafts table
- make_tools signature extended with tavily_api_key + anthropic_api_key"
```

---

### Task 3: Update system prompt to describe new tools

**Files:**
- Modify: `backend/app/agents/orchestrator/agent.py`

- [ ] **Step 1: Add web search section to `_SYSTEM_PROMPT`**

Inside `_SYSTEM_PROMPT`, add a new section after `### Analytics & Ops`:

```
### On-Demand Content Generation
- search_web(query, max_results?) — find current news/info on any topic
- search_and_scrape(query, max_results?) — search + scrape full article text (use before generate_post)
- generate_post(topic, platform?, content_type?) — generate a post grounded in web search + brand voice
- save_draft(content, platform) — save a generated post as a pending draft

**On-demand generation workflow:**
When asked to write a post about something:
1. Call generate_post(topic, platform) — this searches, scrapes, and generates in one step
2. Show the result to the user
3. If they approve, call save_draft(content, platform)
4. If they want changes, regenerate with updated instructions

If you need to check information first without generating, use search_web or search_and_scrape.
```

- [ ] **Step 2: Run full test suite**

```powershell
python -m pytest tests/ -q
```
Expected: all PASS

- [ ] **Step 3: Manual end-to-end test**

With the backend running, test in the orchestrator chat:
```
User: Make a LinkedIn post about SEBI's latest mutual fund regulation changes
```
Expected: The agent calls `generate_post`, searches the web, scrapes an article, generates a LinkedIn post in Growthvine Capital's voice, and offers to save it.

```
User: Save this as a draft
```
Expected: Calls `save_draft`, confirms draft saved, mentions it's visible in Gate 2.

- [ ] **Step 4: Add TAVILY_API_KEY to `.env` (optional but recommended)**

```
# In backend/.env, add:
TAVILY_API_KEY=tvly-your-key-here
```
Get a free key at https://tavily.com — 1000 free searches/month.

- [ ] **Step 5: Final commit**

```powershell
git add backend/app/agents/orchestrator/agent.py
git commit -m "docs: add on-demand generation workflow to orchestrator system prompt"
```
