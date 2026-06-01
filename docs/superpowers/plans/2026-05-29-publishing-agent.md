# Publishing Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Publishing Agent — polls approved drafts every 15 minutes, posts to platform (stub implementations), records in `published_posts`, updates draft status, and schedules analytics arq jobs.

**Architecture:** Two modules under `app/agents/publishing/`. `poster.py` contains stub platform posters (no real API calls — returns generated identifiers). `db_writer.py` handles DB writes. `publishing_agent_task` in `tasks.py` orchestrates the loop. Analytics jobs are scheduled via `ctx["redis"]` (the arq pool injected by the worker into the task context).

**Tech Stack:** arq (existing), Supabase (existing)

---

### Task 33: Platform poster + DB writer modules

**Files:**
- Create: `backend/app/agents/publishing/__init__.py`
- Create: `backend/app/agents/publishing/poster.py`
- Create: `backend/app/agents/publishing/db_writer.py`
- Create: `backend/tests/agents/publishing/__init__.py`
- Create: `backend/tests/agents/publishing/test_poster.py`
- Create: `backend/tests/agents/publishing/test_db_writer.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/agents/publishing/test_poster.py
"""Tests for publishing poster module."""
from unittest.mock import MagicMock
from app.agents.publishing.poster import post_to_platform


def test_post_to_platform_linkedin_returns_identifier():
    settings = MagicMock()
    result = post_to_platform("linkedin", "LinkedIn post content.", settings)
    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0


def test_post_to_platform_twitter_returns_identifier():
    settings = MagicMock()
    result = post_to_platform("twitter", "Twitter thread content.", settings)
    assert result is not None
    assert isinstance(result, str)


def test_post_to_platform_blog_returns_identifier():
    settings = MagicMock()
    result = post_to_platform("blog", "Blog post outline.", settings)
    assert result is not None


def test_post_to_platform_email_returns_identifier():
    settings = MagicMock()
    result = post_to_platform("email", "Email newsletter.", settings)
    assert result is not None


def test_post_to_platform_unknown_returns_none():
    settings = MagicMock()
    result = post_to_platform("unknown_platform", "content", settings)
    assert result is None


def test_post_to_platform_never_raises():
    settings = MagicMock()
    # Should not raise even on unexpected input
    result = post_to_platform("linkedin", "", settings)
    assert isinstance(result, (str, type(None)))
```

```python
# backend/tests/agents/publishing/test_db_writer.py
"""Tests for publishing db_writer."""
from unittest.mock import MagicMock
from uuid import UUID

from app.agents.publishing.db_writer import write_published_post, update_draft_published


_DRAFT_ID = UUID("00000000-0000-0000-0000-000000000001")


def test_write_published_post_returns_id():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "post-uuid-001"}
    ]
    result = write_published_post(sb, "linkedin", "linkedin-stub-abc123", _DRAFT_ID)
    assert result == "post-uuid-001"


def test_write_published_post_returns_none_on_empty_data():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = []
    result = write_published_post(sb, "twitter", "twitter-stub-xyz", _DRAFT_ID)
    assert result is None


def test_write_published_post_returns_none_on_exception():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.side_effect = RuntimeError("DB error")
    result = write_published_post(sb, "blog", "blog-stub-123", None)
    assert result is None


def test_write_published_post_serialises_draft_id_as_string():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "x"}]
    write_published_post(sb, "linkedin", "post-id", _DRAFT_ID)
    payload = sb.table.return_value.insert.call_args[0][0]
    assert payload["draft_id"] == str(_DRAFT_ID)
    assert isinstance(payload["draft_id"], str)


def test_write_published_post_none_draft_id_passed_as_none():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "x"}]
    write_published_post(sb, "email", "email-id", None)
    payload = sb.table.return_value.insert.call_args[0][0]
    assert payload["draft_id"] is None


def test_update_draft_published_calls_update():
    sb = MagicMock()
    update_draft_published(sb, _DRAFT_ID)
    sb.table.assert_called_with("drafts")
    update_call = sb.table.return_value.update.call_args[0][0]
    assert update_call["approval_status"] == "published"


def test_update_draft_published_never_raises():
    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.side_effect = RuntimeError("DB error")
    # Should not raise
    update_draft_published(sb, _DRAFT_ID)
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/agents/publishing/test_poster.py tests/agents/publishing/test_db_writer.py -v
```
Expected: ERROR (ImportError)

- [ ] **Step 3: Create `backend/app/agents/publishing/__init__.py`**

Empty file.

- [ ] **Step 4: Create `backend/tests/agents/publishing/__init__.py`**

Empty file.

- [ ] **Step 5: Create `backend/app/agents/publishing/poster.py`**

