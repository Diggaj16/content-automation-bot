# Decision Summaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After every 5 rejections at Gate 1, call Claude Haiku to summarise the rejection patterns and write the result to `user_decision_summaries` so the scoring agent can learn from them.

**Architecture:** A new pure-Python module `decision_summary.py` in the scoring agent package handles the DB queries and Claude call. The existing `ideas.py` FastAPI router calls it after each rejection without blocking the HTTP response (failures are silently logged).

**Tech Stack:** Python 3.11, anthropic SDK (already installed), supabase-py (already installed), pytest + pytest-mock.

---

## File Map

| Action | Path |
|--------|------|
| Create | `backend/app/agents/scoring/decision_summary.py` |
| Modify | `backend/app/api/routers/ideas.py` |
| Modify | `backend/app/config.py` |
| Create | `backend/tests/test_decision_summary.py` |

---

### Task 1 — `decision_summary.py` module

**Files:**
- Create: `backend/app/agents/scoring/decision_summary.py`
- Create: `backend/tests/test_decision_summary.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_decision_summary.py
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

import pytest


# ── count_unsummarized_rejections ────────────────────────────────

def test_count_no_previous_summary():
    """When no summary exists, counts ALL rejected ideas."""
    sb = MagicMock()
    # Last summary query returns empty
    sb.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = []
    # Rejection count query
    count_resp = MagicMock()
    count_resp.count = 7
    (
        sb.table.return_value.select.return_value
        .eq.return_value
        .execute.return_value
    ) = count_resp

    from app.agents.scoring.decision_summary import count_unsummarized_rejections
    count, since_ts = count_unsummarized_rejections(sb)
    assert count == 7
    assert since_ts is None


def test_count_with_previous_summary():
    """With an existing summary, only counts rejections after its created_at."""
    sb = MagicMock()
    ts = "2026-05-30T10:00:00+00:00"
    sb.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"created_at": ts}
    ]
    count_resp = MagicMock()
    count_resp.count = 3
    (
        sb.table.return_value.select.return_value
        .eq.return_value
        .gt.return_value
        .execute.return_value
    ) = count_resp

    from app.agents.scoring.decision_summary import count_unsummarized_rejections
    count, since_ts = count_unsummarized_rejections(sb)
    assert count == 3
    assert since_ts is not None


def test_count_returns_zero_on_exception():
    """Never raises — returns (0, None) on DB error."""
    sb = MagicMock()
    sb.table.side_effect = Exception("DB down")
    from app.agents.scoring.decision_summary import count_unsummarized_rejections
    count, since_ts = count_unsummarized_rejections(sb)
    assert count == 0
    assert since_ts is None


# ── fetch_recent_rejections ──────────────────────────────────────

def test_fetch_recent_rejections_returns_list():
    sb = MagicMock()
    ideas = [
        {"angle": "Why SEBI rules hurt retail", "platform": "linkedin", "agent_reasoning": "reason A"},
        {"angle": "Loan EMI tips", "platform": "twitter", "agent_reasoning": "reason B"},
    ]
    (
        sb.table.return_value.select.return_value
        .eq.return_value
        .order.return_value
        .limit.return_value
        .execute.return_value.data
    ) = ideas

    from app.agents.scoring.decision_summary import fetch_recent_rejections
    result = fetch_recent_rejections(sb, None, 10)
    assert len(result) == 2
    assert result[0]["angle"] == "Why SEBI rules hurt retail"


def test_fetch_recent_rejections_empty_on_exception():
    sb = MagicMock()
    sb.table.side_effect = Exception("timeout")
    from app.agents.scoring.decision_summary import fetch_recent_rejections
    result = fetch_recent_rejections(sb, None, 10)
    assert result == []


# ── generate_decision_summary ────────────────────────────────────

def test_generate_summary_calls_claude():
    """Calls Claude Haiku and returns the text content."""
    from unittest.mock import MagicMock, patch
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text="Too many generic EMI explainers rejected. Twitter ideas without hooks rejected.")]
    client.messages.create.return_value = msg

    from app.agents.scoring.decision_summary import generate_decision_summary
    rejected = [
        {"angle": "Generic EMI post", "platform": "linkedin"},
        {"angle": "No hook twitter", "platform": "twitter"},
    ]
    result = generate_decision_summary(rejected, client, "claude-haiku-4-5")
    assert "rejected" in result.lower()
    client.messages.create.assert_called_once()


def test_generate_summary_empty_input():
    """Returns empty string for empty input without calling Claude."""
    client = MagicMock()
    from app.agents.scoring.decision_summary import generate_decision_summary
    result = generate_decision_summary([], client, "claude-haiku-4-5")
    assert result == ""
    client.messages.create.assert_not_called()


def test_generate_summary_returns_empty_on_exception():
    client = MagicMock()
    client.messages.create.side_effect = Exception("API error")
    from app.agents.scoring.decision_summary import generate_decision_summary
    rejected = [{"angle": "something", "platform": "linkedin"}]
    result = generate_decision_summary(rejected, client, "claude-haiku-4-5")
    assert result == ""


# ── write_summary ────────────────────────────────────────────────

def test_write_summary_inserts_row():
    sb = MagicMock()
    from app.agents.scoring.decision_summary import write_summary
    write_summary(sb, "Pattern found.", 5)
    sb.table.assert_called_with("user_decision_summaries")
    call_args = sb.table.return_value.insert.call_args[0][0]
    assert call_args["summary_text"] == "Pattern found."
    assert call_args["rejection_count"] == 5


def test_write_summary_skips_empty_text():
    sb = MagicMock()
    from app.agents.scoring.decision_summary import write_summary
    write_summary(sb, "", 3)
    sb.table.return_value.insert.assert_not_called()


def test_write_summary_never_raises():
    sb = MagicMock()
    sb.table.side_effect = Exception("DB error")
    from app.agents.scoring.decision_summary import write_summary
    write_summary(sb, "Some text.", 5)  # Must not raise
```

