# Content Types Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `ContentType` enum (`news_driven`, `kb_driven`, `combined`) to the system and thread it from the Gate 1 trigger button through the API into the creation agent. The orchestrator always uses `combined`; Gate 1 exposes `news_driven` and `kb_driven` via a dropdown.

**Architecture:** `ContentType` enum goes in `models.py`. `creation_agent_task` gains a `content_type` string parameter. `content_generator.py` gains a `kb_context` parameter and conditionally retrieves KB chunks. The triggers router's `CreationTriggerRequest` gains an optional `content_type` field. The Gate 1 frontend adds a `<select>` dropdown. No new files — all changes are additive edits.

**Tech Stack:** Python 3.11, FastAPI, supabase-py, pytest + pytest-mock; Next.js 16, React 19, Tailwind 4.

---

## File Map

| Action | Path |
|--------|------|
| Modify | `backend/app/db/models.py` |
| Modify | `backend/app/queue/tasks.py` |
| Modify | `backend/app/agents/creation/content_generator.py` |
| Modify | `backend/app/api/routers/triggers.py` |
| Create | `backend/tests/test_content_types.py` |
| Modify | `frontend/app/lib/api.ts` |
| Modify | `frontend/app/ideas/page.tsx` |

---

### Task 1 — `ContentType` enum in models.py

**Files:**
- Modify: `backend/app/db/models.py`

- [ ] **Step 1: Add the enum**

In `backend/app/db/models.py`, after the `TriggerType` enum (around line 47), add:

```python
class ContentType(str, Enum):
    NEWS_DRIVEN = "news_driven"
    KB_DRIVEN   = "kb_driven"
    COMBINED    = "combined"
```

- [ ] **Step 2: Verify import**

```powershell
cd D:\Intern\content-automation-bot\backend
python -c "from app.db.models import ContentType; print([e.value for e in ContentType])"
```

Expected: `['news_driven', 'kb_driven', 'combined']`

- [ ] **Step 3: Commit**

```bash
git add backend/app/db/models.py
git commit -m "feat: add ContentType enum (news_driven, kb_driven, combined)"
```

---

### Task 2 — `content_generator.py` — add `kb_context` parameter

