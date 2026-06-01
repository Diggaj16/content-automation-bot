# Scoring Agent Part 2 — DB Writer and Task Wiring

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Scoring Agent by adding the DB write helpers (bulk idea insert, mark-processed, cost log) and wiring the full `scoring_agent_task` arq function that ties embedder, coverage checker, and idea generator together.

**Architecture:** `db_writer.py` contains three synchronous supabase-py helpers. `scoring_agent_task` in `tasks.py` fetches unprocessed `raw_content`, embeds each article, checks recent coverage per platform, generates ideas, writes them to DB, marks the article processed, and records cost/run_log. Voyage AI client is built only when `voyage_api_key` is set; otherwise embedding is skipped and `recent_coverage_flag` defaults to `False`.

**Tech Stack:** `supabase-py`, `voyageai` (optional), `anthropic`, `arq`, existing `app.agents.scoring.*` from Part 1.

---

## File Structure

```
backend/
  app/
    agents/
      scoring/
        db_writer.py        CREATE — write_ideas, mark_article_processed, upsert_cost_log
  app/queue/
    tasks.py                MODIFY — replace scoring_agent_task stub with full impl
tests/
  agents/
    scoring/
      test_db_writer.py     CREATE
  queue/
    test_scoring_task.py    CREATE
```

---

### Task 23: Scoring DB writer

**Files:**
- Create: `backend/app/agents/research/db_writer.py` — note: DO NOT modify this (already done). Create `backend/app/agents/scoring/db_writer.py` (new file, scoring-specific).
- Create: `backend/tests/agents/scoring/test_db_writer.py`

#### Background

Three functions, all synchronous supabase-py:

| Function | Table | Operation |
|---|---|---|
| `write_ideas(supabase, ideas, article_id, publication_date)` | `ideas` | Bulk INSERT; returns list of created UUIDs |
| `mark_article_processed(supabase, article_id)` | `raw_content` | UPDATE `processed=True` WHERE id=article_id |
| `upsert_cost_log(supabase, agent_name, total_usd, token_count)` | `cost_log` | Read-then-write upsert (same pattern as research agent) |

`write_ideas` takes:
- `supabase: Client`
- `ideas: list[IdeaCreate]` — each has `platform`, `angle`, `agent_reasoning`, `score`, `recent_coverage_flag`; caller sets `source_article_id` and `source_article_date` before passing
- Returns `list[str]` — UUIDs of created rows (may be shorter than input if some fail)

Each idea is INSERTed one-by-one (not bulk batch, to isolate per-idea failures). On INSERT failure the idea is skipped (logged) and the loop continues.

`mark_article_processed`:
- `supabase.table("raw_content").update({"processed": True}).eq("id", str(article_id)).execute()`
- Never raises.

