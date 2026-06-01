# Orchestrator Full Tool Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the orchestrator end-to-end pipeline control — approve/reject ideas and drafts, manage brand memory and subscribers, browse all content, all via natural language chat.

**Architecture:** 17 new tools added to `make_tools()` closure in `tools.py` following the exact pattern of existing tools (Supabase via closure, structured logging, never raise, return human-readable string). The `_SYSTEM_PROMPT` in `agent.py` is rewritten to describe the full domain model and instruct the agent to confirm before bulk operations.

**Tech Stack:** Python, LangChain tools, Supabase

---

## File Map

- Modify: `backend/app/agents/orchestrator/tools.py` — 17 new tools inside `make_tools()`
- Modify: `backend/app/agents/orchestrator/agent.py` — rewrite `_SYSTEM_PROMPT`
- Test: `backend/tests/agents/orchestrator/test_orchestrator_tools_expanded.py` — new tests

---

### Task 1: Ideas tools — browse, approve, reject, bulk-reject, send to creation

**Files:**
- Modify: `backend/app/agents/orchestrator/tools.py`
- Test: `backend/tests/agents/orchestrator/test_orchestrator_tools_expanded.py`

- [ ] **Step 1: Write tests for ideas tools**

Create `backend/tests/agents/orchestrator/test_orchestrator_tools_expanded.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
cd D:\Intern\content-automation-bot\backend
python -m pytest tests/agents/orchestrator/test_orchestrator_tools_expanded.py -v 2>&1 | Select-Object -Last 20
```
Expected: FAIL — tools not found yet

- [ ] **Step 3: Add ideas tools to `tools.py`**

Inside `make_tools()`, add these tools after `login_to_site` and before the `return` statement:

```python
    # ── Ideas (Gate 1) ──────────────────────────────────────────────────────

    @tool
    async def get_ideas(
        status: str = "pending_approval",
        platform: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        """Browse content ideas. status: 'pending_approval', 'approved', or 'rejected'.
        Optionally filter by platform (linkedin, twitter, blog, email).
        Returns id, angle, platform, score, and date for each idea."""
        try:
            query = (
                supabase.table("ideas")
                .select("id, angle, platform, score, approval_status, created_at")
                .eq("approval_status", status)
                .order("score", desc=True)
                .limit(limit)
            )
            if platform:
                query = query.eq("platform", platform)
            resp = query.execute()
            ideas = resp.data or []
            if not ideas:
                return f"No {status.replace('_', ' ')} ideas found."
            lines = []
            for i in ideas:
                score = f"score={i['score']:.1f}" if isinstance(i.get('score'), (int, float)) else "score=?"
                lines.append(
                    f"[{i['platform']}] {score} | {i['angle']}\n  id: {i['id']}"
                )
            return f"{len(ideas)} {status.replace('_', ' ')} idea(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("get_ideas failed", extra={"error": str(exc)})
            return f"Error fetching ideas: {exc}"

    @tool
    async def approve_idea(idea_id: str, edited_angle: Optional[str] = None) -> str:
        """Approve a Gate 1 idea. Optionally provide an edited_angle to refine the angle before approving.
        idea_id: the UUID of the idea (from get_ideas output)."""
        try:
            payload: dict = {"approval_status": "approved"}
            if edited_angle:
                payload["edited_angle"] = edited_angle
            resp = supabase.table("ideas").update(payload).eq("id", idea_id).execute()
            if not resp.data:
                return f"Idea {idea_id!r} not found."
            angle = resp.data[0].get("angle") or resp.data[0].get("edited_angle") or idea_id
            return f"✓ Approved idea: {angle!r}"
        except Exception as exc:
            logger.warning("approve_idea failed", extra={"idea_id": idea_id, "error": str(exc)})
            return f"Error approving idea: {exc}"

    @tool
    async def reject_idea(idea_id: str) -> str:
        """Reject a Gate 1 idea.
        idea_id: the UUID of the idea (from get_ideas output)."""
        try:
            resp = supabase.table("ideas").update({"approval_status": "rejected"}).eq("id", idea_id).execute()
            if not resp.data:
                return f"Idea {idea_id!r} not found."
            return f"✓ Rejected idea {idea_id[:8]}…"
        except Exception as exc:
            logger.warning("reject_idea failed", extra={"idea_id": idea_id, "error": str(exc)})
            return f"Error rejecting idea: {exc}"

    @tool
    async def bulk_reject_ideas(idea_ids: list[str]) -> str:
        """Reject multiple ideas at once. ALWAYS confirm the list with the user before calling this.
        idea_ids: list of UUID strings from get_ideas output."""
        if not idea_ids:
            return "Error: idea_ids must not be empty."
        count = 0
        errors = []
        for idea_id in idea_ids:
            try:
                supabase.table("ideas").update({"approval_status": "rejected"}).eq("id", idea_id).execute()
                count += 1
            except Exception as exc:
                errors.append(f"{idea_id[:8]}: {exc}")
        result = f"✓ Rejected {count}/{len(idea_ids)} idea(s)."
        if errors:
            result += f"\nFailed: {'; '.join(errors)}"
        return result

    @tool
    async def send_ideas_to_creation(
        idea_ids: list[str],
        content_type: str = "news_driven",
    ) -> str:
        """Send approved ideas to the creation agent to generate drafts.
        content_type: 'news_driven', 'kb_driven', or 'combined'.
        idea_ids: list of approved idea UUIDs."""
        if not idea_ids:
            return "Error: idea_ids must not be empty."
        if content_type not in {"news_driven", "kb_driven", "combined"}:
            return f"Error: invalid content_type '{content_type}'. Use: news_driven, kb_driven, combined."
        if arq_pool is None:
            return "Error: job queue unavailable (Redis not connected)."
        try:
            job = await arq_pool.enqueue_job(
                "creation_agent_task",
                idea_ids=idea_ids,
                content_type=content_type,
            )
            job_id = job.job_id if job else "unknown"
            return (
                f"✓ Creation queued for {len(idea_ids)} idea(s) "
                f"(content_type={content_type}, job_id={job_id})."
            )
        except Exception as exc:
            logger.warning("send_ideas_to_creation failed", extra={"error": str(exc)})
            return f"Error triggering creation: {exc}"
```