**Files:**
- Modify: `backend/app/agents/creation/content_generator.py`
- Create: `backend/tests/test_content_types.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_content_types.py
"""Tests for ContentType-aware content generation."""
from unittest.mock import MagicMock


def _make_idea():
    from app.db.models import Idea, Platform, ApprovalStatus
    from uuid import uuid4
    from datetime import datetime, timezone
    return Idea(
        id=uuid4(),
        platform=Platform.LINKEDIN,
        angle="Why SEBI just changed debt fund rules",
        edited_angle=None,
        source_article_id=None,
        agent_reasoning="High interest",
        source_article_date=None,
        approval_status=ApprovalStatus.APPROVED,
        score=8.0,
        recent_coverage_flag=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_news_driven_excludes_kb_context():
    """news_driven: prompt must NOT include KB context even if kb_context is provided."""
    from app.agents.creation.content_generator import generate_content

    client = MagicMock()
    msg = MagicMock()
    msg.usage.input_tokens = 100
    msg.usage.output_tokens = 50
    msg.content = [MagicMock(text='{"content_text": "Post text here.", "reasoning": "Good angle"}')]
    client.messages.create.return_value = msg

    generate_content(
        _make_idea(),
        article_context="Article about SEBI",
        brand_context="",
        client=client,
        model="claude-haiku-4-5",
        kb_context="Some KB data",
        content_type="news_driven",
    )

    call_kwargs = client.messages.create.call_args[1]
    prompt = call_kwargs["messages"][0]["content"]
    assert "Some KB data" not in prompt


def test_kb_driven_excludes_article_context():
    """kb_driven: prompt must NOT include article_context even if provided."""
    from app.agents.creation.content_generator import generate_content

    client = MagicMock()
    msg = MagicMock()
    msg.usage.input_tokens = 100
    msg.usage.output_tokens = 50
    msg.content = [MagicMock(text='{"content_text": "Post text here.", "reasoning": "Good angle"}')]
    client.messages.create.return_value = msg

    generate_content(
        _make_idea(),
        article_context="Article about SEBI",
        brand_context="",
        client=client,
        model="claude-haiku-4-5",
        kb_context="Some KB data about debt funds",
        content_type="kb_driven",
    )

    call_kwargs = client.messages.create.call_args[1]
    prompt = call_kwargs["messages"][0]["content"]
    assert "Article about SEBI" not in prompt
    assert "Some KB data" in prompt


def test_combined_includes_both():
    """combined: prompt must include both article_context and kb_context."""
    from app.agents.creation.content_generator import generate_content

    client = MagicMock()
    msg = MagicMock()
    msg.usage.input_tokens = 100
    msg.usage.output_tokens = 50
    msg.content = [MagicMock(text='{"content_text": "Post text here.", "reasoning": "Good angle"}')]
    client.messages.create.return_value = msg

    generate_content(
        _make_idea(),
        article_context="Article about SEBI",
        brand_context="",
        client=client,
        model="claude-haiku-4-5",
        kb_context="Some KB data about debt funds",
        content_type="combined",
    )

    call_kwargs = client.messages.create.call_args[1]
    prompt = call_kwargs["messages"][0]["content"]
    assert "Article about SEBI" in prompt
    assert "Some KB data" in prompt


def test_default_content_type_is_news_driven():
    """When content_type is not specified, behaves as news_driven."""
    from app.agents.creation.content_generator import generate_content

    client = MagicMock()
    msg = MagicMock()
    msg.usage.input_tokens = 100
    msg.usage.output_tokens = 50
    msg.content = [MagicMock(text='{"content_text": "Post text here.", "reasoning": "Good angle"}')]
    client.messages.create.return_value = msg

    generate_content(
        _make_idea(),
        article_context="Article data",
        brand_context="",
        client=client,
        model="claude-haiku-4-5",
        kb_context="KB data that should be excluded",
    )

    call_kwargs = client.messages.create.call_args[1]
    prompt = call_kwargs["messages"][0]["content"]
    assert "KB data that should be excluded" not in prompt
```

- [ ] **Step 2: Run tests — expect failure (function signature mismatch)**

```powershell
cd D:\Intern\content-automation-bot\backend
pytest tests/test_content_types.py -v 2>&1 | Select-Object -First 30
```

Expected: `TypeError` or `unexpected keyword argument 'kb_context'`

- [ ] **Step 3: Update `generate_content` in `content_generator.py`**

In `backend/app/agents/creation/content_generator.py`, replace the `generate_content` function signature and the `context_section` build block (lines 73–111):

```python
def generate_content(
    idea: Idea,
    article_context: str,
    brand_context: str,
    client: Anthropic,
    model: str,
    kb_context: str = "",
    content_type: str = "news_driven",
) -> ContentGenerationResult:
    """
    Generate platform-specific content for an approved idea using Claude Sonnet.

    content_type controls which context sources are included in the prompt:
      - news_driven: article_context only
      - kb_driven:   kb_context only
      - combined:    both article_context and kb_context

    Args:
        idea:            The approved Idea (uses edited_angle if set, else angle).
        article_context: Formatted summary of the source article.
        brand_context:   Formatted past brand content examples from match_brand_memory.
        client:          Anthropic sync client.
        model:           Model name (e.g. "claude-sonnet-4-5").
        kb_context:      Formatted knowledge base chunks (empty if not retrieved).
        content_type:    One of "news_driven", "kb_driven", "combined".

    Returns:
        ContentGenerationResult with draft_create=None on any failure. Never raises.
    """
    angle = idea.edited_angle or idea.angle
    platform = idea.platform.value
    guide = _PLATFORM_GUIDES.get(platform, _PLATFORM_GUIDES["linkedin"])

    context_section = ""

    if content_type == "kb_driven":
        # KB only — ignore article context
        if kb_context:
            context_section = f"\n\nKnowledge base context:\n{kb_context}"
    elif content_type == "combined":
        # Both sources
        if article_context:
            context_section = f"\n\nSource article context:\n{article_context}"
        if kb_context:
            context_section += f"\n\nKnowledge base context:\n{kb_context}"
    else:
        # news_driven (default) — article context only
        if article_context:
            context_section = f"\n\nSource article context:\n{article_context}"

    if brand_context:
        context_section += f"\n\n{brand_context}"
```

