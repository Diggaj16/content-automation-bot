# Orchestrator Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a LangGraph ReAct orchestrator that non-technical operators can chat with to trigger agents, query pipeline state, and manage curated sites — wired to a new chat UI page in the frontend.

**Architecture:** LangGraph's `create_react_agent` prebuilt graph wraps 10 tool functions and a `MemorySaver` for per-thread conversation history. Tools are async functions decorated with `@tool` (LangChain compatible). The agent is constructed once at startup and cached on `app.state`. A `POST /orchestrate` endpoint invokes it. The frontend renders a chat UI at `/orchestrator` with thread-ID persistence via `localStorage`.

**Tech Stack:** Python 3.11, `langgraph>=0.2.0`, `langchain-anthropic>=0.2.0`, `langchain-core`, FastAPI, arq, supabase-py; Next.js 16, React 19, Tailwind 4.

---

## File Map

| Action | Path |
|--------|------|
| Modify | `backend/pyproject.toml` |
| Create | `backend/app/agents/orchestrator/tools.py` |
| Create | `backend/app/agents/orchestrator/agent.py` |
| Create | `backend/app/api/routers/orchestrator.py` |
| Modify | `backend/app/api/main.py` |
| Modify | `backend/app/config.py` |
| Create | `backend/tests/test_orchestrator_tools.py` |
| Create | `frontend/app/orchestrator/page.tsx` |
| Modify | `frontend/app/lib/api.ts` |

Note: `backend/app/agents/orchestrator/__init__.py` is created by the KB ingestion plan. If running this plan standalone, create it as an empty file.

---

### Task 1 — LangGraph dependencies

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add langgraph and langchain-anthropic**

In `backend/pyproject.toml`, in the `dependencies = [...]` list, add:

```toml
"langgraph>=0.2.0",
"langchain-anthropic>=0.2.0",
```

- [ ] **Step 2: Install**

```powershell
cd D:\Intern\content-automation-bot\backend
pip install "langgraph>=0.2.0" "langchain-anthropic>=0.2.0"
```

Expected: both install successfully.

- [ ] **Step 3: Verify imports**

```powershell
cd D:\Intern\content-automation-bot\backend
python -c "from langgraph.prebuilt import create_react_agent; from langchain_anthropic import ChatAnthropic; print('LangGraph OK')"
```

Expected: `LangGraph OK`

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml
git commit -m "chore: add langgraph and langchain-anthropic dependencies"
```

---

### Task 2 — Config addition

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add `orchestrator_model` field**

In `backend/app/config.py`, inside the `Settings` class, after `claude_model_light`, add:

```python
    # Orchestrator
    orchestrator_model: str = Field("claude-sonnet-4-6", alias="ORCHESTRATOR_MODEL")
```

- [ ] **Step 2: Verify**

```powershell
cd D:\Intern\content-automation-bot\backend
python -c "from app.config import get_settings; s = get_settings(); print(f'orchestrator_model = {s.orchestrator_model}')"
```

Expected: `orchestrator_model = claude-sonnet-4-6`

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: add ORCHESTRATOR_MODEL config field"
```

---

### Task 3 — Orchestrator tools

**Files:**
- Create: `backend/app/agents/orchestrator/tools.py`
- Create: `backend/tests/test_orchestrator_tools.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_orchestrator_tools.py
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


# ── get_pending_ideas ─────────────────────────────────────────────────────────

def test_get_pending_ideas_returns_data():
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"id": "idea-1", "angle": "Some idea", "platform": "linkedin", "score": 7.5}
    ]
    tools, _, _ = _make_tools(sb_mock=sb)
    get_pending = next(t for t in tools if t.name == "get_pending_ideas")
    result = get_pending.invoke({"limit": 10})
    assert "idea-1" in result or "Some idea" in result


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
```

- [ ] **Step 2: Run tests — expect ImportError**

```powershell
cd D:\Intern\content-automation-bot\backend
pytest tests/test_orchestrator_tools.py -v 2>&1 | Select-Object -First 20
```

Expected: `ModuleNotFoundError: No module named 'app.agents.orchestrator.tools'`

- [ ] **Step 3: Write `tools.py`**

