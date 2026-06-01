# Content Creation Agent Implementation Plan — Part 2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `creation_agent_task` stub in `tasks.py` with the real orchestration loop that processes approved idea IDs end-to-end.

**Architecture:** For each idea_id: fetch Idea from DB → fetch source article summary → embed idea text (Voyage AI, optional) → get brand context → generate content (Claude Sonnet) → detect finance flags → write draft → track costs + run_log.

**Tech Stack:** All modules from Part 1 plus arq task framework (existing).

**Pre-requisite:** All four creation agent modules from Part 1 are implemented: `brand_context.py`, `content_generator.py`, `finance_flags.py`, `db_writer.py`.

---

### Task 32: Wire creation_agent_task orchestration loop

**Files:**
- Modify: `backend/app/queue/tasks.py` — replace stub with real implementation
- Create: `backend/tests/queue/test_creation_task.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/queue/test_creation_task.py
"""Tests for creation_agent_task orchestration loop."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from app.queue.tasks import creation_agent_task


def _make_ctx(voyage_key=None):
    settings = MagicMock()
    settings.anthropic_api_key = "sk-test"
    settings.voyage_api_key = voyage_key
    settings.claude_model_heavy = "claude-sonnet-4-5"
    settings.daily_cost_alert_usd = 10.0
    settings.slack_webhook_url = None
    supabase = MagicMock()
    return {"settings": settings, "supabase": supabase}


def _make_idea_data(idea_id="11111111-1111-1111-1111-111111111111", platform="linkedin"):
    return {
        "id": idea_id,
        "platform": platform,
        "angle": "SEBI new circular impacts AMCs",
        "edited_angle": None,
        "source_article_id": None,
        "agent_reasoning": "Relevant to Indian investors",
        "source_article_date": None,
        "approval_status": "approved",
        "score": 8.0,
        "recent_coverage_flag": False,
        "created_at": "2026-05-29T00:00:00+00:00",
        "updated_at": "2026-05-29T00:00:00+00:00",
    }


# ─── happy path ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_creation_task_processes_one_idea():
    ctx = _make_ctx()
    idea_id = "11111111-1111-1111-1111-111111111111"

    # Supabase mocks
    ctx["supabase"].table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        _make_idea_data(idea_id)
    ]

    with (
        patch("app.queue.tasks.Anthropic"),
        patch("app.agents.creation.content_generator.generate_content") as mock_gen,
        patch("app.agents.creation.finance_flags.detect_finance_flags", return_value=[]),
        patch("app.agents.creation.db_writer.write_draft", return_value="draft-uuid-001"),
        patch("app.agents.creation.db_writer.upsert_cost_log"),
        patch("app.agents.creation.brand_context.get_brand_context", return_value=""),
    ):
        from app.db.models import DraftCreate, Platform
        mock_gen.return_value = MagicMock(
            draft_create=DraftCreate(
                platform=Platform.LINKEDIN,
                content_text="Generated content.",
                agent_reasoning="Good angle.",
            ),
            input_tokens=100,
            output_tokens=200,
        )
        result = await creation_agent_task(ctx, idea_ids=[idea_id])

    assert result["status"] == "done"
    assert result["processed"] == 1
    assert result["drafts_created"] == 1
    assert result["failures"] == 0


@pytest.mark.asyncio
async def test_creation_task_counts_failure_when_draft_write_fails():
    ctx = _make_ctx()
    idea_id = "22222222-2222-2222-2222-222222222222"

    ctx["supabase"].table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        _make_idea_data(idea_id)
    ]

    with (
        patch("app.queue.tasks.Anthropic"),
        patch("app.agents.creation.content_generator.generate_content") as mock_gen,
        patch("app.agents.creation.finance_flags.detect_finance_flags", return_value=[]),
        patch("app.agents.creation.db_writer.write_draft", return_value=None),  # write fails
        patch("app.agents.creation.db_writer.upsert_cost_log"),
        patch("app.agents.creation.brand_context.get_brand_context", return_value=""),
    ):
        from app.db.models import DraftCreate, Platform
        mock_gen.return_value = MagicMock(
            draft_create=DraftCreate(
                platform=Platform.LINKEDIN,
                content_text="Content here.",
                agent_reasoning="Good.",
            ),
            input_tokens=50,
            output_tokens=100,
        )
        result = await creation_agent_task(ctx, idea_ids=[idea_id])

    assert result["status"] == "done"
    assert result["drafts_created"] == 0
    assert result["failures"] == 1


@pytest.mark.asyncio
async def test_creation_task_skips_idea_not_found():
    ctx = _make_ctx()
    ctx["supabase"].table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    with patch("app.queue.tasks.Anthropic"):
        result = await creation_agent_task(ctx, idea_ids=["nonexistent-id"])

    assert result["status"] == "done"
    assert result["processed"] == 1
    assert result["drafts_created"] == 0
    assert result["failures"] == 1


@pytest.mark.asyncio
async def test_creation_task_skips_when_generate_returns_none():
    ctx = _make_ctx()
    idea_id = "33333333-3333-3333-3333-333333333333"
    ctx["supabase"].table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        _make_idea_data(idea_id)
    ]

    with (
        patch("app.queue.tasks.Anthropic"),
        patch("app.agents.creation.content_generator.generate_content") as mock_gen,
        patch("app.agents.creation.db_writer.upsert_cost_log"),
        patch("app.agents.creation.brand_context.get_brand_context", return_value=""),
    ):
        mock_gen.return_value = MagicMock(draft_create=None, input_tokens=20, output_tokens=5)
        result = await creation_agent_task(ctx, idea_ids=[idea_id])

    assert result["status"] == "done"
    assert result["drafts_created"] == 0
    assert result["failures"] == 1


@pytest.mark.asyncio
async def test_creation_task_returns_error_on_fatal_exception():
    ctx = _make_ctx()
    # Make the entire idea fetch raise (per-idea exception handler)
    ctx["supabase"].table.return_value.select.return_value.eq.return_value.execute.side_effect = RuntimeError("db down")

    with patch("app.queue.tasks.Anthropic"):
        result = await creation_agent_task(ctx, idea_ids=["some-id"])

    assert result["status"] == "done"
    assert result["failures"] == 1


@pytest.mark.asyncio
async def test_creation_task_empty_idea_ids_returns_done():
    ctx = _make_ctx()
    with patch("app.queue.tasks.Anthropic"):
        result = await creation_agent_task(ctx, idea_ids=[])

    assert result["status"] == "done"
    assert result["processed"] == 0
    assert result["drafts_created"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/queue/test_creation_task.py -v
```
Expected: tests import but creation_agent_task returns stub dict `{"status": "stub", ...}`

