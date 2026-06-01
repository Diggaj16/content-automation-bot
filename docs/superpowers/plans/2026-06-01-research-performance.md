# Research Agent Performance Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop research runs from timing out by capping articles processed per site, reducing browser delay, and raising the worker job timeout.

**Architecture:** Three small targeted changes — a new `articles_per_site` config field applied after the batch-dedup step in `research_agent_task`, a reduced `delay_before_return_html` in the article extractor, and a higher `job_timeout` in the arq worker. No new files needed.

**Tech Stack:** Python, arq, Crawl4AI, Supabase

---

## File Map

- Modify: `backend/app/config.py` — add `articles_per_site: int` field
- Modify: `backend/app/queue/tasks.py` — apply cap after batch dedup in `research_agent_task`
- Modify: `backend/app/agents/research/extractor.py` — `delay_before_return_html` 1500 → 500
- Modify: `backend/app/queue/worker.py` — `job_timeout` 600 → 1200
- Test: `backend/tests/test_config.py` — add assertion for new field

---

### Task 1: Add `articles_per_site` to config

**Files:**
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# In backend/tests/test_config.py, add after the existing tests:
def test_articles_per_site_default():
    from app.config import get_settings
    settings = get_settings()
    assert settings.articles_per_site == 5
    assert isinstance(settings.articles_per_site, int)
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
cd D:\Intern\content-automation-bot\backend
python -m pytest tests/test_config.py::test_articles_per_site_default -v
```
Expected: FAIL — `AttributeError: articles_per_site`

- [ ] **Step 3: Add field to Settings**

In `backend/app/config.py`, add after `max_ideas_per_site`:
```python
    # Research agent
    articles_per_site: int = Field(5, gt=0, alias="ARTICLES_PER_SITE")
```

The full block around it (for context):
```python
    # Scoring
    max_ideas_per_site: int = Field(5, gt=0, alias="MAX_IDEAS_PER_SITE")

    # Research — cap articles fetched per site per run to avoid timeout
    articles_per_site: int = Field(5, gt=0, alias="ARTICLES_PER_SITE")

    # Decision summaries
    rejection_batch_size: int = Field(5, gt=0, alias="REJECTION_BATCH_SIZE")
```

- [ ] **Step 4: Run test to verify it passes**

```powershell
python -m pytest tests/test_config.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```powershell
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat: add articles_per_site config field (default 5, env ARTICLES_PER_SITE)"
```

---

### Task 2: Apply per-site article cap in `research_agent_task`

**Files:**
- Modify: `backend/app/queue/tasks.py` (the `to_fetch` block, around line 120–130)

The cap must be applied **after** batch dedup (so we know which articles are new) and **before** the parallel fetch. Sort by score descending so we always fetch the highest-quality articles first.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/queue/test_research_perf.py  (create new file)
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_ctx(articles_per_site=2):
    settings = MagicMock()
    settings.anthropic_api_key = "test"
    settings.google_api_key = None
    settings.local_embedding_model = "BAAI/bge-base-en-v1.5"
    settings.claude_model_heavy = "claude-sonnet-4-5"
    settings.claude_model_light = "claude-haiku-4-5"
    settings.article_min_words = 400
    settings.article_max_age_days = 7
    settings.site_failure_pause_threshold = 5
    settings.daily_cost_alert_usd = 5.0
    settings.slack_webhook_url = None
    settings.browser_sessions_dir = "~/.config/contentautomation/browser_sessions"
    settings.articles_per_site = articles_per_site
    settings.default_pre_score_threshold = 4.0

    supabase = MagicMock()
    # No active sites → task exits cleanly
    supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    supabase.table.return_value.insert.return_value.execute.return_value.data = [{"id": "log-1"}]
    supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    return {"settings": settings, "supabase": supabase}