```python
# backend/app/agents/orchestrator/tools.py
"""
LangGraph tool factory for the orchestrator agent.

Call make_tools(supabase, arq_pool) once at startup — tools receive
supabase and arq_pool via closure so callers don't need to pass them
as tool arguments (which would leak internal types into the LLM's context).
"""
from __future__ import annotations

import json
from typing import Optional
from urllib.parse import urlparse

from langchain_core.tools import tool
from supabase import Client

from app.utils.logging import get_logger

logger = get_logger(__name__)


def make_tools(supabase: Client, arq_pool) -> list:
    """Build and return all 10 orchestrator tool callables."""

    @tool
    async def trigger_research(topic: Optional[str] = None) -> str:
        """Trigger the research agent to discover and scrape new articles.
        Optionally pass a topic hint (e.g. 'SEBI announcement') to guide research."""
        try:
            job = await arq_pool.enqueue_job("research_agent_task", topic=topic)
            job_id = job.job_id if job else "unknown"
            return f"Research agent enqueued (job_id={job_id}). Topic hint: {topic or 'none'}."
        except Exception as exc:
            logger.warning(f"trigger_research failed | err={exc}")
            return f"Error triggering research: {exc}"

    @tool
    async def trigger_scoring() -> str:
        """Trigger the scoring agent to generate content ideas from unprocessed articles."""
        try:
            job = await arq_pool.enqueue_job("scoring_agent_task")
            job_id = job.job_id if job else "unknown"
            return f"Scoring agent enqueued (job_id={job_id})."
        except Exception as exc:
            logger.warning(f"trigger_scoring failed | err={exc}")
            return f"Error triggering scoring: {exc}"

    @tool
    async def trigger_creation(idea_ids: list[str], content_type: str = "combined") -> str:
        """Trigger the creation agent to generate drafts for approved ideas.
        The orchestrator always uses content_type='combined' (article + KB context).
        idea_ids: list of approved idea UUID strings."""
        if not idea_ids:
            return "Error: idea_ids must not be empty."
        try:
            job = await arq_pool.enqueue_job(
                "creation_agent_task",
                idea_ids=idea_ids,
                content_type=content_type,
            )
            job_id = job.job_id if job else "unknown"
            return (
                f"Creation agent enqueued for {len(idea_ids)} idea(s) "
                f"(job_id={job_id}, content_type={content_type})."
            )
        except Exception as exc:
            logger.warning(f"trigger_creation failed | err={exc}")
            return f"Error triggering creation: {exc}"

    @tool
    def get_pending_ideas(limit: int = 10) -> str:
        """Return up to `limit` ideas awaiting approval at Gate 1. Shows id, angle, platform, and score."""
        try:
            resp = (
                supabase.table("ideas")
                .select("id, angle, platform, score, created_at")
                .eq("approval_status", "pending_approval")
                .order("score", desc=True)
                .limit(limit)
                .execute()
            )
            ideas = resp.data or []
            if not ideas:
                return "No pending ideas at Gate 1."
            lines = [f"[{i['platform']}] score={i.get('score','?'):.1f} | {i['angle']} (id: {i['id']})"
                     if isinstance(i.get('score'), (int, float))
                     else f"[{i['platform']}] {i['angle']} (id: {i['id']})"
                     for i in ideas]
            return f"{len(ideas)} pending idea(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning(f"get_pending_ideas failed | err={exc}")
            return f"Error fetching pending ideas: {exc}"

    @tool
    def get_analytics_summary() -> str:
        """Return last 5 run logs and average performance per platform from content analytics."""
        try:
            logs_resp = (
                supabase.table("run_logs")
                .select("agent_name, trigger_type, success_count, failure_count, duration_seconds, token_cost, created_at")
                .order("created_at", desc=True)
                .limit(5)
                .execute()
            )
            analytics_resp = (
                supabase.table("content_analytics")
                .select("platform, performance_score")
                .execute()
            )

            lines = ["=== Recent Runs ==="]
            for log in (logs_resp.data or []):
                cost = log.get("token_cost", {}) or {}
                total_usd = cost.get("total_usd", 0)
                lines.append(
                    f"{log['agent_name']} | success={log['success_count']} "
                    f"fail={log['failure_count']} | ${total_usd:.4f} | {log['created_at'][:16]}"
                )

            # Platform averages
            platform_scores: dict[str, list[float]] = {}
            for row in (analytics_resp.data or []):
                p = row["platform"]
                s = row.get("performance_score")
                if s is not None:
                    platform_scores.setdefault(p, []).append(s)

            if platform_scores:
                lines.append("\n=== Platform Averages ===")
                for platform, scores in sorted(platform_scores.items()):
                    avg = sum(scores) / len(scores)
                    lines.append(f"{platform}: avg score={avg:.2f} ({len(scores)} posts)")

            return "\n".join(lines)
        except Exception as exc:
            logger.warning(f"get_analytics_summary failed | err={exc}")
            return f"Error fetching analytics: {exc}"

    @tool
    def add_curated_site(name: str, url: str, threshold: float = 4.0) -> str:
        """Add a new curated news site to the research pipeline.
        name: display name (e.g. 'ET Markets'). url: full section URL. threshold: pre-score threshold 1.0–10.0."""
        # Validate URL
        try:
            parsed = urlparse(url)
            if not (parsed.scheme in ("http", "https") and parsed.netloc):
                return f"Error: Invalid URL '{url}'. Must start with http:// or https://."
        except Exception:
            return f"Error: Invalid URL '{url}'."

        try:
            resp = supabase.table("curated_sites").insert({
                "site_name": name,
                "section_url": url,
                "active": True,
                "pre_score_threshold": threshold,
                "consecutive_failures": 0,
            }).execute()
            if resp.data:
                site_id = resp.data[0].get("id", "unknown")
                return f"Added curated site '{name}' (id={site_id}, threshold={threshold})."
            return f"Added '{name}' but insert returned no data."
        except Exception as exc:
            logger.warning(f"add_curated_site failed | err={exc}")
            return f"Error adding site: {exc}"

    @tool
    def remove_curated_site(site_name: str) -> str:
        """Deactivate a curated site by name (soft delete — sets active=false).
        The site will no longer be scraped in future research runs."""
        try:
            resp = (
                supabase.table("curated_sites")
                .update({"active": False})
                .eq("site_name", site_name)
                .execute()
            )
            if not resp.data:
                return f"No site named '{site_name}' found."
            return f"Site '{site_name}' has been deactivated and will no longer be scraped."
        except Exception as exc:
            logger.warning(f"remove_curated_site failed | err={exc}")
            return f"Error removing site: {exc}"

    @tool
    def list_curated_sites() -> str:
        """List all curated news sites with their active status, failure count, and last run time."""
        try:
            resp = (
                supabase.table("curated_sites")
                .select("site_name, section_url, active, consecutive_failures, last_run_at, pre_score_threshold")
                .order("site_name")
                .execute()
            )
            sites = resp.data or []
            if not sites:
                return "No curated sites configured."
            lines = []
            for s in sites:
                status = "ACTIVE" if s["active"] else "INACTIVE"
                last_run = s["last_run_at"][:16] if s.get("last_run_at") else "never"
                lines.append(
                    f"[{status}] {s['site_name']} | threshold={s['pre_score_threshold']} "
                    f"| failures={s['consecutive_failures']} | last_run={last_run}"
                )
            return f"{len(sites)} curated site(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning(f"list_curated_sites failed | err={exc}")
            return f"Error listing sites: {exc}"

    @tool
    def get_topic_performance() -> str:
        """Return all topic categories ranked by performance score from the topic_performance_model."""
        try:
            resp = (
                supabase.table("topic_performance_model")
                .select("topic_category, performance_score, sample_count, updated_at")
                .order("performance_score", desc=True)
                .execute()
            )
            rows = resp.data or []
            if not rows:
                return "No topic performance data yet."
            lines = []
            for r in rows:
                lines.append(
                    f"{r['topic_category']}: score={r['performance_score']:.2f} "
                    f"({r['sample_count']} samples)"
                )
            return "Topic performance (best to worst):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning(f"get_topic_performance failed | err={exc}")
            return f"Error fetching topic performance: {exc}"

    @tool
    def get_run_logs(limit: int = 5) -> str:
        """Return the last N agent run logs with timing, cost, and success/failure counts."""
        try:
            resp = (
                supabase.table("run_logs")
                .select("agent_name, trigger_type, success_count, failure_count, duration_seconds, token_cost, created_at")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            rows = resp.data or []
            if not rows:
                return "No run logs found."
            lines = []
            for r in rows:
                cost = r.get("token_cost", {}) or {}
                total_usd = cost.get("total_usd", 0)
                lines.append(
                    f"{r['created_at'][:16]} | {r['agent_name']} ({r['trigger_type']}) "
                    f"| ✓{r['success_count']} ✗{r['failure_count']} "
                    f"| {r['duration_seconds']:.1f}s | ${total_usd:.4f}"
                )
            return f"Last {len(rows)} run log(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning(f"get_run_logs failed | err={exc}")
            return f"Error fetching run logs: {exc}"

    return [
        trigger_research,
        trigger_scoring,
        trigger_creation,
        get_pending_ideas,
        get_analytics_summary,
        add_curated_site,
        remove_curated_site,
        list_curated_sites,
        get_topic_performance,
        get_run_logs,
    ]
```