```python
"""
Platform posting stubs for the publishing agent.

These are no-ops that simulate successful posting and return a generated identifier.
Replace each function with a real API call when platform credentials are available.
"""
import uuid
from typing import Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)


def post_linkedin(content_text: str, settings) -> str:
    """Post to LinkedIn. Stub — logs and returns a generated identifier."""
    logger.info(f"poster: [STUB] LinkedIn | chars={len(content_text)}")
    return f"linkedin-stub-{uuid.uuid4().hex[:8]}"


def post_twitter(content_text: str, settings) -> str:
    """Post a Twitter thread. Stub — logs and returns a generated identifier."""
    logger.info(f"poster: [STUB] Twitter | chars={len(content_text)}")
    return f"twitter-stub-{uuid.uuid4().hex[:8]}"


def post_blog(content_text: str, settings) -> str:
    """Publish a blog post. Stub — logs and returns a generated identifier."""
    logger.info(f"poster: [STUB] Blog | chars={len(content_text)}")
    return f"blog-stub-{uuid.uuid4().hex[:8]}"


def post_email(content_text: str, settings) -> str:
    """Send an email newsletter. Stub — logs and returns a generated identifier."""
    logger.info(f"poster: [STUB] Email | chars={len(content_text)}")
    return f"email-stub-{uuid.uuid4().hex[:8]}"


_PLATFORM_POSTERS = {
    "linkedin": post_linkedin,
    "twitter":  post_twitter,
    "blog":     post_blog,
    "email":    post_email,
}


def post_to_platform(platform: str, content_text: str, settings) -> Optional[str]:
    """
    Dispatch to the correct platform poster.

    Returns a post_identifier string on success.
    Returns None if the platform is unknown or an error occurs.
    Never raises.
    """
    poster = _PLATFORM_POSTERS.get(platform)
    if poster is None:
        logger.error(f"post_to_platform: unknown platform | platform={platform}")
        return None
    try:
        return poster(content_text, settings)
    except Exception as exc:
        logger.error(f"post_to_platform: failed | platform={platform} | err={exc}")
        return None
```

- [ ] **Step 6: Create `backend/app/agents/publishing/db_writer.py`**

```python
"""
DB write operations for the publishing agent.
"""
from typing import Optional
from uuid import UUID

from app.utils.logging import get_logger

logger = get_logger(__name__)


def write_published_post(
    supabase,
    platform: str,
    post_identifier: str,
    draft_id: Optional[UUID],
) -> Optional[str]:
    """
    Insert a record into published_posts.
    Returns the new post UUID string on success, or None on failure. Never raises.
    """
    try:
        payload = {
            "platform":        platform,
            "post_identifier": post_identifier,
            "draft_id":        str(draft_id) if draft_id else None,
        }
        resp = supabase.table("published_posts").insert(payload).execute()
        if not resp.data:
            logger.warning("write_published_post: insert returned no data")
            return None
        return resp.data[0]["id"]
    except Exception as exc:
        logger.error(f"write_published_post: failed | platform={platform} | err={exc}")
        return None


def update_draft_published(supabase, draft_id: UUID) -> None:
    """
    Set the draft's approval_status to 'published'.
    Never raises.
    """
    try:
        supabase.table("drafts").update(
            {"approval_status": "published"}
        ).eq("id", str(draft_id)).execute()
    except Exception as exc:
        logger.error(f"update_draft_published: failed | id={draft_id} | err={exc}")
```

- [ ] **Step 7: Run tests**

```
pytest tests/agents/publishing/test_poster.py tests/agents/publishing/test_db_writer.py -v
```
Expected: all PASSED

- [ ] **Step 8: Run full suite**

```
pytest tests/ --ignore=tests/agents/research/test_install.py -q
```
Expected: all pass

- [ ] **Step 9: Commit**

```bash
git add app/agents/publishing/__init__.py app/agents/publishing/poster.py app/agents/publishing/db_writer.py tests/agents/publishing/__init__.py tests/agents/publishing/test_poster.py tests/agents/publishing/test_db_writer.py
git commit -m "feat: add publishing agent poster and db_writer modules"
```

---

### Task 34: Wire publishing_agent_task orchestration loop