- [ ] **Step 4: Run tests**

```powershell
python -m pytest tests/agents/orchestrator/test_orchestrator_tools_expanded.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```powershell
git add backend/app/agents/orchestrator/tools.py \
        backend/tests/agents/orchestrator/test_orchestrator_tools_expanded.py
git commit -m "feat: add ideas tools to orchestrator (get, approve, reject, bulk-reject, send-to-creation)"
```

---

### Task 2: Drafts tools

**Files:**
- Modify: `backend/app/agents/orchestrator/tools.py`
- Modify: `backend/tests/agents/orchestrator/test_orchestrator_tools_expanded.py`

- [ ] **Step 1: Add draft tests**

Append to `test_orchestrator_tools_expanded.py`:

```python
# ── Drafts ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_drafts_returns_string():
    sb = _make_sb()
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"id": "d-1", "platform": "linkedin", "content_text": "Draft post text here.",
         "approval_status": "pending_approval", "created_at": "2026-06-01T10:00:00+00:00",
         "finance_flags": []}
    ]
    tools = make_tools(supabase=sb, arq_pool=None)
    tool = next(t for t in tools if t.name == "get_drafts")
    result = await tool.ainvoke({"status": "pending_approval"})
    assert "linkedin" in result
    assert "Draft post" in result


@pytest.mark.asyncio
async def test_approve_draft_updates_status():
    sb = _make_sb()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "d-1"}]
    tools = make_tools(supabase=sb, arq_pool=None)
    tool = next(t for t in tools if t.name == "approve_draft")
    result = await tool.ainvoke({"draft_id": "d-1"})
    assert "approved" in result.lower()


@pytest.mark.asyncio
async def test_reject_draft_updates_status():
    sb = _make_sb()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "d-1"}]
    tools = make_tools(supabase=sb, arq_pool=None)
    tool = next(t for t in tools if t.name == "reject_draft")
    result = await tool.ainvoke({"draft_id": "d-1"})
    assert "rejected" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/agents/orchestrator/test_orchestrator_tools_expanded.py::test_get_drafts_returns_string -v