- [ ] **Step 4: Run tests — expect all pass**

```powershell
cd D:\Intern\content-automation-bot\backend
pytest tests/test_orchestrator_tools.py -v
```

Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/orchestrator/tools.py backend/tests/test_orchestrator_tools.py
git commit -m "feat: add orchestrator tool factory (10 tools for LangGraph ReAct agent)"
```

---

### Task 4 — Orchestrator agent builder

**Files:**
- Create: `backend/app/agents/orchestrator/agent.py`

- [ ] **Step 1: Write `agent.py`**

```python
# backend/app/agents/orchestrator/agent.py
"""
Builds the LangGraph ReAct orchestrator agent.

Usage:
    agent = build_orchestrator_agent(supabase, arq_pool, api_key, model)
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "How many pending ideas?"}]},
        config={"configurable": {"thread_id": "session-abc"}},
    )
    last_message = result["messages"][-1].content
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from supabase import Client

from app.agents.orchestrator.tools import make_tools
from app.utils.logging import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are the operations assistant for an Indian finance content automation pipeline.
You help non-technical operators manage the pipeline through natural language.

Your capabilities:
- Trigger research, scoring, and creation agents
- Check pending ideas and recent agent run history
- Manage curated news sites (add, remove, list)
- View topic performance rankings
- Summarise analytics

Guidelines:
- Be concise and factual. State what you did and the current state.
- When triggering agents, confirm the action and report the job ID.
- When removing a curated site, state clearly that it was deactivated.
- Never fabricate data — use tools to fetch real state.
- If a tool returns an error, report it clearly and suggest what the user can do.
- Financial content note: this pipeline creates educational finance content for Indian audiences.
  It never gives investment advice.
"""