**Files:**
- Modify: `backend/app/queue/tasks.py` — replace stub with real implementation
- Create: `backend/tests/queue/test_publishing_task.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/queue/test_publishing_task.py
"""Tests for publishing_agent_task orchestration loop."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from app.queue.tasks import publishing_agent_task


def _make_ctx(with_redis=True):
    settings = MagicMock()
    supabase = MagicMock()
    ctx = {"settings": settings, "supabase": supabase}
    if with_redis:
        ctx["redis"] = AsyncMock()
    return ctx


def _make_draft_data(draft_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", platform="linkedin"):
    return {
        "id": draft_id,
        "platform": platform,
        "content_text": "LinkedIn post content here.",
        "agent_reasoning": "Good angle.",
        "source_idea_id": None,
        "finance_flags": [],
        "suggested_publish_time": None,
        "scheduled_at": "2026-05-29T00:00:00+00:00",
        "approval_status": "approved",
        "created_at": "2026-05-29T00:00:00+00:00",
        "updated_at": "2026-05-29T00:00:00+00:00",
    }


# ─── happy path ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_publishing_task_publishes_one_draft():
    ctx = _make_ctx()
    draft_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    ctx["supabase"].table.return_value.select.return_value.eq.return_value \
        .lte.return_value.execute.return_value.data = [_make_draft_data(draft_id)]

    with (
        patch("app.agents.publishing.poster.post_to_platform", return_value="linkedin-stub-abc"),
        patch("app.agents.publishing.db_writer.write_published_post", return_value="post-uuid-001"),
        patch("app.agents.publishing.db_writer.update_draft_published"),
    ):
        result = await publishing_agent_task(ctx)

    assert result["status"] == "done"
    assert result["processed"] == 1
    assert result["published"] == 1
    assert result["failures"] == 0


@pytest.mark.asyncio
async def test_publishing_task_schedules_analytics_jobs():
    ctx = _make_ctx(with_redis=True)
    draft_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    ctx["supabase"].table.return_value.select.return_value.eq.return_value \
        .lte.return_value.execute.return_value.data = [_make_draft_data(draft_id)]

    with (
        patch("app.agents.publishing.poster.post_to_platform", return_value="linkedin-stub-xyz"),
        patch("app.agents.publishing.db_writer.write_published_post", return_value="post-uuid-002"),
        patch("app.agents.publishing.db_writer.update_draft_published"),
    ):
        await publishing_agent_task(ctx)

    # 3 analytics jobs scheduled: 24h, 72h, 7d
    assert ctx["redis"].enqueue_job.call_count == 3
    call_args_list = ctx["redis"].enqueue_job.call_args_list
    periods = [call[0][0] for call in call_args_list]
    assert periods == ["analytics_agent_task", "analytics_agent_task", "analytics_agent_task"]


@pytest.mark.asyncio
async def test_publishing_task_no_redis_skips_analytics():
    ctx = _make_ctx(with_redis=False)
    draft_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"

    ctx["supabase"].table.return_value.select.return_value.eq.return_value \
        .lte.return_value.execute.return_value.data = [_make_draft_data(draft_id)]

    with (
        patch("app.agents.publishing.poster.post_to_platform", return_value="linkedin-stub-abc"),
        patch("app.agents.publishing.db_writer.write_published_post", return_value="post-uuid-003"),
        patch("app.agents.publishing.db_writer.update_draft_published"),
    ):
        result = await publishing_agent_task(ctx)

    assert result["status"] == "done"
    assert result["published"] == 1  # still published even without analytics scheduling


@pytest.mark.asyncio
async def test_publishing_task_counts_failure_when_post_returns_none():
    ctx = _make_ctx()
    draft_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"

    ctx["supabase"].table.return_value.select.return_value.eq.return_value \
        .lte.return_value.execute.return_value.data = [_make_draft_data(draft_id)]

    with patch("app.agents.publishing.poster.post_to_platform", return_value=None):
        result = await publishing_agent_task(ctx)

    assert result["status"] == "done"
    assert result["published"] == 0
    assert result["failures"] == 1


@pytest.mark.asyncio
async def test_publishing_task_empty_drafts_returns_done():
    ctx = _make_ctx()
    ctx["supabase"].table.return_value.select.return_value.eq.return_value \
        .lte.return_value.execute.return_value.data = []

    result = await publishing_agent_task(ctx)

    assert result["status"] == "done"
    assert result["processed"] == 0
    assert result["published"] == 0


@pytest.mark.asyncio
async def test_publishing_task_returns_error_on_fetch_failure():
    ctx = _make_ctx()
    ctx["supabase"].table.return_value.select.return_value.eq.return_value \
        .lte.return_value.execute.side_effect = RuntimeError("db down")

    result = await publishing_agent_task(ctx)

    assert result["status"] == "error"
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/queue/test_publishing_task.py -v
```
Expected: some tests fail (stub returns `{"status": "stub"}`)

- [ ] **Step 3: Replace `publishing_agent_task` stub in `app/queue/tasks.py`**

Read `app/queue/tasks.py` first. Replace the entire body of `publishing_agent_task` with:

```python
async def publishing_agent_task(ctx: dict) -> dict:
    """
    Publishing agent — posts approved drafts that are due.
    Triggered: every 15 minutes by cron.
    """
    import time
    from datetime import datetime, timezone, timedelta
    from app.agents.publishing.poster import post_to_platform
    from app.agents.publishing.db_writer import write_published_post, update_draft_published
    from app.utils.logging import log_agent_decision
    from app.db.models import Draft, RunLogCreate, TriggerType

    settings = ctx["settings"]
    supabase = ctx["supabase"]
    arq_pool = ctx.get("redis")   # arq injects "redis" key into task ctx
    start_time = time.time()

    processed_count = 0
    published_count = 0
    failure_count = 0
    errors: list[dict] = []
    trace_entries: list[str] = []

    now = datetime.now(timezone.utc)

    try:
        resp = (
            supabase.table("drafts")
            .select("*")
            .eq("approval_status", "approved")
            .lte("scheduled_at", now.isoformat())
            .execute()
        )
        drafts = [Draft(**d) for d in (resp.data or [])]
    except Exception as exc:
        logger.error(f"publishing_agent_task: failed to fetch drafts | err={exc}")
        return {
            "status": "error",
            "processed": 0,
            "published": 0,
            "failures": 0,
            "duration_seconds": round(time.time() - start_time, 2),
            "error": str(exc),
        }

    for draft in drafts:
        processed_count += 1
        try:
            # Step 1 — Post to platform
            post_identifier = post_to_platform(draft.platform.value, draft.content_text, settings)
            if post_identifier is None:
                failure_count += 1
                errors.append({"draft_id": str(draft.id), "error": "post_to_platform returned None"})
                continue

            # Step 2 — Record in published_posts
            post_id = write_published_post(supabase, draft.platform.value, post_identifier, draft.id)
            if post_id is None:
                failure_count += 1
                errors.append({"draft_id": str(draft.id), "error": "write_published_post failed"})
                continue

            # Step 3 — Update draft status to published
            update_draft_published(supabase, draft.id)

            # Step 4 — Schedule analytics jobs (24h, 72h, 7d)
            if arq_pool is not None:
                for period, hours in [("24h", 24), ("72h", 72), ("7d", 168)]:
                    await arq_pool.enqueue_job(
                        "analytics_agent_task",
                        post_id=post_id,
                        measurement_period=period,
                        _defer_by=timedelta(hours=hours),
                    )

            published_count += 1
            trace_entries.append(log_agent_decision(
                logger, "draft_published", "Published and analytics scheduled",
                {"draft_id": str(draft.id), "platform": draft.platform.value, "post_id": post_id},
            ))

        except Exception as exc:
            logger.error(f"publishing_agent_task: draft error | id={draft.id} | err={exc}")
            errors.append({"draft_id": str(draft.id), "error": str(exc)})
            failure_count += 1

    duration = time.time() - start_time

    run_log = RunLogCreate(
        agent_name="publishing_agent",
        trigger_type=TriggerType.CRON,
        processed_count=processed_count,
        success_count=published_count,
        failure_count=failure_count,
        duration_seconds=round(duration, 2),
        reasoning_trace="\n".join(trace_entries) if trace_entries else None,
        errors=errors,
        token_cost={"total_usd": 0.0},
    )
    try:
        supabase.table("run_logs").insert(run_log.model_dump()).execute()
    except Exception as exc:
        logger.error(f"publishing_agent_task: failed to write run_log | err={exc}")

    logger.info(
        f"publishing_agent_task done | processed={processed_count} "
        f"published={published_count} failures={failure_count} "
        f"duration={duration:.1f}s"
    )
    return {
        "status": "done",
        "processed": processed_count,
        "published": published_count,
        "failures": failure_count,
        "duration_seconds": round(duration, 2),
    }
```

- [ ] **Step 4: Run tests**

```
pytest tests/queue/test_publishing_task.py -v
```
Expected: 6 PASSED.

**Debugging note:** The test `test_publishing_task_schedules_analytics_jobs` checks `ctx["redis"].enqueue_job.call_count == 3`. The mock is `ctx["redis"] = AsyncMock()`, so `await ctx["redis"].enqueue_job(...)` will work. The first positional arg is `"analytics_agent_task"`. The test checks `call[0][0]` for each call — this is `call_args[0][0]`, i.e., the first positional arg. All three calls pass `"analytics_agent_task"` as first arg, so this should work.

- [ ] **Step 5: Run full suite**

```
pytest tests/ --ignore=tests/agents/research/test_install.py -q
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/queue/tasks.py tests/queue/test_publishing_task.py
git commit -m "feat: implement publishing_agent_task orchestration loop"
```