Keep everything from `user_prompt = (` onwards unchanged.

- [ ] **Step 4: Run tests — expect all pass**

```powershell
cd D:\Intern\content-automation-bot\backend
pytest tests/test_content_types.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/creation/content_generator.py backend/tests/test_content_types.py
git commit -m "feat: add content_type parameter to generate_content (news_driven/kb_driven/combined)"
```

---

### Task 3 — `tasks.py` — add `content_type` to `creation_agent_task`

**Files:**
- Modify: `backend/app/queue/tasks.py`

- [ ] **Step 1: Add `content_type` parameter to the task function**

In `backend/app/queue/tasks.py`, update the `creation_agent_task` signature from:

```python
async def creation_agent_task(
    ctx: dict,
    idea_ids: list[str],
) -> dict:
```

to:

```python
async def creation_agent_task(
    ctx: dict,
    idea_ids: list[str],
    content_type: str = "news_driven",
) -> dict:
```

- [ ] **Step 2: Add KB retrieval block and pass `content_type` to `generate_content`**

In `creation_agent_task`, after the `# Step 3 — Embed idea text and get brand context` block and before `# Step 4 — Generate content`, add:

```python
            # Step 3b — Retrieve KB context if needed
            kb_context = ""
            if content_type in ("kb_driven", "combined") and voyage_client:
                from app.agents.scoring.embedder import embed_text as _embed
                embed_input = f"{idea.platform.value}: {idea.edited_angle or idea.angle}"
                embedding = _embed(embed_input, voyage_client)
                if embedding:
                    try:
                        kb_resp = supabase.rpc(
                            "match_knowledge_base",
                            {"query_embedding": embedding, "match_count": 8},
                        ).execute()
                        kb_rows = kb_resp.data or []
                        if kb_rows:
                            kb_context = "\n\n---\n\n".join(r["content"] for r in kb_rows)
                    except Exception as kb_exc:
                        logger.warning(f"creation_agent_task: KB retrieval failed | err={kb_exc}")
```

Then update the `generate_content` call in `# Step 4` to include the new parameters:

```python
            gen_result = generate_content(
                idea, article_context, brand_ctx, anthropic_client, settings.claude_model_heavy,
                kb_context=kb_context,
                content_type=content_type,
            )
```

- [ ] **Step 3: Smoke test**

```powershell
cd D:\Intern\content-automation-bot\backend
python -c "from app.queue.tasks import creation_agent_task; import inspect; sig = inspect.signature(creation_agent_task); print(list(sig.parameters.keys()))"
```

Expected: `['ctx', 'idea_ids', 'content_type']`

- [ ] **Step 4: Commit**

```bash
git add backend/app/queue/tasks.py
git commit -m "feat: add content_type param to creation_agent_task with KB retrieval"
```

---

### Task 4 — `triggers.py` — expose `content_type` in the API

**Files:**
- Modify: `backend/app/api/routers/triggers.py`

- [ ] **Step 1: Update `CreationTriggerRequest`**

In `backend/app/api/routers/triggers.py`, update the `CreationTriggerRequest` model from:

```python
class CreationTriggerRequest(BaseModel):
    idea_ids: list[str]
```

to:

```python
class CreationTriggerRequest(BaseModel):
    idea_ids: list[str]
    content_type: str = "news_driven"
```

- [ ] **Step 2: Pass `content_type` to `enqueue_job`**

In the `trigger_creation` endpoint, update the `enqueue_job` call from:

```python
    job = await pool.enqueue_job("creation_agent_task", idea_ids=body.idea_ids)
```