`upsert_cost_log`: identical read-then-write pattern to `app.agents.research.db_writer.upsert_cost_log`. Copy the implementation rather than cross-importing.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/agents/scoring/test_db_writer.py`:

```python
"""Unit tests for app.agents.scoring.db_writer."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, call
from uuid import UUID, uuid4

import pytest

from app.agents.scoring.db_writer import (
    write_ideas,
    mark_article_processed,
    upsert_cost_log,
)
from app.db.models import IdeaCreate, Platform


def _make_idea(platform: Platform = Platform.LINKEDIN) -> IdeaCreate:
    return IdeaCreate(
        platform=platform,
        angle="How RBI rate hike affects your home loan EMI",
        agent_reasoning="High engagement topic for retail borrowers.",
        score=8.5,
        recent_coverage_flag=False,
        source_article_id=uuid4(),
        source_article_date=datetime(2025, 5, 15, tzinfo=timezone.utc),
    )


def _make_sb(insert_id: str = "idea-uuid-001") -> MagicMock:
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": insert_id}]
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    return sb


class TestWriteIdeas:
    def test_returns_list_of_ids_on_success(self):
        sb = _make_sb(insert_id="idea-uuid-001")
        ids = write_ideas(sb, [_make_idea()], uuid4(), datetime(2025, 5, 15, tzinfo=timezone.utc))
        assert ids == ["idea-uuid-001"]

    def test_inserts_into_ideas_table(self):
        sb = _make_sb()
        write_ideas(sb, [_make_idea()], uuid4(), None)
        sb.table.assert_any_call("ideas")

    def test_returns_empty_list_for_no_ideas(self):
        sb = _make_sb()
        ids = write_ideas(sb, [], uuid4(), None)
        assert ids == []
        # No insert should be attempted
        sb.table.return_value.insert.assert_not_called()

    def test_skips_failed_ideas_and_continues(self):
        """If one idea INSERT fails, the rest still succeed."""
        sb = MagicMock()
        # First call fails, second succeeds
        sb.table.return_value.insert.return_value.execute.side_effect = [
            Exception("DB error"),
            MagicMock(data=[{"id": "idea-uuid-002"}]),
        ]
        ideas = [_make_idea(Platform.LINKEDIN), _make_idea(Platform.TWITTER)]
        ids = write_ideas(sb, ideas, uuid4(), None)
        assert ids == ["idea-uuid-002"]

    def test_payload_includes_platform_angle_score(self):
        sb = _make_sb()
        idea = _make_idea(Platform.LINKEDIN)
        write_ideas(sb, [idea], uuid4(), None)
        insert_payload = sb.table.return_value.insert.call_args.args[0]
        assert insert_payload["platform"] == "linkedin"
        assert insert_payload["angle"] == idea.angle
        assert insert_payload["score"] == idea.score


class TestMarkArticleProcessed:
    def test_updates_processed_to_true(self):
        sb = _make_sb()
        article_id = UUID("11111111-1111-1111-1111-111111111111")
        mark_article_processed(sb, article_id)
        sb.table.assert_any_call("raw_content")
        update_payload = sb.table.return_value.update.call_args.args[0]
        assert update_payload["processed"] is True

    def test_does_not_raise_on_exception(self):
        sb = MagicMock()
        sb.table.side_effect = Exception("DB error")
        # Should not raise
        mark_article_processed(sb, UUID("11111111-1111-1111-1111-111111111111"))


class TestUpsertCostLog:
    def test_inserts_new_row_when_no_existing(self):
        sb = _make_sb()
        upsert_cost_log(sb, "scoring_agent", total_usd=0.03, token_count=800)
        insert_payload = sb.table.return_value.insert.call_args.args[0]
        assert insert_payload["agent_name"] == "scoring_agent"
        assert insert_payload["estimated_cost_usd"] == 0.03

    def test_increments_existing_row(self):
        sb = _make_sb()
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "existing-id", "token_count": 500, "estimated_cost_usd": 0.02}
        ]
        upsert_cost_log(sb, "scoring_agent", total_usd=0.03, token_count=600)
        update_payload = sb.table.return_value.update.call_args.args[0]
        assert update_payload["token_count"] == 1100
        assert abs(update_payload["estimated_cost_usd"] - 0.05) < 1e-6
```

- [ ] **Step 2: Run failing tests**

```bash
cd D:/Intern/content-automation-bot/backend && .venv/Scripts/pytest.exe tests/agents/scoring/test_db_writer.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `backend/app/agents/scoring/db_writer.py`**

```python
"""
DB write helpers for the scoring agent.

All functions are synchronous (supabase-py). Never raise.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from supabase import Client

from app.db.models import IdeaCreate
from app.utils.logging import get_logger

logger = get_logger(__name__)


