# Analytics Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Analytics Agent — records platform engagement metrics at 24h/72h/7d after publish, calculates a performance score, stores in `content_analytics`, and at the 7d mark updates the `style_guide` for the platform.

**Architecture:** Two modules under `app/agents/analytics/`. `metrics_fetcher.py` generates stub metrics per platform (no real API calls). `db_writer.py` handles DB writes. Style guide update at 7d uses a simple DB aggregation — no AI cost. `analytics_agent_task` in `tasks.py` orchestrates the flow.

**Tech Stack:** Supabase (existing), arq (existing). No LLM calls in this agent.

---

### Task 35: Analytics metrics fetcher + DB writer modules

**Files:**
- Create: `backend/app/agents/analytics/__init__.py`
- Create: `backend/app/agents/analytics/metrics_fetcher.py`
- Create: `backend/app/agents/analytics/db_writer.py`
- Create: `backend/tests/agents/analytics/__init__.py`
- Create: `backend/tests/agents/analytics/test_metrics_fetcher.py`
- Create: `backend/tests/agents/analytics/test_db_writer.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/agents/analytics/test_metrics_fetcher.py
"""Tests for analytics metrics_fetcher module."""
from app.agents.analytics.metrics_fetcher import (
    fetch_metrics,
    calculate_performance_score,
)


def test_fetch_metrics_linkedin_returns_required_keys():
    metrics = fetch_metrics("linkedin", "li-stub-abc", "24h")
    assert "impressions" in metrics
    assert "reactions" in metrics
    assert "comments" in metrics
    assert "shares" in metrics


def test_fetch_metrics_twitter_returns_required_keys():
    metrics = fetch_metrics("twitter", "tw-stub-abc", "72h")
    assert "likes" in metrics
    assert "retweets" in metrics
    assert "impressions" in metrics
    assert "bookmarks" in metrics


def test_fetch_metrics_blog_returns_required_keys():
    metrics = fetch_metrics("blog", "blog-stub-abc", "7d")
    assert "page_views" in metrics
    assert "sessions" in metrics
    assert "avg_engagement_time_seconds" in metrics


def test_fetch_metrics_email_returns_required_keys():
    metrics = fetch_metrics("email", "email-stub-abc", "24h")
    assert "open_rate" in metrics
    assert "click_rate" in metrics
    assert "unsubscribes" in metrics


def test_fetch_metrics_unknown_platform_returns_empty_dict():
    metrics = fetch_metrics("unknown", "id-abc", "24h")
    assert metrics == {}


def test_fetch_metrics_never_raises():
    # Should not raise on any input
    metrics = fetch_metrics("linkedin", "", "invalid_period")
    assert isinstance(metrics, dict)


def test_calculate_performance_score_linkedin_range():
    metrics = {"impressions": 1000, "reactions": 50, "comments": 10, "shares": 5}
    score = calculate_performance_score("linkedin", metrics)
    assert 0.0 <= score <= 10.0


def test_calculate_performance_score_zero_impressions():
    metrics = {"impressions": 0, "reactions": 5, "comments": 1, "shares": 0}
    score = calculate_performance_score("linkedin", metrics)
    assert score == 0.0


def test_calculate_performance_score_unknown_platform_returns_zero():
    score = calculate_performance_score("unknown", {})
    assert score == 0.0


def test_calculate_performance_score_twitter():
    metrics = {"impressions": 500, "likes": 25, "retweets": 10, "bookmarks": 5}
    score = calculate_performance_score("twitter", metrics)
    assert 0.0 <= score <= 10.0
```