to:

```python
    job = await pool.enqueue_job(
        "creation_agent_task",
        idea_ids=body.idea_ids,
        content_type=body.content_type,
    )
```

Also update the return dict to include `content_type`:

```python
    return {
        "job_id": job.job_id if job else None,
        "status": "enqueued",
        "agent": "creation",
        "idea_count": len(body.idea_ids),
        "content_type": body.content_type,
    }
```

- [ ] **Step 3: Smoke test**

```powershell
cd D:\Intern\content-automation-bot\backend
python -c "from app.api.routers.triggers import CreationTriggerRequest; r = CreationTriggerRequest(idea_ids=['a']); print(r.content_type)"
```

Expected: `news_driven`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/routers/triggers.py
git commit -m "feat: expose content_type in creation trigger API endpoint"
```

---

### Task 5 — Frontend api.ts — update `triggerCreation`

**Files:**
- Modify: `frontend/app/lib/api.ts`

- [ ] **Step 1: Add `contentType` parameter to `triggerCreation`**

In `frontend/app/lib/api.ts`, replace the existing `triggerCreation` function:

```typescript
export async function triggerCreation(ideaIds: string[]) {
  return apiFetch<{ job_id: string; status: string; agent: string; idea_count: number }>(
    "/trigger/creation",
    { method: "POST", body: JSON.stringify({ idea_ids: ideaIds }) }
  );
}
```

with:

```typescript
export async function triggerCreation(ideaIds: string[], contentType: string = "news_driven") {
  return apiFetch<{ job_id: string; status: string; agent: string; idea_count: number; content_type: string }>(
    "/trigger/creation",
    { method: "POST", body: JSON.stringify({ idea_ids: ideaIds, content_type: contentType }) }
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
git add frontend/app/lib/api.ts
git commit -m "feat: add contentType parameter to triggerCreation API function"
```

---

### Task 6 — Gate 1 frontend — content type selector

**Files:**
- Modify: `frontend/app/ideas/page.tsx`

- [ ] **Step 1: Add content type state and dropdown**

In `frontend/app/ideas/page.tsx`, inside the `IdeasPage` component:

**Add state variable** (after `sendingToCreation` state):
```typescript
  const [contentType, setContentType] = useState<string>("news_driven");
```

**Replace the approved-ideas action block** (the `{approvedIds.length > 0 && ...}` block at the bottom of the component). Replace the entire block with:

```tsx
      {approvedIds.length > 0 && (
        <div className="flex items-center gap-3 mt-4 flex-wrap">
          <select
            value={contentType}
            onChange={(e) => setContentType(e.target.value)}
            className="text-sm border border-gray-300 rounded px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="news_driven">News-driven</option>
            <option value="kb_driven">KB-driven</option>
          </select>
          <button
            onClick={async () => {
              setSendingToCreation(true);
              setCreationMsg(null);
              try {
                const r = await triggerCreation(approvedIds, contentType);
                setCreationMsg(
                  `Creation queued for ${r.idea_count} idea(s) as ${r.content_type} — job_id: ${r.job_id ?? "n/a"}`
                );
                setApprovedIds([]);
              } catch (e: unknown) {
                setCreationMsg(
                  e instanceof Error ? `Error: ${e.message}` : "Failed"
                );
              } finally {
                setSendingToCreation(false);
              }
            }}
            disabled={sendingToCreation}
            className="bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded"
          >
            {sendingToCreation
              ? "Sending..."
              : `Send ${approvedIds.length} approved idea(s) to Creation`}
          </button>
          {creationMsg && (
            <p className="text-sm text-gray-600">{creationMsg}</p>
          )}
        </div>
      )}
```

- [ ] **Step 2: Verify TypeScript compiles**

```powershell
cd D:\Intern\content-automation-bot\frontend
npx tsc --noEmit 2>&1 | Select-Object -First 20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/ideas/page.tsx
git commit -m "feat: add content type selector to Gate 1 creation trigger"
```
