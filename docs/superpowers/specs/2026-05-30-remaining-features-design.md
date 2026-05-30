# Remaining Features Design Spec

**Date:** 2026-05-30  
**Project:** Content Automation System — Indian Finance  
**Features:** Orchestrator Agent (LangGraph), User Decision Summaries, Email Subscriber Management, Knowledge Base Ingestion, 3 Content Types

---

## Context

All 6 agent task loops are implemented and wired into arq. The 15-table DB schema exists in Supabase. FastAPI serves trigger endpoints and the approval gate CRUD. The frontend has Gate 1, Gate 2, Dashboard, and a generic table browser for all tables.

What's missing:
1. Orchestrator agent (natural language interface with LangGraph)
2. User decision summary generation on idea rejection
3. Email subscriber management + unsubscribe endpoint
4. Knowledge base ingestion (upload → chunk → embed → store)
5. Three content types exposed in creation flow (News-driven, KB-driven, Combined)

---

## Feature 1 — Orchestrator Agent (LangGraph ReAct)

### Architecture

Uses `langgraph.prebuilt.create_react_agent` — the prebuilt ReAct graph. Accepts a list of tool callables and a system prompt. Internally builds the Reason → Act → Observe loop as a compiled LangGraph graph. Uses `MemorySaver` to keep per-thread conversation history so follow-up messages work naturally.

### New files

**`backend/app/agents/orchestrator/__init__.py`**  
Empty init.

**`backend/app/agents/orchestrator/tools.py`**  
10 tool functions decorated with `@tool` (LangGraph/LangChain compatible):

| Tool | Description |
|------|-------------|
| `trigger_research(topic: str = None)` | Enqueues `research_agent_task` via arq pool. Optional topic hint passed as arg. |
| `trigger_scoring()` | Enqueues `scoring_agent_task`. |
| `trigger_creation(idea_ids: list[str], content_type: str = "combined")` | Enqueues `creation_agent_task` with Combined type (orchestrator always uses combined). |
| `get_pending_ideas(limit: int = 10)` | Returns pending_approval ideas with score and platform. |
| `get_analytics_summary()` | Returns last 5 run_logs + platform performance averages from content_analytics. |
| `add_curated_site(name: str, url: str, threshold: float = 4.0)` | Inserts into curated_sites. Validates URL format. Returns confirmation with new site id. |
| `remove_curated_site(site_name: str)` | Sets `active = false` for matching site (soft delete). Returns site name removed. |
| `list_curated_sites()` | Returns all sites with active status, consecutive_failures, last_run_at. |
| `get_topic_performance()` | Returns all rows from topic_performance_model ordered by performance_score desc. |
| `get_run_logs(limit: int = 5)` | Returns last N run_logs with agent_name, duration, token cost, success/failure counts. |

All tools receive `supabase` and `arq_pool` via closure (injected at agent construction time, not as tool args).

**`backend/app/agents/orchestrator/agent.py`**  
```python
# Builds and returns the compiled LangGraph ReAct agent.
# Call build_orchestrator_agent(supabase, arq_pool, anthropic_api_key) once at startup.
# Returns a compiled graph; call .ainvoke({messages: [...]}, config={configurable: {thread_id: ...}})
```

System prompt covers:
- Role: non-technical ops interface for Indian finance content pipeline
- Capabilities: trigger agents, query data, manage curated sites, explain performance
- Tone: concise, factual, tells user what it did and what state things are in
- For destructive actions (remove site): confirms the action in the response and states what was changed

### New API endpoint

**`backend/app/api/routers/orchestrator.py`**

`POST /orchestrate`  
Request: `{ "message": str, "thread_id": str }`  
Response: `{ "response": str, "tools_used": list[str], "thread_id": str }`

- Builds (or reuses cached) agent on first call
- Invokes `agent.ainvoke()` with the message
- Extracts tool names from the response message list for the `tools_used` field
- Returns the final text response

Registered in `main.py` as `/orchestrate`.

### Config addition

`ORCHESTRATOR_MODEL` env var (default: `claude-sonnet-4-6`) — the model the orchestrator uses. Added to `Settings`.

### New dependency

`langgraph>=0.2.0` added to `pyproject.toml`.

### Frontend

**`frontend/app/orchestrator/page.tsx`**  
Chat UI:
- Message history list (user messages right-aligned, assistant left-aligned)
- "Tools used:" tag row under each assistant response (e.g., `get_pending_ideas`, `list_curated_sites`)
- Text input + Send button at bottom
- Thread ID generated as `crypto.randomUUID()` on first load, stored in `localStorage`
- Calls `POST /api/proxy/orchestrate`
- Loading spinner while waiting

**`frontend/app/lib/api.ts`** — add `orchestrate(message, threadId)` function.

**`frontend/app/layout.tsx`** — add "Orchestrator" link in the MAIN nav section above Dashboard.