def write_ideas(
    supabase: Client,
    ideas: list[IdeaCreate],
    article_id: UUID,
    publication_date: Optional[datetime],
) -> list[str]:
    """
    INSERT each idea into the ideas table one by one.

    Returns a list of created row UUIDs. If an individual idea fails,
    it is skipped and the loop continues — partial success is acceptable.
    """
    if not ideas:
        return []

    created_ids: list[str] = []
    pub_date_iso = publication_date.isoformat() if publication_date else None

    for idea in ideas:
        payload = {
            "platform":            idea.platform.value,
            "angle":               idea.angle,
            "source_article_id":   str(article_id),
            "agent_reasoning":     idea.agent_reasoning,
            "source_article_date": pub_date_iso,
            "score":               idea.score,
            "recent_coverage_flag": idea.recent_coverage_flag,
        }
        try:
            resp = supabase.table("ideas").insert(payload).execute()
            if resp.data:
                created_ids.append(resp.data[0]["id"])
            else:
                logger.warning("write_ideas: insert returned no data", extra={"angle": idea.angle})
        except Exception as exc:
            logger.warning(
                "write_ideas: failed to insert idea",
                extra={"angle": idea.angle, "error": str(exc)},
            )

    return created_ids


def mark_article_processed(supabase: Client, article_id: UUID) -> None:
    """
    Mark a raw_content row as processed=True.
    Never raises.
    """
    try:
        supabase.table("raw_content").update({"processed": True}).eq(
            "id", str(article_id)
        ).execute()
    except Exception as exc:
        logger.warning(
            "mark_article_processed failed",
            extra={"article_id": str(article_id), "error": str(exc)},
        )


def upsert_cost_log(
    supabase: Client,
    agent_name: str,
    total_usd: float,
    token_count: int,
) -> None:
    """
    Increment today's cost_log row for this agent (or create it if not present).
    Read-then-write pattern. Safe for single-process arq workers.
    """
    today = str(datetime.now(timezone.utc).date())
    try:
        existing = (
            supabase.table("cost_log")
            .select("id, token_count, estimated_cost_usd")
            .eq("agent_name", agent_name)
            .eq("date", today)
            .limit(1)
            .execute()
        )
        if existing.data:
            row = existing.data[0]
            supabase.table("cost_log").update({
                "token_count":        row["token_count"] + token_count,
                "estimated_cost_usd": round(row["estimated_cost_usd"] + total_usd, 6),
            }).eq("id", row["id"]).execute()
        else:
            supabase.table("cost_log").insert({
                "agent_name":         agent_name,
                "date":               today,
                "token_count":        token_count,
                "estimated_cost_usd": round(total_usd, 6),
            }).execute()
    except Exception as exc:
        logger.warning("upsert_cost_log failed", extra={"agent": agent_name, "error": str(exc)})
```

- [ ] **Step 4: Run tests — all should pass**

```bash
cd D:/Intern/content-automation-bot/backend && .venv/Scripts/pytest.exe tests/agents/scoring/test_db_writer.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Run full suite**

```bash
cd D:/Intern/content-automation-bot/backend && .venv/Scripts/pytest.exe -m "not integration" -v
```

- [ ] **Step 6: Commit**

```bash
git -C D:/Intern/content-automation-bot add backend/app/agents/scoring/db_writer.py backend/tests/agents/scoring/test_db_writer.py
git -C D:/Intern/content-automation-bot commit -m "feat(scoring): add scoring agent db_writer module with tests (Task 23)"
```

---

### Task 24: Wire `scoring_agent_task`

**Files:**
- Modify: `backend/app/queue/tasks.py` — replace `scoring_agent_task` stub
- Create: `backend/tests/queue/test_scoring_task.py`

#### Background

The arq task receives `ctx` (dict with `supabase` and `settings`). The task:

1. Fetches all `raw_content` rows where `processed=False` (limit 50 per run to avoid timeouts)
2. Builds Anthropic client; builds Voyage AI client only if `settings.voyage_api_key` is set
3. For each article:
   a. Embed article title + story_narrative (if Voyage client available)
   b. Generate ideas via `generate_ideas(article, anthropic_client, settings.claude_model_heavy)`
   c. For each idea: check `check_recent_coverage(embedding, idea.platform.value, supabase)` → set `idea.recent_coverage_flag`
   d. Set `idea.source_article_id = article.id` and `idea.source_article_date = article.publication_date`
   e. Write ideas to DB via `write_ideas(supabase, ideas, article.id, article.publication_date)`
   f. Mark article processed: `mark_article_processed(supabase, article.id)`