def build_orchestrator_agent(
    supabase: Client,
    arq_pool,
    anthropic_api_key: str,
    model: str = "claude-sonnet-4-6",
):
    """
    Build and return a compiled LangGraph ReAct agent.

    Call once at startup. The returned graph is thread-safe and can be
    called concurrently with different thread_id values in the config.
    """
    tools = make_tools(supabase, arq_pool)
    llm = ChatAnthropic(model=model, api_key=anthropic_api_key)
    memory = MemorySaver()

    agent = create_react_agent(
        model=llm,
        tools=tools,
        checkpointer=memory,
        prompt=_SYSTEM_PROMPT,
    )
    logger.info(f"orchestrator agent built | model={model} | tools={len(tools)}")
    return agent
```

- [ ] **Step 2: Smoke test**

```powershell
cd D:\Intern\content-automation-bot\backend
python -c "
from unittest.mock import MagicMock, AsyncMock
from app.agents.orchestrator.agent import build_orchestrator_agent
sb = MagicMock()
pool = AsyncMock()
agent = build_orchestrator_agent(sb, pool, 'fake-key', 'claude-haiku-4-5')
print('agent built OK, type:', type(agent).__name__)
"
```

Expected: `agent built OK, type: CompiledStateGraph` (or similar LangGraph type name)

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/orchestrator/agent.py
git commit -m "feat: add orchestrator agent builder with LangGraph ReAct and MemorySaver"
```

---

### Task 5 — Orchestrator API router

**Files:**
- Create: `backend/app/api/routers/orchestrator.py`

- [ ] **Step 1: Write the router**