---

## Feature 2 — User Decision Summaries on Rejection

### Behaviour

When `PATCH /ideas/{idea_id}` is called with `approval_status = "rejected"`:
1. Write the rejection to DB (existing behaviour, unchanged)
2. Count rejected ideas created after the timestamp of the most recent `user_decision_summaries` row
3. If count >= `REJECTION_BATCH_SIZE` (default 5):
   a. Fetch those N rejected ideas: `angle`, `platform`, `agent_reasoning`
   b. Call Claude Haiku with a prompt asking for a 2–3 sentence pattern summary
   c. Insert into `user_decision_summaries` (`summary_text`, `rejection_count = N`)

This is synchronous in the request — Haiku is fast (< 1s). If the Claude call fails, it logs a warning and does not block the rejection response.

### New module

**`backend/app/agents/scoring/decision_summary.py`**

Functions:
- `count_unsummarized_rejections(supabase) -> int` — counts rejections newer than last summary
- `fetch_recent_rejections(supabase, since_ts, limit) -> list[dict]` — fetches angle+platform+reasoning
- `generate_decision_summary(rejected_ideas, client, model) -> str` — single Claude Haiku call
- `write_summary(supabase, summary_text, rejection_count) -> None` — inserts row

### Changes to existing files

**`backend/app/api/routers/ideas.py`** — after the Supabase update succeeds and status is "rejected":
```python
from app.agents.scoring.decision_summary import (
    count_unsummarized_rejections, fetch_recent_rejections,
    generate_decision_summary, write_summary
)
# ... after update succeeds:
if payload.approval_status == ApprovalStatus.REJECTED:
    _maybe_generate_summary(supabase, settings, anthropic_client)
```

**`backend/app/config.py`** — add `rejection_batch_size: int = Field(5, alias="REJECTION_BATCH_SIZE")`.

### No DB migration needed

`user_decision_summaries` table exists with columns `id, summary_text, rejection_count, created_at`.

---

## Feature 3 — Email Subscriber Management + Unsubscribe

### DB migration

**`backend/app/db/migrations/002_subscribers_token.sql`**
```sql
ALTER TABLE email_subscribers
ADD COLUMN IF NOT EXISTS unsubscribe_token TEXT UNIQUE DEFAULT gen_random_uuid()::TEXT;

UPDATE email_subscribers
SET unsubscribe_token = gen_random_uuid()::TEXT
WHERE unsubscribe_token IS NULL;
```

Run once in Supabase SQL Editor.

### New router

**`backend/app/api/routers/subscribers.py`**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/subscribers` | List all subscribers. Optional `?active=true/false` filter. |
| `POST` | `/subscribers` | Add subscriber. Body: `{email, name?}`. Auto-generates `unsubscribe_token`. Returns 409 if email already exists. |
| `PATCH` | `/subscribers/{id}` | Update `name` and/or `active`. Body: `{name?, active?}`. |
| `DELETE` | `/subscribers/{id}` | Soft-delete: sets `active = false`. Does not remove row. |
| `GET` | `/unsubscribe` | Query param: `?token=xxx`. No auth. Sets `active = false`. Returns HTML confirmation page. Returns 404 HTML if token not found. |

Registered in `main.py` as `/subscribers` (and `/unsubscribe` at root level for clean email links).

### Publishing agent

Publishing is **disabled** (stubbed) until platform APIs are connected. The subscriber management endpoints are built now so the data layer is ready. When publishing is enabled, the email sender will append:
```
Unsubscribe: {BASE_URL}/unsubscribe?token={subscriber.unsubscribe_token}
```

### Frontend

**`frontend/app/subscribers/page.tsx`**  
Dedicated page (better UX than generic table browser):
- Subscriber table: email, name, status (active/inactive), subscribed date
- "Add subscriber" form: email + optional name fields + submit
- Toggle active/inactive inline per row (PATCH call)
- Unsubscribe token shown as a copyable link for testing

Added to sidebar under "Pipeline".

**`frontend/app/lib/api.ts`** — add `getSubscribers()`, `addSubscriber()`, `updateSubscriber()`, `deleteSubscriber()` functions.

---

## Feature 4 — Knowledge Base Ingestion

### New router

**`backend/app/api/routers/knowledge_base.py`**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/knowledge-base/upload` | Multipart file upload. Accepts PDF or TXT. Extracts text, chunks, optionally embeds (if VOYAGE_API_KEY set), writes to `knowledge_base`. Returns `{source_file, chunks_ingested}`. |
| `GET` | `/knowledge-base` | Lists ingested files: `{source_file, chunk_count, created_at}` grouped by `source_file`. |
| `DELETE` | `/knowledge-base/{source_file}` | Deletes all `knowledge_base` rows where `source_file = {source_file}`. |

### New module