```python
# backend/tests/agents/analytics/test_db_writer.py
"""Tests for analytics db_writer."""
from unittest.mock import MagicMock
from uuid import UUID

from app.agents.analytics.db_writer import write_analytics, update_style_guide


_POST_ID = "post-uuid-001"


def test_write_analytics_returns_id_on_success():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "analytics-001"}]
    result = write_analytics(sb, _POST_ID, "linkedin", "24h", {"impressions": 100}, 5.5)
    assert result == "analytics-001"


def test_write_analytics_returns_none_on_empty_data():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = []
    result = write_analytics(sb, _POST_ID, "twitter", "72h", {}, 3.0)
    assert result is None


def test_write_analytics_returns_none_on_exception():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.side_effect = RuntimeError("DB error")
    result = write_analytics(sb, _POST_ID, "blog", "7d", {}, 0.0)
    assert result is None


def test_write_analytics_payload_has_required_fields():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "x"}]
    write_analytics(sb, _POST_ID, "linkedin", "24h", {"impressions": 200}, 6.0)
    payload = sb.table.return_value.insert.call_args[0][0]
    assert payload["post_id"] == _POST_ID
    assert payload["platform"] == "linkedin"
    assert payload["measurement_period"] == "24h"
    assert isinstance(payload["metrics"], dict)
    assert payload["performance_score"] == 6.0


def test_update_style_guide_calls_upsert():
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "sg-1", "platform": "linkedin", "insights": {}}
    ]
    update_style_guide(sb, "linkedin", 7.5)
    # Should call update (existing record)
    sb.table.return_value.update.assert_called()


def test_update_style_guide_inserts_when_not_exists():
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    update_style_guide(sb, "twitter", 4.0)
    # Should call insert (new record)
    sb.table.return_value.insert.assert_called()


def test_update_style_guide_never_raises():
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.side_effect = RuntimeError("DB error")
    update_style_guide(sb, "blog", 5.0)  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/agents/analytics/test_metrics_fetcher.py tests/agents/analytics/test_db_writer.py -v
```
Expected: ERROR (ImportError)

- [ ] **Step 3: Create `backend/app/agents/analytics/__init__.py`**

Empty file.

- [ ] **Step 4: Create `backend/tests/agents/analytics/__init__.py`**

Empty file.

- [ ] **Step 5: Create `backend/app/agents/analytics/metrics_fetcher.py`**

```python
"""
Platform metrics fetcher stubs for the analytics agent.

These return simulated engagement data. Replace with real API calls
when platform credentials (LinkedIn API, Twitter API, etc.) are configured.
"""
import random
from app.utils.logging import get_logger

logger = get_logger(__name__)


def fetch_metrics(platform: str, post_identifier: str, measurement_period: str) -> dict:
    """
    Fetch engagement metrics for a published post.

    Currently returns randomised stub data. In production, replace each branch
    with a real API call using the post_identifier.

    Returns an empty dict for unknown platforms or on error. Never raises.
    """
    try:
        if platform == "linkedin":
            return {
                "impressions": random.randint(200, 5000),
                "reactions":   random.randint(5, 300),
                "comments":    random.randint(0, 80),
                "shares":      random.randint(0, 50),
            }
        elif platform == "twitter":
            return {
                "impressions": random.randint(100, 10000),
                "likes":       random.randint(2, 500),
                "retweets":    random.randint(0, 100),
                "bookmarks":   random.randint(0, 80),
            }
        elif platform == "blog":
            return {
                "page_views":                  random.randint(50, 3000),
                "sessions":                    random.randint(30, 2000),
                "avg_engagement_time_seconds": round(random.uniform(30, 300), 1),
            }
        elif platform == "email":
            return {
                "open_rate":    round(random.uniform(0.10, 0.55), 3),
                "click_rate":   round(random.uniform(0.01, 0.15), 3),
                "unsubscribes": random.randint(0, 10),
            }
        else:
            logger.warning(f"fetch_metrics: unknown platform | platform={platform}")
            return {}
    except Exception as exc:
        logger.error(f"fetch_metrics: error | platform={platform} | err={exc}")
        return {}


def calculate_performance_score(platform: str, metrics: dict) -> float:
    """
    Calculate a 0–10 performance score from engagement metrics.

    Each platform uses its primary engagement signals.
    Returns 0.0 for unknown platforms or when impressions are zero.
    Never raises.
    """
    try:
        if platform == "linkedin":
            impressions = metrics.get("impressions", 0)
            if impressions == 0:
                return 0.0
            engagement = (
                metrics.get("reactions", 0)
                + metrics.get("comments", 0) * 2
                + metrics.get("shares", 0) * 3
            )
            rate = engagement / impressions
            return round(min(10.0, rate * 100), 2)

        elif platform == "twitter":
            impressions = metrics.get("impressions", 0)
            if impressions == 0:
                return 0.0
            engagement = (
                metrics.get("likes", 0)
                + metrics.get("retweets", 0) * 2
                + metrics.get("bookmarks", 0)
            )
            rate = engagement / impressions
            return round(min(10.0, rate * 100), 2)

        elif platform == "blog":
            page_views = metrics.get("page_views", 0)
            if page_views == 0:
                return 0.0
            avg_time = metrics.get("avg_engagement_time_seconds", 0)
            # Score: 5 for >60s average time, 10 for >300s
            time_score = min(10.0, avg_time / 30.0)
            return round(time_score, 2)

        elif platform == "email":
            open_rate = metrics.get("open_rate", 0.0)
            click_rate = metrics.get("click_rate", 0.0)
            # Industry average open rate ~20%, click rate ~2.5%
            score = (open_rate / 0.20) * 5 + (click_rate / 0.025) * 5
            return round(min(10.0, score), 2)

        else:
            return 0.0

    except Exception as exc:
        logger.error(f"calculate_performance_score: error | platform={platform} | err={exc}")
        return 0.0
```