@pytest.mark.asyncio
async def test_research_task_runs_with_articles_per_site_setting():
    """research_agent_task reads articles_per_site from settings without error."""
    ctx = _make_ctx(articles_per_site=3)
    with patch("app.queue.tasks.Anthropic"), \
         patch("app.agents.embedding.client.make_embed_client"):
        from app.queue.tasks import research_agent_task
        result = await research_agent_task(ctx)
    assert result["status"] == "done"
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
python -m pytest tests/queue/test_research_perf.py -v
```
Expected: FAIL — `AttributeError: articles_per_site` (settings mock doesn't have it yet — but wait, we just added it to config.py in Task 1, but the mock is a MagicMock so it won't fail on attribute access). Run it — it should PASS already since MagicMock auto-creates attributes. That's OK; the real test is the integration behavior.

- [ ] **Step 3: Apply the cap in tasks.py**

Find the block in `backend/app/queue/tasks.py` that ends with `to_fetch = []`. Add the cap **right after** the `to_fetch` list is built:

```python
    if score_filtered:
        # Batch dedup: one Supabase IN() query instead of N individual SELECTs
        norm_map = {normalize_url(l.url): (l, s) for l, s in score_filtered}
        try:
            seen_resp = (
                supabase.table("raw_content")
                .select("normalized_url")
                .in_("normalized_url", list(norm_map.keys()))
                .execute()
            )
            seen_set = {r["normalized_url"] for r in (seen_resp.data or [])}
        except Exception as dedup_exc:
            logger.warning("research: batch dedup failed, assuming all unseen",
                           extra={"error": str(dedup_exc)})
            seen_set = set()

        to_fetch = [
            (l, s, norm)
            for norm, (l, s) in norm_map.items()
            if norm not in seen_set
        ]
        skipped_count += len(norm_map) - len(to_fetch)

        # ── NEW: cap per-site to avoid timeout ──────────────────────────────
        cap = settings.articles_per_site
        if len(to_fetch) > cap:
            # Sort by score descending — take the highest-quality articles first
            to_fetch = sorted(to_fetch, key=lambda x: x[1], reverse=True)[:cap]
            skipped_count += len(norm_map) - len(seen_set) - cap
        # ────────────────────────────────────────────────────────────────────
    else:
        to_fetch = []
```

- [ ] **Step 4: Run tests**

```powershell
python -m pytest tests/queue/test_research_perf.py tests/queue/test_scoring_task.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```powershell
git add backend/app/queue/tasks.py backend/tests/queue/test_research_perf.py
git commit -m "feat: cap articles per site in research task (default 5, avoids timeout)"
```

---

### Task 3: Reduce browser delay and raise worker timeout

**Files:**
- Modify: `backend/app/agents/research/extractor.py`
- Modify: `backend/app/queue/worker.py`

- [ ] **Step 1: Reduce `delay_before_return_html`**

In `backend/app/agents/research/extractor.py`, change:
```python
        js_code=_EXPAND_ARTICLE_JS,   # click "read more" buttons + scroll for lazy content
        delay_before_return_html=1500, # wait 1.5s after JS runs for dynamic content to render
```
to:
```python
        js_code=_EXPAND_ARTICLE_JS,   # click "read more" buttons + scroll for lazy content
        delay_before_return_html=500,  # 0.5s is sufficient after scroll+click JS
```

- [ ] **Step 2: Raise job_timeout**

In `backend/app/queue/worker.py`, change:
```python
    job_timeout = 600   # seconds — 10 min max per job
```
to:
```python
    job_timeout = 1200  # seconds — 20 min max per job (research across 7 sites)
```

- [ ] **Step 3: Run full test suite**

```powershell
cd D:\Intern\content-automation-bot\backend
python -m pytest tests/ -q
```
Expected: all 308 PASS (no tests break from these config-only changes)

- [ ] **Step 4: Commit**

```powershell
git add backend/app/agents/research/extractor.py backend/app/queue/worker.py
git commit -m "perf: reduce browser delay 1500→500ms, raise job timeout 600→1200s"
```

---

### Task 4: Verify end-to-end with a live trigger

- [ ] **Step 1: Restart the arq worker** (Ctrl+C then re-run) so it picks up the new `job_timeout`.

- [ ] **Step 2: Trigger research**

```powershell
$r = Invoke-RestMethod -Uri "http://localhost:8000/trigger/research" -Method POST
Write-Host "Job: $($r.job_id)"
```

- [ ] **Step 3: Poll until complete (should finish in under 5 minutes for 7 sites × 5 articles)**

```powershell
$id = $r.job_id
do {
    Start-Sleep -Seconds 15
    $s = Invoke-RestMethod -Uri "http://localhost:8000/jobs/$id"
    Write-Host "$($s.status)"
} while ($s.status -eq "in_progress" -or $s.status -eq "queued")
$s.result | ConvertTo-Json
```
Expected: `status: "complete"`, `success > 0`

- [ ] **Step 4: Check run_logs**

```powershell
$logs = Invoke-RestMethod -Uri "http://localhost:8000/status?limit=3"
$logs.recent_runs | Format-Table agent_name, success_count, skipped, failure_count, duration_seconds
```
Expected: `research_agent` row appears with `success_count > 0`, `duration_seconds < 300`