4. Accumulate sonnet token counts; compute cost
5. Call `upsert_cost_log(supabase, "scoring_agent", total_usd, total_tokens)`
6. Write `run_logs` row
7. If cost >= threshold and webhook set → `send_slack_alert`
8. Return summary dict

**Fetching unprocessed articles:**
```python
resp = supabase.table("raw_content").select("*").eq("processed", False).limit(50).execute()
articles = [RawContent(**r) for r in resp.data]
```

**IdeaCreate is immutable** (Pydantic model, no `.recent_coverage_flag = ...` assignment).
Build a new IdeaCreate with the flag set:
```python
idea_with_flag = IdeaCreate(
    **{**idea.model_dump(), "recent_coverage_flag": is_covered, "source_article_id": article.id, "source_article_date": article.publication_date}
)
```

**Token cost:** Only sonnet tokens (from `generate_ideas`). Voyage AI cost is negligible and not tracked separately.

**`run_logs` trigger_type:** Always `TriggerType.EVENT` (scoring is triggered by research completing).

- [ ] **Step 1: Write failing tests**

Create `backend/tests/queue/test_scoring_task.py`:

```python
"""Smoke tests for scoring_agent_task."""
import pytest
from unittest.mock import MagicMock, patch


def _make_ctx() -> dict:
    settings = MagicMock()
    settings.anthropic_api_key = "test-key"
    settings.voyage_api_key = None          # skip embedding
    settings.claude_model_heavy = "claude-sonnet-4-5"
    settings.daily_cost_alert_usd = 5.0
    settings.slack_webhook_url = None

    supabase = MagicMock()
    # No unprocessed articles
    supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    supabase.table.return_value.insert.return_value.execute.return_value.data = [{"id": "log-id"}]
    supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    # cost_log read returns empty (no existing row)
    supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

    return {"settings": settings, "supabase": supabase}


@pytest.mark.asyncio
async def test_scoring_task_returns_done_with_no_articles():
    ctx = _make_ctx()
    with patch("app.queue.tasks.Anthropic"):
        from app.queue.tasks import scoring_agent_task
        result = await scoring_agent_task(ctx)
    assert result["status"] == "done"
    assert result["processed"] == 0
    assert result["ideas_created"] == 0
    assert "duration_seconds" in result


@pytest.mark.asyncio
async def test_scoring_task_writes_run_log():
    ctx = _make_ctx()
    with patch("app.queue.tasks.Anthropic"):
        from app.queue.tasks import scoring_agent_task
        await scoring_agent_task(ctx)
    table_calls = [str(c) for c in ctx["supabase"].table.call_args_list]
    assert any("run_logs" in c for c in table_calls)


@pytest.mark.asyncio
async def test_scoring_task_skips_voyage_when_key_is_none():
    """With voyage_api_key=None, embedding should be skipped — no voyageai import error."""
    ctx = _make_ctx()
    ctx["settings"].voyage_api_key = None
    with patch("app.queue.tasks.Anthropic"):
        from app.queue.tasks import scoring_agent_task
        result = await scoring_agent_task(ctx)
    assert result["status"] == "done"
```

- [ ] **Step 2: Run failing tests**

```bash
cd D:/Intern/content-automation-bot/backend && .venv/Scripts/pytest.exe tests/queue/test_scoring_task.py -v
```

Expected: fails because stub returns `{"status": "stub", ...}`

- [ ] **Step 3: Replace `scoring_agent_task` in `tasks.py`**

Read `backend/app/queue/tasks.py` first. Replace only the `scoring_agent_task` function body (keep module-level imports and other tasks untouched):