- [ ] **Step 6: Create `backend/app/agents/analytics/db_writer.py`**

```python
"""
DB write operations for the analytics agent.
"""
from typing import Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)


def write_analytics(
    supabase,
    post_id: str,
    platform: str,
    measurement_period: str,
    metrics: dict,
    performance_score: float,
) -> Optional[str]:
    """
    Insert a content_analytics row.
    Returns the new record UUID string on success, or None on failure. Never raises.
    """
    try:
        payload = {
            "post_id":            post_id,
            "platform":           platform,
            "measurement_period": measurement_period,
            "metrics":            metrics,
            "performance_score":  performance_score,
        }
        resp = supabase.table("content_analytics").insert(payload).execute()
        if not resp.data:
            logger.warning("write_analytics: insert returned no data")
            return None
        return resp.data[0]["id"]
    except Exception as exc:
        logger.error(f"write_analytics: failed | post_id={post_id} | period={measurement_period} | err={exc}")
        return None


def update_style_guide(supabase, platform: str, performance_score: float) -> None:
    """
    Update the style_guide for the platform based on the latest 7d performance.

    Uses read-then-write: fetches the existing row, updates top_performing data.
    Creates a new record if none exists. Never raises.
    """
    try:
        existing = (
            supabase.table("style_guide")
            .select("*")
            .eq("platform", platform)
            .execute()
        )

        if existing.data:
            row = existing.data[0]
            current_insights = row.get("insights") or {}
            # Increment insights with this performance data point
            scores = current_insights.get("recent_scores", [])
            scores.append(round(performance_score, 2))
            # Keep last 30 scores
            scores = scores[-30:]
            avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
            updated_insights = {
                **current_insights,
                "recent_scores":    scores,
                "avg_score_30d":    avg_score,
                "last_updated_by":  "analytics_agent",
            }
            supabase.table("style_guide").update(
                {"insights": updated_insights}
            ).eq("platform", platform).execute()
        else:
            initial_insights = {
                "recent_scores":   [round(performance_score, 2)],
                "avg_score_30d":   round(performance_score, 2),
                "last_updated_by": "analytics_agent",
            }
            supabase.table("style_guide").insert(
                {"platform": platform, "insights": initial_insights}
            ).execute()

    except Exception as exc:
        logger.error(f"update_style_guide: failed | platform={platform} | err={exc}")
```

- [ ] **Step 7: Run tests**

```
pytest tests/agents/analytics/test_metrics_fetcher.py tests/agents/analytics/test_db_writer.py -v
```
Expected: all PASSED

- [ ] **Step 8: Run full suite**

```
pytest tests/ --ignore=tests/agents/research/test_install.py -q
```

- [ ] **Step 9: Commit**