```python
# backend/app/api/routers/orchestrator.py
"""
Orchestrator chat endpoint.

POST /orchestrate
  Request:  { "message": str, "thread_id": str }
  Response: { "response": str, "tools_used": list[str], "thread_id": str }

The agent is built on first call and cached on app.state.orchestrator_agent.
Subsequent calls reuse the same compiled graph (thread-safe; conversation
history is per thread_id via MemorySaver).
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import get_supabase, get_settings
from app.config import Settings
from supabase import Client

router = APIRouter(tags=["Orchestrator"])


class OrchestratorRequest(BaseModel):
    message: str
    thread_id: str


class OrchestratorResponse(BaseModel):
    response: str
    tools_used: list[str]
    thread_id: str


def _get_or_build_agent(request: Request, supabase: Client, settings: Settings):
    """Return cached orchestrator agent, building it on first call."""
    if not hasattr(request.app.state, "orchestrator_agent") or request.app.state.orchestrator_agent is None:
        from app.agents.orchestrator.agent import build_orchestrator_agent
        arq_pool = getattr(request.app.state, "arq_pool", None)
        request.app.state.orchestrator_agent = build_orchestrator_agent(
            supabase=supabase,
            arq_pool=arq_pool,
            anthropic_api_key=settings.anthropic_api_key,
            model=settings.orchestrator_model,
        )
    return request.app.state.orchestrator_agent


@router.post("/orchestrate", response_model=OrchestratorResponse)
async def orchestrate(
    body: OrchestratorRequest,
    request: Request,
    supabase: Client = Depends(get_supabase),
    settings: Settings = Depends(get_settings),
) -> OrchestratorResponse:
    """Send a message to the orchestrator and get a response."""
    if not body.message.strip():
        raise HTTPException(status_code=422, detail="message must not be empty")

    agent = _get_or_build_agent(request, supabase, settings)

    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": body.message}]},
            config={"configurable": {"thread_id": body.thread_id}},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Orchestrator error: {exc}")

    # Extract the final text response from the last AI message
    messages = result.get("messages", [])
    response_text = ""
    for msg in reversed(messages):
        # LangGraph messages are LangChain message objects
        msg_type = type(msg).__name__
        if "AI" in msg_type or "ai" in msg_type.lower():
            content = msg.content
            if isinstance(content, str):
                response_text = content
                break
            elif isinstance(content, list):
                # Can be list of content blocks
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        response_text = block.get("text", "")
                        break
                    elif isinstance(block, str):
                        response_text = block
                        break
                if response_text:
                    break

    # Collect tool names used (from ToolMessage entries)
    tools_used: list[str] = []
    for msg in messages:
        msg_type = type(msg).__name__
        if "Tool" in msg_type:
            name = getattr(msg, "name", None)
            if name and name not in tools_used:
                tools_used.append(name)

    return OrchestratorResponse(
        response=response_text or "No response generated.",
        tools_used=tools_used,
        thread_id=body.thread_id,
    )
```

- [ ] **Step 2: Register in `main.py`**

In `backend/app/api/main.py`, inside `create_app()`, after the knowledge base router block, add:

```python
    from app.api.routers.orchestrator import router as orchestrator_router
    _app.include_router(orchestrator_router)
```

Also set `orchestrator_agent` to None in the lifespan:

```python
    app.state.orchestrator_agent = None
```

Add that line inside the `lifespan` function, right after `app.state.arq_pool = None`.

- [ ] **Step 3: Smoke test**

```powershell
cd D:\Intern\content-automation-bot\backend
python -c "from app.api.main import app; routes = [r.path for r in app.routes]; print([r for r in routes if 'orchestrate' in r])"
```

Expected: `['/orchestrate']`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/routers/orchestrator.py backend/app/api/main.py
git commit -m "feat: add /orchestrate endpoint with lazy agent construction and tool tracking"
```

---

### Task 6 — Frontend api.ts — add `orchestrate` function

**Files:**
- Modify: `frontend/app/lib/api.ts`

- [ ] **Step 1: Add orchestrate function and type**

In `frontend/app/lib/api.ts`, append after the KB functions block (before the generic table browser comment):

```typescript
// --- Orchestrator ---

export interface OrchestratorResponse {
  response: string;
  tools_used: string[];
  thread_id: string;
}