```python
async def scoring_agent_task(ctx: dict) -> dict:
    """
    Scoring agent — generates content ideas from unprocessed raw_content articles.
    Triggered: by event after research_agent_task completes.
    """
    import time
    from anthropic import Anthropic
    from app.agents.scoring.embedder import embed_text
    from app.agents.scoring.coverage_checker import check_recent_coverage
    from app.agents.scoring.idea_generator import generate_ideas
    from app.agents.scoring.db_writer import write_ideas, mark_article_processed, upsert_cost_log
    from app.utils.slack import send_slack_alert
    from app.utils.logging import format_token_cost, log_agent_decision
    from app.db.models import RawContent, IdeaCreate, RunLogCreate, TriggerType

    settings = ctx["settings"]
    supabase = ctx["supabase"]
    start_time = time.time()

    anthropic_client = Anthropic(api_key=settings.anthropic_api_key)

    # Build Voyage client only if key is configured
    voyage_client = None
    if settings.voyage_api_key:
        import voyageai
        voyage_client = voyageai.Client(api_key=settings.voyage_api_key)

    processed_count = 0
    ideas_created_count = 0
    failure_count = 0
    errors: list[dict] = []
    trace_entries: list[str] = []
    sonnet_in = sonnet_out = 0

    # Fetch unprocessed articles (limit 50 to stay within job timeout)
    try:
        resp = supabase.table("raw_content").select("*").eq("processed", False).limit(50).execute()
        articles = [RawContent(**r) for r in resp.data]
    except Exception as exc:
        logger.error(f"scoring_agent_task: failed to fetch raw_content | err={exc}")
        return {
            "status": "error",
            "processed": 0,
            "ideas_created": 0,
            "failures": 0,
            "duration_seconds": round(time.time() - start_time, 2),
            "cost_usd": 0.0,
            "error": str(exc),
        }

    logger.info(f"scoring_agent_task: {len(articles)} unprocessed articles")

    for article in articles:
        processed_count += 1
        try:
            # Step 1 — Embed article for coverage check
            embedding: list[float] = []
            if voyage_client is not None:
                embed_input = f"{article.title}. {article.structured_summary.story_narrative if article.structured_summary else ''}"
                embedding = embed_text(embed_input, voyage_client)

            # Step 2 — Generate ideas via Claude Sonnet
            idea_result = generate_ideas(article, anthropic_client, settings.claude_model_heavy)
            sonnet_in += idea_result.input_tokens
            sonnet_out += idea_result.output_tokens

            if not idea_result.ideas:
                trace_entries.append(log_agent_decision(
                    logger, "no_ideas", "generate_ideas returned empty list",
                    {"article_id": str(article.id), "title": article.title},
                ))
                mark_article_processed(supabase, article.id)
                continue

            # Step 3 — Check coverage per idea and build final IdeaCreate list
            final_ideas: list[IdeaCreate] = []
            for idea in idea_result.ideas:
                is_covered = check_recent_coverage(embedding, idea.platform.value, supabase)
                final_ideas.append(IdeaCreate(**{
                    **idea.model_dump(),
                    "recent_coverage_flag": is_covered,
                    "source_article_id":    article.id,
                    "source_article_date":  article.publication_date,
                }))

            # Step 4 — Write ideas to DB
            created_ids = write_ideas(supabase, final_ideas, article.id, article.publication_date)
            ideas_created_count += len(created_ids)

            if len(created_ids) < len(final_ideas):
                failure_count += len(final_ideas) - len(created_ids)

            trace_entries.append(log_agent_decision(
                logger, "ideas_written", f"{len(created_ids)} ideas stored",
                {"article_id": str(article.id), "title": article.title, "ideas": len(created_ids)},
            ))

            # Step 5 — Mark article as processed
            mark_article_processed(supabase, article.id)

        except Exception as exc:
            logger.error(f"scoring_agent_task: article error | id={article.id} | err={exc}")
            errors.append({"article_id": str(article.id), "error": str(exc)})
            failure_count += 1

    duration = time.time() - start_time

    # Cost tracking (Sonnet only; Voyage is negligible)
    sonnet_cost = format_token_cost(sonnet_in, sonnet_out, settings.claude_model_heavy)
    total_usd = sonnet_cost["estimated_usd"]
    total_tokens = sonnet_in + sonnet_out
    token_cost_dict = {"sonnet": sonnet_cost, "total_usd": round(total_usd, 6)}

    upsert_cost_log(supabase, "scoring_agent", total_usd=total_usd, token_count=total_tokens)

    run_log = RunLogCreate(
        agent_name="scoring_agent",
        trigger_type=TriggerType.EVENT,
        processed_count=processed_count,
        success_count=ideas_created_count,
        failure_count=failure_count,
        duration_seconds=round(duration, 2),
        reasoning_trace="\n".join(trace_entries) if trace_entries else None,
        errors=errors,
        token_cost=token_cost_dict,
    )
    try:
        supabase.table("run_logs").insert(run_log.model_dump()).execute()
    except Exception as exc:
        logger.error(f"scoring_agent_task: failed to write run_log | err={exc}")

    if settings.slack_webhook_url and total_usd >= settings.daily_cost_alert_usd:
        send_slack_alert(
            settings.slack_webhook_url,
            f"Scoring agent cost alert: ${total_usd:.4f} in this run "
            f"(threshold: ${settings.daily_cost_alert_usd})",
        )

    logger.info(
        f"scoring_agent_task done | processed={processed_count} "
        f"ideas={ideas_created_count} failures={failure_count} "
        f"duration={duration:.1f}s cost=${total_usd:.4f}"
    )
    return {
        "status": "done",
        "processed": processed_count,
        "ideas_created": ideas_created_count,
        "failures": failure_count,
        "duration_seconds": round(duration, 2),
        "cost_usd": round(total_usd, 6),
    }
```