```bash
git add app/agents/analytics/__init__.py app/agents/analytics/metrics_fetcher.py app/agents/analytics/db_writer.py tests/agents/analytics/__init__.py tests/agents/analytics/test_metrics_fetcher.py tests/agents/analytics/test_db_writer.py
git commit -m "feat: add analytics agent metrics_fetcher and db_writer modules"
```

---

### Task 36: Wire analytics_agent_task orchestration loop

**Files:**
- Modify: `backend/app/queue/tasks.py` — replace stub with real implementation
- Create: `backend/tests/queue/test_analytics_task.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/queue/test_analytics_task.py
"""Tests for analytics_agent_task orchestration loop."""
import pytest
from unittest.mock import MagicMock, patch

from app.queue.tasks import analytics_agent_task


def _make_ctx():
    settings = MagicMock()
    supabase = MagicMock()
    return {"settings": settings, "supabase": supabase}


def _make_post_data(post_id="post-uuid-001", platform="linkedin"):
    return {
        "id": post_id,
        "platform": platform,
        "post_identifier": f"{platform}-stub-abc123",
        "published_at": "2026-05-28T10:00:00+00:00",
        "draft_id": None,
        "created_at": "2026-05-28T10:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_analytics_task_stores_24h_metrics():
    ctx = _make_ctx()
    post_id = "post-uuid-001"
    ctx["supabase"].table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        _make_post_data(post_id)
    ]

    with (
        patch("app.agents.analytics.metrics_fetcher.fetch_metrics", return_value={"impressions": 500, "reactions": 25, "comments": 5, "shares": 2}),
        patch("app.agents.analytics.metrics_fetcher.calculate_performance_score", return_value=6.5),
        patch("app.agents.analytics.db_writer.write_analytics", return_value="analytics-001"),
        patch("app.agents.analytics.db_writer.update_style_guide"),
    ):
        result = await analytics_agent_task(ctx, post_id=post_id, measurement_period="24h")

    assert result["status"] == "done"
    assert result["measurement_period"] == "24h"


@pytest.mark.asyncio
async def test_analytics_task_updates_style_guide_at_7d():
    ctx = _make_ctx()
    post_id = "post-uuid-002"
    ctx["supabase"].table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        _make_post_data(post_id)
    ]

    with (
        patch("app.agents.analytics.metrics_fetcher.fetch_metrics", return_value={}),
        patch("app.agents.analytics.metrics_fetcher.calculate_performance_score", return_value=7.0),
        patch("app.agents.analytics.db_writer.write_analytics", return_value="analytics-002"),
        patch("app.agents.analytics.db_writer.update_style_guide") as mock_update,
    ):
        result = await analytics_agent_task(ctx, post_id=post_id, measurement_period="7d")

    assert result["status"] == "done"
    mock_update.assert_called_once()


@pytest.mark.asyncio
async def test_analytics_task_does_not_update_style_guide_at_24h():
    ctx = _make_ctx()
    post_id = "post-uuid-003"
    ctx["supabase"].table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        _make_post_data(post_id)
    ]

    with (
        patch("app.agents.analytics.metrics_fetcher.fetch_metrics", return_value={}),
        patch("app.agents.analytics.metrics_fetcher.calculate_performance_score", return_value=5.0),
        patch("app.agents.analytics.db_writer.write_analytics", return_value="analytics-003"),
        patch("app.agents.analytics.db_writer.update_style_guide") as mock_update,
    ):
        await analytics_agent_task(ctx, post_id=post_id, measurement_period="24h")

    mock_update.assert_not_called()


@pytest.mark.asyncio
async def test_analytics_task_returns_error_when_post_not_found():
    ctx = _make_ctx()
    ctx["supabase"].table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    result = await analytics_agent_task(ctx, post_id="nonexistent", measurement_period="24h")

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_analytics_task_handles_fetch_failure():
    ctx = _make_ctx()
    ctx["supabase"].table.return_value.select.return_value.eq.return_value.execute.side_effect = RuntimeError("db down")

    result = await analytics_agent_task(ctx, post_id="post-uuid-005", measurement_period="72h")

    assert result["status"] == "error"
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/queue/test_analytics_task.py -v
```
Expected: tests fail (stub returns `{"status": "stub"}`)