**`backend/app/agents/orchestrator/kb_ingester.py`**

Functions:
- `extract_text(filename: str, content_bytes: bytes) -> str`  
  PDF: uses `PyPDF2.PdfReader` to extract page text. TXT: UTF-8 decode.
  
- `chunk_text(text: str, max_words: int = 500, overlap_words: int = 50) -> list[str]`  
  Splits on double-newlines (paragraphs) first, then by word count. Sliding window overlap between chunks preserves context at boundaries.

- `ingest_file(filename: str, text: str, voyage_client, supabase) -> int`  
  For each chunk: if voyage_client is not None, embed via `embed_text()`; insert row into `knowledge_base`. Returns count of chunks written. Uses upsert with `ON CONFLICT (source_file, chunk_index) DO UPDATE` so re-uploading a file replaces old chunks.

### New dependencies

`PyPDF2>=3.0.0` added to `pyproject.toml`.

### Frontend

**`frontend/app/knowledge-base/page.tsx`**  
- Drag-and-drop file upload zone (accepts `.pdf`, `.txt`)
- Upload button triggers `POST /api/proxy/knowledge-base/upload`
- After upload: shows success toast with chunk count
- File list below: filename, chunk count, upload date, Delete button
- Delete calls `DELETE /api/proxy/knowledge-base/{encodeURIComponent(filename)}`

Added to sidebar under "Data Stores".

**`frontend/app/lib/api.ts`** — add `uploadKbFile()`, `listKbFiles()`, `deleteKbFile()` functions.

---

## Feature 5 — Three Content Types in Creation Flow

### Content type enum

Three types defined in `app/db/models.py`:
```python
class ContentType(str, Enum):
    NEWS_DRIVEN = "news_driven"   # source article only
    KB_DRIVEN   = "kb_driven"     # knowledge base chunks only  
    COMBINED    = "combined"      # article + KB chunks (used by orchestrator)
```

### Creation agent changes

**`backend/app/queue/tasks.py`** — `creation_agent_task` gains `content_type: str = "news_driven"` parameter.

**`backend/app/agents/creation/content_generator.py`** — `generate_content()` already accepts `article_context` and `brand_ctx`. Add `kb_context: str = ""` parameter. The prompt template conditionally includes:
- `news_driven`: article_context only (current behaviour)
- `kb_driven`: kb_context only (retrieves top-8 KB chunks via `match_knowledge_base` RPC)
- `combined`: both article_context + kb_context

KB retrieval: embed the idea angle text → call `supabase.rpc("match_knowledge_base", ...)` → format top-8 chunks as context string.

### Trigger endpoint change

**`backend/app/api/routers/triggers.py`** — `POST /trigger/creation` body gains optional `content_type: str = "news_driven"` field. Passes through to `creation_agent_task`.

### Gate 1 frontend change

**`frontend/app/ideas/page.tsx`** — the "Send N approved ideas to Creation" button area gains a `<select>` dropdown:
- Options: "News-driven" (value: `news_driven`), "KB-driven" (value: `kb_driven`)
- Combined is not shown here — orchestrator creates combined posts via chat
- Default: "News-driven"
- Selected value passed as `content_type` in the `triggerCreation()` API call

**`frontend/app/lib/api.ts`** — `triggerCreation(ideaIds, contentType)` gains `contentType` param.

---

## API surface summary

| New endpoint | Method | Auth |
|-------------|--------|------|
| `/orchestrate` | POST | Service role (same as all backend endpoints) |
| `/subscribers` | GET, POST | Service role |
| `/subscribers/{id}` | PATCH, DELETE | Service role |
| `/unsubscribe` | GET | None (email link) |
| `/knowledge-base/upload` | POST | Service role |
| `/knowledge-base` | GET | Service role |
| `/knowledge-base/{source_file}` | DELETE | Service role |

---

## Dependencies to add

```toml
# pyproject.toml additions
langgraph>=0.2.0
langchain-anthropic>=0.1.0   # LangGraph's Anthropic integration
PyPDF2>=3.0.0
```

---

## What is NOT changing

- Publishing agent remains stubbed (no real platform API calls) until user connects platform credentials
- The arq cron schedule is unchanged
- All existing agent tasks (research, scoring, creation, publishing, analytics) are unchanged except creation gaining the `content_type` parameter
- The generic table browser continues to work for all tables

---

## Self-review checklist

- [x] No TBD or TODO left — all sections specify exact file paths, function signatures, and data flows
- [x] Internal consistency — LangGraph agent uses same arq pool as trigger endpoints; tools use same Supabase client singleton
- [x] Scope — 5 coherent features that share infrastructure (all use existing Supabase client, most share existing agents)
- [x] Ambiguity resolved — content type selection: Gate 1 UI (news/kb), orchestrator always combined; unsubscribe: token-based; decision summaries: batch of 5; publishing: stubbed