- [ ] **Step 4: Run task tests**

```bash
cd D:/Intern/content-automation-bot/backend && .venv/Scripts/pytest.exe tests/queue/test_scoring_task.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Run full suite**

```bash
cd D:/Intern/content-automation-bot/backend && .venv/Scripts/pytest.exe -m "not integration" -v
```

- [ ] **Step 6: Commit**

```bash
git -C D:/Intern/content-automation-bot add backend/app/agents/scoring/db_writer.py backend/tests/agents/scoring/test_db_writer.py backend/app/queue/tasks.py backend/tests/queue/test_scoring_task.py
git -C D:/Intern/content-automation-bot commit -m "feat(scoring): add db_writer and wire scoring_agent_task (Tasks 23-24)"
```

---

## Self-Review

**Spec coverage:**
- [x] `write_ideas` bulk INSERT ideas (one-by-one with per-idea failure isolation) — Task 23
- [x] `mark_article_processed` UPDATE processed=True — Task 23
- [x] `upsert_cost_log` read-then-write — Task 23
- [x] Fetch unprocessed articles (limit 50) — Task 24
- [x] Voyage client built only when key is set — Task 24
- [x] Embedding used for coverage check per idea — Task 24
- [x] `source_article_id` and `source_article_date` set on ideas — Task 24
- [x] `recent_coverage_flag` set via `check_recent_coverage` — Task 24
- [x] `run_logs` with `TriggerType.EVENT` — Task 24
- [x] Cost log + slack alert — Task 24

**Placeholder scan:** None found.

**Type consistency:**
- `write_ideas(supabase, ideas: list[IdeaCreate], article_id: UUID, publication_date: Optional[datetime]) -> list[str]` — matches test and task code
- `mark_article_processed(supabase, article_id: UUID) -> None` — matches test and task code
- `upsert_cost_log(supabase, agent_name, total_usd, token_count)` — matches test and task code