- [ ] **Step 3: Replace `analytics_agent_task` stub in `app/queue/tasks.py`**

Read `app/queue/tasks.py` first. Replace the entire body of `analytics_agent_task` with:

```python
async def analytics_agent_task(
    ctx: dict,
    post_id: str,
    measurement_period: str,
) -> dict:
    """
    Analytics agent — pulls metrics for one post at one time window.
    Triggered: by publishing agent at 24h, 72h, and 7d after publish.
    Args:
        post_id:            UUID of the published_post record.
        measurement_period: "24h", "72h", or "7d"
    """
    import time
    from app.agents.analytics.metrics_fetcher import fetch_metrics, calculate_performance_score
    from app.agents.analytics.db_writer import write_analytics, update_style_guide
    from app.utils.logging import log_agent_decision
    from app.db.models import PublishedPost, RunLogCreate, TriggerType

    settings = ctx["settings"]
    supabase = ctx["supabase"]
    start_time = time.time()

    # Fetch the published post record
    try:
        resp = (
            supabase.table("published_posts")
            .select("*")
            .eq("id", post_id)
            .execute()
        )
        if not resp.data:
            logger.warning(f"analytics_agent_task: post not found | id={post_id}")
            return {
                "status": "error",
                "post_id": post_id,
                "measurement_period": measurement_period,
                "duration_seconds": round(time.time() - start_time, 2),
                "error": "Post not found",
            }
        post = PublishedPost(**resp.data[0])
    except Exception as exc:
        logger.error(f"analytics_agent_task: failed to fetch post | id={post_id} | err={exc}")
        return {
            "status": "error",
            "post_id": post_id,
            "measurement_period": measurement_period,
            "duration_seconds": round(time.time() - start_time, 2),
            "error": str(exc),
        }

    # Fetch metrics (stub)
    metrics = fetch_metrics(post.platform, post.post_identifier, measurement_period)

    # Calculate performance score
    performance_score = calculate_performance_score(post.platform, metrics)

    # Store analytics
    analytics_id = write_analytics(
        supabase, post_id, post.platform, measurement_period, metrics, performance_score
    )

    # Update style guide only at 7d mark
    if measurement_period == "7d":
        update_style_guide(supabase, post.platform, performance_score)

    duration = time.time() - start_time

    run_log = RunLogCreate(
        agent_name="analytics_agent",
        trigger_type=TriggerType.EVENT,
        processed_count=1,
        success_count=1 if analytics_id else 0,
        failure_count=0 if analytics_id else 1,
        duration_seconds=round(duration, 2),
        reasoning_trace=log_agent_decision(
            logger, "analytics_stored",
            f"Metrics recorded for {post.platform} at {measurement_period}",
            {"post_id": post_id, "period": measurement_period, "score": performance_score},
        ) if analytics_id else None,
        errors=[],
        token_cost={"total_usd": 0.0},
    )
    try:
        supabase.table("run_logs").insert(run_log.model_dump()).execute()
    except Exception as exc:
        logger.error(f"analytics_agent_task: failed to write run_log | err={exc}")

    logger.info(
        f"analytics_agent_task done | post_id={post_id} "
        f"period={measurement_period} platform={post.platform} "
        f"score={performance_score} duration={duration:.1f}s"
    )
    return {
        "status": "done",
        "post_id": post_id,
        "measurement_period": measurement_period,
        "platform": post.platform,
        "performance_score": performance_score,
        "analytics_id": analytics_id,
        "duration_seconds": round(duration, 2),
    }
```

- [ ] **Step 4: Run tests**

```
pytest tests/queue/test_analytics_task.py -v
```
Expected: 5 PASSED.

- [ ] **Step 5: Run full suite**

```
pytest tests/ --ignore=tests/agents/research/test_install.py -q
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/queue/tasks.py tests/queue/test_analytics_task.py
git commit -m "feat: implement analytics_agent_task orchestration loop"
```