```
Expected: FAIL

- [ ] **Step 3: Add draft tools to `tools.py`** (inside `make_tools()`)

```python
    # ── Drafts (Gate 2) ─────────────────────────────────────────────────────

    @tool
    async def get_drafts(
        status: str = "pending_approval",
        platform: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        """Browse content drafts. status: 'pending_approval', 'approved', or 'rejected'.
        Shows platform, preview of content, finance flags, and date."""
        try:
            query = (
                supabase.table("drafts")
                .select("id, platform, content_text, finance_flags, approval_status, created_at")
                .eq("approval_status", status)
                .order("created_at", desc=True)
                .limit(limit)
            )
            if platform:
                query = query.eq("platform", platform)
            resp = query.execute()
            drafts = resp.data or []
            if not drafts:
                return f"No {status.replace('_', ' ')} drafts found."
            lines = []
            for d in drafts:
                preview = (d.get("content_text") or "")[:120].replace("\n", " ")
                flags = d.get("finance_flags") or []
                flag_str = f" ⚠ {len(flags)} flag(s)" if flags else ""
                lines.append(
                    f"[{d['platform']}]{flag_str} | {preview}…\n  id: {d['id']}"
                )
            return f"{len(drafts)} {status.replace('_', ' ')} draft(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("get_drafts failed", extra={"error": str(exc)})
            return f"Error fetching drafts: {exc}"

    @tool
    async def approve_draft(draft_id: str, scheduled_at: Optional[str] = None) -> str:
        """Approve a Gate 2 draft for publishing.
        draft_id: UUID from get_drafts output.
        scheduled_at: optional ISO datetime string (e.g. '2026-06-02T09:00:00+05:30')."""
        try:
            payload: dict = {"approval_status": "approved"}
            if scheduled_at:
                payload["scheduled_at"] = scheduled_at
            resp = supabase.table("drafts").update(payload).eq("id", draft_id).execute()
            if not resp.data:
                return f"Draft {draft_id!r} not found."
            sched = f" (scheduled: {scheduled_at})" if scheduled_at else ""
            return f"✓ Approved draft {draft_id[:8]}…{sched}"
        except Exception as exc:
            logger.warning("approve_draft failed", extra={"draft_id": draft_id, "error": str(exc)})
            return f"Error approving draft: {exc}"

    @tool
    async def reject_draft(draft_id: str) -> str:
        """Reject a Gate 2 draft.
        draft_id: UUID from get_drafts output."""
        try:
            resp = supabase.table("drafts").update({"approval_status": "rejected"}).eq("id", draft_id).execute()
            if not resp.data:
                return f"Draft {draft_id!r} not found."
            return f"✓ Rejected draft {draft_id[:8]}…"
        except Exception as exc:
            logger.warning("reject_draft failed", extra={"draft_id": draft_id, "error": str(exc)})
            return f"Error rejecting draft: {exc}"
```

- [ ] **Step 4: Run tests**

```powershell
python -m pytest tests/agents/orchestrator/test_orchestrator_tools_expanded.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```powershell
git add backend/app/agents/orchestrator/tools.py \
        backend/tests/agents/orchestrator/test_orchestrator_tools_expanded.py
git commit -m "feat: add drafts tools to orchestrator (get, approve, reject)"
```

---

### Task 3: Brand memory, subscribers, and content browsing tools

**Files:**
- Modify: `backend/app/agents/orchestrator/tools.py`
- Modify: `backend/tests/agents/orchestrator/test_orchestrator_tools_expanded.py`

- [ ] **Step 1: Add tests**

Append to `test_orchestrator_tools_expanded.py`:

```python
# ── Brand memory ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_brand_memory_inserts_row():
    sb = _make_sb()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "bm-1"}]
    tools = make_tools(supabase=sb, arq_pool=None)
    tool = next(t for t in tools if t.name == "add_brand_memory")
    result = await tool.ainvoke({"content": "Great LinkedIn post about GST.", "platform": "linkedin"})
    assert "saved" in result.lower() or "added" in result.lower()
    sb.table.assert_any_call("brand_memory")


@pytest.mark.asyncio
async def test_list_brand_memory_returns_string():
    sb = _make_sb()
    sb.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"id": "bm-1", "platform": "linkedin", "content": "Post about mutual funds.", "created_at": "2026-06-01T10:00:00+00:00"}
    ]
    tools = make_tools(supabase=sb, arq_pool=None)
    tool = next(t for t in tools if t.name == "list_brand_memory")
    result = await tool.ainvoke({})
    assert "mutual funds" in result.lower()


# ── Subscribers ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_email_subscriber_inserts():
    sb = _make_sb()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "sub-1"}]
    tools = make_tools(supabase=sb, arq_pool=None)
    tool = next(t for t in tools if t.name == "add_email_subscriber")
    result = await tool.ainvoke({"email": "test@example.com"})
    assert "added" in result.lower() or "subscribed" in result.lower()


@pytest.mark.asyncio
async def test_remove_email_subscriber_deactivates():
    sb = _make_sb()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "sub-1"}]
    tools = make_tools(supabase=sb, arq_pool=None)
    tool = next(t for t in tools if t.name == "remove_email_subscriber")
    result = await tool.ainvoke({"email": "test@example.com"})
    assert "removed" in result.lower() or "deactivated" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/agents/orchestrator/test_orchestrator_tools_expanded.py -k "brand_memory or subscriber" -v
```
Expected: FAIL

- [ ] **Step 3: Add tools to `tools.py`**

```python
    # ── Brand memory ─────────────────────────────────────────────────────────

    @tool
    async def add_brand_memory(content: str, platform: str) -> str:
        """Save a piece of brand content (e.g. a LinkedIn post you wrote) as a style reference.
        The creation agent will use these examples to match your brand voice when generating new posts.
        platform: 'linkedin', 'twitter', 'blog', or 'email'."""
        try:
            resp = supabase.table("brand_memory").insert({
                "content": content,
                "platform": platform,
                "performance_metrics": {},
            }).execute()
            if resp.data:
                return f"✓ Saved to brand memory for {platform} (id={resp.data[0].get('id', '?')[:8]}…)"
            return f"Saved to brand memory for {platform}."
        except Exception as exc:
            logger.warning("add_brand_memory failed", extra={"error": str(exc)})
            return f"Error adding brand memory: {exc}"

    @tool
    async def list_brand_memory(platform: Optional[str] = None, limit: int = 5) -> str:
        """List recent brand memory posts used as style reference by the creation agent.
        Optionally filter by platform."""
        try:
            query = (
                supabase.table("brand_memory")
                .select("id, platform, content, created_at")
                .order("created_at", desc=True)
                .limit(limit)
            )
            if platform:
                query = query.eq("platform", platform)
            resp = query.execute()
            rows = resp.data or []
            if not rows:
                return "No brand memory entries found."
            lines = [
                f"[{r['platform']}] {(r.get('content') or '')[:100]}…\n  id: {r['id']}"
                for r in rows
            ]
            return f"{len(rows)} brand memory entry(ies):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("list_brand_memory failed", extra={"error": str(exc)})
            return f"Error listing brand memory: {exc}"

    # ── Email subscribers ─────────────────────────────────────────────────────

    @tool
    async def list_subscribers(limit: int = 10) -> str:
        """List active email subscribers."""
        try:
            resp = (
                supabase.table("email_subscribers")
                .select("id, email, name, created_at")
                .eq("active", True)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            rows = resp.data or []
            if not rows:
                return "No active subscribers found."
            lines = [
                f"{r.get('name') or '—'} <{r['email']}>"
                for r in rows
            ]
            return f"{len(rows)} active subscriber(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("list_subscribers failed", extra={"error": str(exc)})
            return f"Error listing subscribers: {exc}"

    @tool
    async def add_email_subscriber(email: str, name: Optional[str] = None) -> str:
        """Add a new email subscriber.
        email: valid email address. name: optional display name."""
        import uuid as _uuid
        try:
            resp = supabase.table("email_subscribers").insert({
                "email": email,
                "name": name or None,
                "active": True,
                "unsubscribe_token": str(_uuid.uuid4()),
            }).execute()
            if resp.data:
                return f"✓ Added subscriber: {email}"
            return f"Added subscriber: {email}"
        except Exception as exc:
            logger.warning("add_email_subscriber failed", extra={"email": email, "error": str(exc)})
            return f"Error adding subscriber: {exc}"

    @tool
    async def remove_email_subscriber(email: str) -> str:
        """Deactivate (soft-delete) an email subscriber by email address."""
        try:
            resp = (
                supabase.table("email_subscribers")
                .update({"active": False})
                .eq("email", email)
                .execute()
            )
            if not resp.data:
                return f"No subscriber found with email {email!r}."
            return f"✓ Removed subscriber: {email}"
        except Exception as exc:
            logger.warning("remove_email_subscriber failed", extra={"email": email, "error": str(exc)})
            return f"Error removing subscriber: {exc}"

    # ── Content browsing ──────────────────────────────────────────────────────

    @tool
    async def get_decision_summaries(limit: int = 5) -> str:
        """Show recent rejection pattern summaries — AI-generated analyses of why ideas were rejected.
        Useful for understanding what content to avoid."""
        try:
            resp = (
                supabase.table("user_decision_summaries")
                .select("summary_text, rejection_count, created_at")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            rows = resp.data or []
            if not rows:
                return "No decision summaries yet."
            lines = [
                f"[{r['created_at'][:10]}] ({r['rejection_count']} rejections)\n{r['summary_text']}"
                for r in rows
            ]
            return "\n\n".join(lines)
        except Exception as exc:
            logger.warning("get_decision_summaries failed", extra={"error": str(exc)})
            return f"Error fetching decision summaries: {exc}"

    @tool
    async def get_recent_articles(limit: int = 5, source_name: Optional[str] = None) -> str:
        """Browse recently scraped articles from the research pipeline.
        Optionally filter by source_name (e.g. 'ET Markets', 'LiveMint')."""
        try:
            query = (
                supabase.table("raw_content")
                .select("id, title, source_name, pre_score, word_count, created_at, url")
                .order("created_at", desc=True)
                .limit(limit)
            )
            if source_name:
                query = query.eq("source_name", source_name)
            resp = query.execute()
            rows = resp.data or []
            if not rows:
                return "No articles found."
            lines = [
                f"[{r['source_name']}] score={r.get('pre_score', '?')} | {r['title']}\n  {r['url'][:80]}"
                for r in rows
            ]
            return f"{len(rows)} article(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("get_recent_articles failed", extra={"error": str(exc)})
            return f"Error fetching articles: {exc}"

    @tool
    async def get_published_posts(platform: Optional[str] = None, limit: int = 5) -> str:
        """Show recently published posts. Optionally filter by platform."""
        try:
            query = (
                supabase.table("published_posts")
                .select("id, platform, published_at, content_preview")
                .order("published_at", desc=True)
                .limit(limit)
            )
            if platform:
                query = query.eq("platform", platform)
            resp = query.execute()
            rows = resp.data or []
            if not rows:
                return "No published posts found."
            lines = [
                f"[{r['platform']}] {(r.get('published_at') or '')[:10]} | {(r.get('content_preview') or '')[:80]}…"
                for r in rows
            ]
            return f"{len(rows)} published post(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("get_published_posts failed", extra={"error": str(exc)})
            return f"Error fetching published posts: {exc}"

    @tool
    async def list_kb_files() -> str:
        """List knowledge base files that have been uploaded and chunked for retrieval."""
        try:
            resp = (
                supabase.table("knowledge_base")
                .select("source_file, chunk_index, created_at")
                .order("source_file")
                .execute()
            )
            rows = resp.data or []
            if not rows:
                return "No knowledge base files uploaded."
            files: dict[str, int] = {}
            for r in rows:
                files[r["source_file"]] = files.get(r["source_file"], 0) + 1
            lines = [f"{fname} ({count} chunks)" for fname, count in files.items()]
            return f"{len(files)} KB file(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("list_kb_files failed", extra={"error": str(exc)})
            return f"Error listing KB files: {exc}"
```

- [ ] **Step 4: Add all new tools to the return list**

At the bottom of `make_tools()`, update the return to include all new tools:
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
    ]