- [ ] **Step 3: Replace `creation_agent_task` stub in `backend/app/queue/tasks.py`**

Read `app/queue/tasks.py` first. Replace the entire `creation_agent_task` function body (keeping the signature) with the following implementation:

```python
async def creation_agent_task(
    ctx: dict,
    idea_ids: list[str],
) -> dict:
    """
    Content creation agent — generates platform drafts for approved ideas.
    Triggered: by orchestrator after weekly plan is approved.
    Args:
        idea_ids: List of approved idea UUIDs to generate content for.
    """
    import time
    from anthropic import Anthropic
    from app.agents.creation.brand_context import get_brand_context
    from app.agents.creation.content_generator import generate_content
    from app.agents.creation.finance_flags import detect_finance_flags
    from app.agents.creation.db_writer import write_draft, upsert_cost_log
    from app.utils.slack import send_slack_alert
    from app.utils.logging import format_token_cost, log_agent_decision
    from app.db.models import Idea, DraftCreate, RunLogCreate, TriggerType

    settings = ctx["settings"]
    supabase = ctx["supabase"]
    start_time = time.time()

    anthropic_client = Anthropic(api_key=settings.anthropic_api_key)

    voyage_client = None
    if settings.voyage_api_key:
        import voyageai
        voyage_client = voyageai.Client(api_key=settings.voyage_api_key)

    processed_count = 0
    draft_count = 0
    failure_count = 0
    errors: list[dict] = []
    trace_entries: list[str] = []
    sonnet_in = sonnet_out = 0

    for idea_id in idea_ids:
        processed_count += 1
        try:
            # Step 1 — Fetch idea
            idea_resp = (
                supabase.table("ideas")
                .select("*")
                .eq("id", idea_id)
                .execute()
            )
            if not idea_resp.data:
                logger.warning(f"creation_agent_task: idea not found | id={idea_id}")
                failure_count += 1
                continue
            idea = Idea(**idea_resp.data[0])

            # Step 2 — Fetch source article context (optional)
            article_context = ""
            if idea.source_article_id:
                art_resp = (
                    supabase.table("raw_content")
                    .select("structured_summary")
                    .eq("id", str(idea.source_article_id))
                    .execute()
                )
                if art_resp.data and art_resp.data[0].get("structured_summary"):
                    s = art_resp.data[0]["structured_summary"]
                    article_context = (
                        f"Story: {s.get('story_narrative', '')}\n"
                        f"Key data: {', '.join(s.get('key_data_points', []))}\n"
                        f"Mechanism: {s.get('mechanism', '')}\n"
                        f"Implications: {s.get('implications', '')}"
                    )

            # Step 3 — Embed idea text and get brand context
            brand_ctx = ""
            if voyage_client:
                from app.agents.scoring.embedder import embed_text
                embed_input = f"{idea.platform.value}: {idea.edited_angle or idea.angle}"
                embedding = embed_text(embed_input, voyage_client)
                brand_ctx = get_brand_context(embedding, idea.platform.value, supabase)

            # Step 4 — Generate content with Claude Sonnet
            gen_result = generate_content(
                idea, article_context, brand_ctx, anthropic_client, settings.claude_model_heavy
            )
            sonnet_in += gen_result.input_tokens
            sonnet_out += gen_result.output_tokens

            if gen_result.draft_create is None:
                trace_entries.append(log_agent_decision(
                    logger, "no_draft", "generate_content returned None",
                    {"idea_id": idea_id, "platform": idea.platform.value},
                ))
                failure_count += 1
                continue

            # Step 5 — Detect finance flags
            flags = detect_finance_flags(gen_result.draft_create.content_text)
            draft_with_flags = DraftCreate(**{
                **gen_result.draft_create.model_dump(),
                "finance_flags": flags,
            })

            # Step 6 — Write draft to DB
            draft_id = write_draft(supabase, draft_with_flags)
            if draft_id:
                draft_count += 1
                trace_entries.append(log_agent_decision(
                    logger, "draft_written", "Draft stored",
                    {"draft_id": draft_id, "idea_id": idea_id, "platform": idea.platform.value},
                ))
            else:
                failure_count += 1
                trace_entries.append(log_agent_decision(
                    logger, "draft_write_failed", "write_draft returned None",
                    {"idea_id": idea_id},
                ))

        except Exception as exc:
            logger.error(f"creation_agent_task: idea error | id={idea_id} | err={exc}")
            errors.append({"idea_id": idea_id, "error": str(exc)})
            failure_count += 1

    duration = time.time() - start_time

    sonnet_cost = format_token_cost(sonnet_in, sonnet_out, settings.claude_model_heavy)
    total_usd = sonnet_cost["estimated_usd"]
    total_tokens = sonnet_in + sonnet_out
    token_cost_dict = {"sonnet": sonnet_cost, "total_usd": round(total_usd, 6)}

    upsert_cost_log(supabase, "creation_agent", total_usd=total_usd, token_count=total_tokens)

    run_log = RunLogCreate(
        agent_name="creation_agent",
        trigger_type=TriggerType.ORCHESTRATOR,
        processed_count=processed_count,
        success_count=draft_count,
        failure_count=failure_count,
        duration_seconds=round(duration, 2),
        reasoning_trace="\n".join(trace_entries) if trace_entries else None,
        errors=errors,
        token_cost=token_cost_dict,
    )
    try:
        supabase.table("run_logs").insert(run_log.model_dump()).execute()
    except Exception as exc:
        logger.error(f"creation_agent_task: failed to write run_log | err={exc}")

    if settings.slack_webhook_url and total_usd >= settings.daily_cost_alert_usd:
        send_slack_alert(
            settings.slack_webhook_url,
            f"Creation agent cost alert: ${total_usd:.4f} in this run "
            f"(threshold: ${settings.daily_cost_alert_usd})",
        )

    logger.info(
        f"creation_agent_task done | processed={processed_count} "
        f"drafts={draft_count} failures={failure_count} "
        f"duration={duration:.1f}s cost=${total_usd:.4f}"
    )
    return {
        "status": "done",
        "processed": processed_count,
        "drafts_created": draft_count,
        "failures": failure_count,
        "duration_seconds": round(duration, 2),
        "cost_usd": round(total_usd, 6),
    }
```

- [ ] **Step 4: Run tests**

```
pytest tests/queue/test_creation_task.py -v
```
Expected: 6 PASSED.

If tests fail, check mock setup — the `ctx["supabase"].table().select().eq().execute().data` chain returns idea data for the first call and `[]` (no article) for subsequent calls. The second `supabase.table(...)` call (for `raw_content`) uses the same mock chain. If the test `test_creation_task_processes_one_idea` fails because the raw_content fetch also returns the idea data (same mock chain), you can make `source_article_id=None` in the idea data (it already is in `_make_idea_data`). This avoids the second DB call entirely.

- [ ] **Step 5: Run full suite**

```
pytest tests/ --ignore=tests/agents/research/test_install.py -q
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/queue/tasks.py tests/queue/test_creation_task.py
git commit -m "feat: implement creation_agent_task orchestration loop"
```