export async function orchestrate(message: string, threadId: string) {
  return apiFetch<OrchestratorResponse>("/orchestrate", {
    method: "POST",
    body: JSON.stringify({ message, thread_id: threadId }),
  });
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```powershell
cd D:\Intern\content-automation-bot\frontend
npx tsc --noEmit 2>&1 | Select-Object -First 20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/lib/api.ts
git commit -m "feat: add orchestrate API function to frontend api.ts"
```

---

### Task 7 — Frontend orchestrator chat page

**Files:**
- Create: `frontend/app/orchestrator/page.tsx`

- [ ] **Step 1: Write the chat page**

```tsx
// frontend/app/orchestrator/page.tsx
"use client";

import { useState, useEffect, useRef } from "react";
import { orchestrate, type OrchestratorResponse } from "../lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  tools_used?: string[];
}

function getOrCreateThreadId(): string {
  if (typeof window === "undefined") return "default";
  const key = "orchestrator_thread_id";
  let tid = localStorage.getItem(key);
  if (!tid) {
    tid = crypto.randomUUID();
    localStorage.setItem(key, tid);
  }
  return tid;
}

export default function OrchestratorPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string>("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setThreadId(getOrCreateThreadId());
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);

    try {
      const result = await orchestrate(text, threadId);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: result.response,
          tools_used: result.tools_used,
        },
      ]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Request failed");
      setMessages((prev) => prev.slice(0, -1)); // Remove optimistic user message
      setInput(text); // Restore input
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const resetThread = () => {
    const key = "orchestrator_thread_id";
    const newId = crypto.randomUUID();
    localStorage.setItem(key, newId);
    setThreadId(newId);
    setMessages([]);
    setError(null);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Orchestrator</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Manage the pipeline with natural language
          </p>
        </div>
        <button
          onClick={resetThread}
          className="px-3 py-1.5 text-xs border border-gray-300 rounded text-gray-600 hover:bg-gray-50"
          title="Start a new conversation"
        >
          New conversation
        </button>
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.length === 0 && (
          <div className="text-center py-16 text-gray-400 text-sm space-y-2">
            <p className="text-2xl">🤖</p>
            <p className="font-medium text-gray-500">Orchestrator ready</p>
            <p>Try: "Show pending ideas", "Add site ET Markets https://...", "Trigger research"</p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-2xl rounded-lg px-4 py-3 text-sm ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-white border border-gray-200 text-gray-800"
              }`}
            >
              <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              {msg.tools_used && msg.tools_used.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {msg.tools_used.map((t) => (
                    <span
                      key={t}
                      className="inline-block px-2 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-500"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-lg px-4 py-3 text-sm text-gray-400">
              <span className="animate-pulse">Thinking...</span>
            </div>
          </div>
        )}

        {error && (
          <div className="flex justify-center">
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-600">
              {error}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 flex gap-3 items-end border-t border-gray-200 pt-4">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          rows={2}
          placeholder="Ask the orchestrator... (Enter to send, Shift+Enter for newline)"
          className="flex-1 resize-none border border-gray-300 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
        />
        <button
          onClick={sendMessage}
          disabled={loading || !input.trim()}
          className="px-5 py-3 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```powershell
cd D:\Intern\content-automation-bot\frontend
npx tsc --noEmit 2>&1 | Select-Object -First 20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/orchestrator/page.tsx
git commit -m "feat: add orchestrator chat UI page"
```

---

### Task 8 — End-to-end smoke test (manual)

This task verifies the full stack works together before declaring the feature complete.

- [ ] **Step 1: Start the backend**

```powershell
cd D:\Intern\content-automation-bot\backend
uvicorn app.api.main:app --reload --port 8001
```

- [ ] **Step 2: Test the endpoint with curl**

In a separate terminal:

```powershell
curl -X POST "http://localhost:8001/orchestrate" `
  -H "Content-Type: application/json" `
  -d '{"message": "List curated sites", "thread_id": "test-thread-1"}'
```

Expected: JSON with `response` containing site names and `tools_used` containing `"list_curated_sites"`.

- [ ] **Step 3: Start the frontend**

```powershell
cd D:\Intern\content-automation-bot\frontend
npm run dev
```

- [ ] **Step 4: Visit `http://localhost:3000/orchestrator`**

Verify:
- Chat page loads with empty state
- Type "How many pending ideas?" and press Enter
- Response appears with tool tags below the message
- "New conversation" button clears the chat

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: orchestrator agent fully wired — LangGraph ReAct with 10 tools and chat UI"
```