```

- [ ] **Step 5: Run all orchestrator tests**

```powershell
python -m pytest tests/agents/orchestrator/ -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```powershell
git add backend/app/agents/orchestrator/tools.py \
        backend/tests/agents/orchestrator/test_orchestrator_tools_expanded.py
git commit -m "feat: add 14 more orchestrator tools (brand memory, subscribers, browsing, KB)"
```

---

### Task 4: Rewrite `_SYSTEM_PROMPT` in `agent.py`

**Files:**
- Modify: `backend/app/agents/orchestrator/agent.py`

- [ ] **Step 1: Replace `_SYSTEM_PROMPT`**

In `backend/app/agents/orchestrator/agent.py`, replace the entire `_SYSTEM_PROMPT` string:

```python
_SYSTEM_PROMPT = """You are the operations assistant for Growthvine Capital's Indian finance content automation pipeline.
You have complete end-to-end control over the pipeline through natural language.

## Pipeline Overview
The pipeline has two approval gates:
- Gate 1 (Ideas): Research agent scrapes articles → Scoring agent generates content ideas → YOU approve/reject
- Gate 2 (Drafts): Creation agent writes drafts from approved ideas → YOU approve/reject → Publishing agent publishes

## Your Full Capabilities

### Pipeline Control
- trigger_research — scrape new articles from curated news sites
- trigger_scoring — generate content ideas from unprocessed articles
- send_ideas_to_creation — queue approved ideas for draft generation
- trigger_creation (legacy, same as send_ideas_to_creation)

### Gate 1 — Ideas
- get_ideas(status, platform, limit) — browse ideas by status
- approve_idea(idea_id, edited_angle?) — approve; optionally refine the angle
- reject_idea(idea_id) — reject one idea
- bulk_reject_ideas(idea_ids) — reject many at once

### Gate 2 — Drafts
- get_drafts(status, platform, limit) — browse drafts
- approve_draft(draft_id, scheduled_at?) — approve for publishing
- reject_draft(draft_id) — reject

### Brand & Audience
- add_brand_memory(content, platform) — save a post as style reference for the creation agent
- list_brand_memory(platform, limit) — see style reference posts
- list_subscribers(limit) — see email subscribers
- add_email_subscriber(email, name?) — add subscriber
- remove_email_subscriber(email) — deactivate subscriber

### Content Browsing
- get_recent_articles(limit, source_name?) — scraped raw articles
- get_decision_summaries(limit) — AI analysis of rejection patterns
- get_published_posts(platform, limit) — published content history

### Analytics & Ops
- get_analytics_summary — recent run logs + platform performance averages
- get_run_logs(limit) — detailed agent run history
- get_topic_performance — topic categories ranked by performance
- list_kb_files — knowledge base files uploaded for retrieval
- add_curated_site / remove_curated_site / list_curated_sites — manage news sources
- login_to_site(url) — open browser to log in to a paywalled news site

## Behavioural Rules

1. **Listing ideas/drafts**: Always show id (first 8 chars), angle/preview, platform, and score. Never show full UUIDs.

2. **Single actions** (approve_idea, reject_idea, approve_draft, reject_draft): Just do it immediately. No confirmation needed for single items.

3. **Bulk actions** (bulk_reject_ideas with >3 items): ALWAYS show the list first and ask "Shall I reject all N of these?" before calling the tool.

4. **Triggering agents**: Report the job_id and tell the user they can check progress on the Dashboard.

5. **Tone**: Concise and factual. State what you did and what the current state is. No filler.

6. **Financial content**: This pipeline creates educational finance content for Indian audiences. Never generate investment advice.

7. **Unknown requests**: If asked to do something not covered by your tools, say clearly what you can and cannot do.
"""
```

- [ ] **Step 2: Run full test suite**

```powershell
cd D:\Intern\content-automation-bot\backend
python -m pytest tests/ -q
```
Expected: all PASS (system prompt change doesn't affect tests)

- [ ] **Step 3: Commit**

```powershell
git add backend/app/agents/orchestrator/agent.py
git commit -m "feat: rewrite orchestrator system prompt for full end-to-end pipeline control"
```