- [ ] **Step 2: Run tests — expect ImportError (module not yet created)**

```powershell
cd D:\Intern\content-automation-bot\backend
pytest tests/test_decision_summary.py -v 2>&1 | Select-Object -First 20
```

Expected: `ModuleNotFoundError: No module named 'app.agents.scoring.decision_summary'`

- [ ] **Step 3: Write `decision_summary.py`**

```python
# backend/app/agents/scoring/decision_summary.py
"""
Generates rejection pattern summaries from Gate 1 idea rejections.
Called by the ideas router after each rejection when the unsummarized count
reaches REJECTION_BATCH_SIZE.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from anthropic import Anthropic
from supabase import Client

from app.utils.logging import get_logger

logger = get_logger(__name__)


def count_unsummarized_rejections(supabase: Client) -> tuple[int, Optional[datetime]]:
    """
    Return (count, since_ts) where count is rejections after the last summary
    and since_ts is that summary's timestamp (None if no summary exists yet).
    """
    try:
        last = (
            supabase.table("user_decision_summaries")
            .select("created_at")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        since_ts: Optional[datetime] = None
        if last.data:
            since_ts = datetime.fromisoformat(last.data[0]["created_at"])

        query = (
            supabase.table("ideas")
            .select("id", count="exact")
            .eq("approval_status", "rejected")
        )
        if since_ts:
            query = query.gt("updated_at", since_ts.isoformat())

        resp = query.execute()
        return (resp.count or 0), since_ts
    except Exception as exc:
        logger.warning(f"count_unsummarized_rejections failed | err={exc}")
        return 0, None


def fetch_recent_rejections(
    supabase: Client,
    since_ts: Optional[datetime],
    limit: int,
) -> list[dict]:
    """Fetch recently rejected ideas returning angle, platform, agent_reasoning."""
    try:
        query = (
            supabase.table("ideas")
            .select("angle, platform, agent_reasoning")
            .eq("approval_status", "rejected")
            .order("updated_at", desc=True)
            .limit(limit)
        )
        if since_ts:
            query = query.gt("updated_at", since_ts.isoformat())
        resp = query.execute()
        return resp.data or []
    except Exception as exc:
        logger.warning(f"fetch_recent_rejections failed | err={exc}")
        return []


def generate_decision_summary(
    rejected_ideas: list[dict],
    client: Anthropic,
    model: str,
) -> str:
    """
    Call Claude Haiku to write a 2-3 sentence rejection pattern summary.
    Returns empty string on failure or empty input — never raises.
    """
    if not rejected_ideas:
        return ""

    ideas_text = "\n".join(
        f"- [{r.get('platform', '?')}] {r.get('angle', '')}"
        for r in rejected_ideas
    )

    try:
        message = client.messages.create(
            model=model,
            max_tokens=256,
            system=(
                "You analyse rejected content ideas for an Indian finance newsletter. "
                "Identify common patterns in what gets rejected and write a short summary "
                "to help an AI agent understand what kind of ideas to avoid. "
                "Be specific: mention angle types, platforms, and topic patterns. "
                "Write 2-3 sentences only."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"These {len(rejected_ideas)} ideas were recently rejected:\n\n"
                    f"{ideas_text}\n\n"
                    "Summarise the rejection patterns in 2-3 sentences."
                ),
            }],
        )
        return message.content[0].text.strip() if message.content else ""
    except Exception as exc:
        logger.warning(f"generate_decision_summary: Claude call failed | err={exc}")
        return ""


def write_summary(supabase: Client, summary_text: str, rejection_count: int) -> None:
    """Insert a row into user_decision_summaries. Never raises."""
    if not summary_text:
        return
    try:
        supabase.table("user_decision_summaries").insert({
            "summary_text": summary_text,
            "rejection_count": rejection_count,
        }).execute()
    except Exception as exc:
        logger.warning(f"write_summary failed | err={exc}")
```

- [ ] **Step 4: Run tests — expect all pass**

```powershell
cd D:\Intern\content-automation-bot\backend
pytest tests/test_decision_summary.py -v
```

Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/scoring/decision_summary.py backend/tests/test_decision_summary.py
git commit -m "feat: add decision_summary module for rejection pattern analysis"
```

---

### Task 2 — Config + ideas router hook

**Files:**
- Modify: `backend/app/config.py` — add `rejection_batch_size`
- Modify: `backend/app/api/routers/ideas.py` — call summary generator on rejection

- [ ] **Step 1: Add config field**

In `backend/app/config.py`, inside the `Settings` class, add after the `max_ideas_per_site` field:

```python
# Decision summaries
rejection_batch_size: int = Field(5, gt=0, alias="REJECTION_BATCH_SIZE")
```

- [ ] **Step 2: Verify config loads**

```powershell
cd D:\Intern\content-automation-bot\backend
python -c "from app.config import get_settings; s = get_settings(); print(f'rejection_batch_size = {s.rejection_batch_size}')"
```

Expected: `rejection_batch_size = 5`

- [ ] **Step 3: Update `ideas.py` — add imports and helper**

Open `backend/app/api/routers/ideas.py`. Replace the import block and add the helper. The full updated file:

```python
"""
Gate 1 — Ideas approval router.

GET  /ideas            — list ideas with source article data joined
PATCH /ideas/{idea_id} — approve or reject an idea, optionally with an edited angle
"""
from typing import Optional
from uuid import UUID

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.api.deps import get_supabase, get_settings
from app.config import Settings
from app.db.models import ApprovalStatus, IdeaApproval

router = APIRouter(prefix="/ideas", tags=["Gate 1 — Ideas"])


@router.get("")
def list_ideas(
    status: Optional[str] = Query(
        default=ApprovalStatus.PENDING.value,
        description="Filter by approval_status. Pass empty string to skip filter.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    supabase: Client = Depends(get_supabase),
) -> list[dict]:
    """Return ideas with their source article scraped data joined."""
    try:
        query = supabase.table("ideas").select("*").limit(limit)
        if status:
            query = query.eq("approval_status", status)
        resp = query.execute()
        ideas = resp.data or []

        article_ids = list({
            i["source_article_id"]
            for i in ideas
            if i.get("source_article_id")
        })

        articles_by_id: dict[str, dict] = {}
        if article_ids:
            art_resp = (
                supabase.table("raw_content")
                .select("id, url, title, source_name, publication_date, full_text, structured_summary, word_count, pre_score, vision_fallback_used, paywall_detected")
                .in_("id", article_ids)
                .execute()
            )
            for a in (art_resp.data or []):
                articles_by_id[a["id"]] = a

        for idea in ideas:
            aid = idea.get("source_article_id")
            idea["source_article"] = articles_by_id.get(aid) if aid else None

        return ideas
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/{idea_id}")
def approve_idea(
    idea_id: UUID,
    payload: IdeaApproval,
    supabase: Client = Depends(get_supabase),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Approve or reject an idea. Optionally supply an edited_angle."""
    update: dict = {"approval_status": payload.approval_status.value}
    if payload.edited_angle is not None:
        update["edited_angle"] = payload.edited_angle

    try:
        resp = (
            supabase.table("ideas")
            .update(update)
            .eq("id", str(idea_id))
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Idea not found")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if payload.approval_status == ApprovalStatus.REJECTED:
        _maybe_generate_summary(supabase, settings)

    return resp.data[0]


def _maybe_generate_summary(supabase: Client, settings: Settings) -> None:
    """
    If unsummarized rejections >= rejection_batch_size, generate and store a summary.
    Failures are silently logged — never propagated to the caller.
    """
    from app.agents.scoring.decision_summary import (
        count_unsummarized_rejections,
        fetch_recent_rejections,
        generate_decision_summary,
        write_summary,
    )
    from app.utils.logging import get_logger as _log
    log = _log(__name__)
    try:
        count, since_ts = count_unsummarized_rejections(supabase)
        if count < settings.rejection_batch_size:
            return
        rejected = fetch_recent_rejections(supabase, since_ts, count)
        client = Anthropic(api_key=settings.anthropic_api_key)
        summary = generate_decision_summary(rejected, client, settings.claude_model_light)
        write_summary(supabase, summary, count)
        log.info(f"_maybe_generate_summary: wrote summary for {count} rejections")
    except Exception as exc:
        from app.utils.logging import get_logger as _log2
        _log2(__name__).warning(f"_maybe_generate_summary failed | err={exc}")
```

- [ ] **Step 4: TypeScript check (frontend unaffected — skip) + smoke test**

```powershell
cd D:\Intern\content-automation-bot\backend
python -c "from app.api.routers.ideas import router; print('ideas router OK')"
```

Expected: `ideas router OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routers/ideas.py backend/app/config.py
git commit -m "feat: generate decision summaries after every 5 idea rejections"
```
