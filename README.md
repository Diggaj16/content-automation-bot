# Content Automation — Indian Finance Content Pipeline

An autonomous content pipeline for Indian finance publishing. Scrapes curated news sites, scores and filters article ideas using LLMs, drafts platform-specific posts, and routes everything through two human approval gates before publishing.

---

## What it does

```
Research → Score → [Gate 1: Approve Ideas] → Create → [Gate 2: Approve Drafts] → Publish
```

1. **Research** — Crawl4AI scrapes 7+ curated Indian finance news sites (Mint, Business Standard, ET Markets, etc.). Articles are pre-scored by Claude Haiku, batch-deduped against the DB, and summarised by Claude Sonnet.
2. **Scoring** — Approved articles are fed to an idea generator. Claude produces 2–4 content angles per article, scored and ranked.
3. **Gate 1 — Ideas** — Human approves or rejects ideas in the admin panel. Rejected ideas feed a decision-summary model that learns your taste over time.
4. **Creation** — Approved ideas go to a content generator. Claude Sonnet writes platform-specific drafts (LinkedIn, Twitter thread, blog outline, email newsletter) grounded in the source article and your brand voice.
5. **Gate 2 — Drafts** — Human reviews and approves drafts. Optional scheduling.
6. **Publishing** — Approved drafts are published to the configured platforms. Analytics are recorded.
7. **Orchestrator** — A natural-language chat agent with full pipeline control: trigger agents, approve/reject ideas and drafts, manage subscribers, search the web and generate on-demand posts.

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI 0.111 |
| Job queue | arq (Redis-backed async task queue) |
| Database | Supabase (PostgreSQL + PostgREST) |
| Web scraping | Crawl4AI 0.4 (headless Chromium) |
| LLM | Anthropic Claude (Haiku for scoring, Sonnet for generation) |
| Orchestrator | LangGraph ReAct agent |
| Web search | Tavily (primary) / DuckDuckGo (fallback) |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| Data fetching | SWR (stale-while-revalidate) |

---

## Project structure

```
content-automation-bot/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── research/       # Scraper, extractor, prescorer, summariser
│   │   │   ├── scoring/        # Idea generator, embedder, coverage checker
│   │   │   ├── creation/       # Content generator, brand context, KB retrieval
│   │   │   ├── publishing/     # Platform posters
│   │   │   ├── analytics/      # Metrics fetcher, DB writer
│   │   │   └── orchestrator/   # LangGraph agent, tools (28 tools), system prompt
│   │   ├── api/
│   │   │   ├── routers/        # ideas, drafts, triggers, tables, subscribers, KB, orchestrator
│   │   │   ├── deps.py         # FastAPI dependencies (auth, DB, queue)
│   │   │   └── main.py         # App factory, CORS, global auth
│   │   ├── db/
│   │   │   ├── models.py       # Pydantic models for all 15 DB tables
│   │   │   └── client.py       # Supabase client singleton
│   │   ├── queue/
│   │   │   ├── tasks.py        # arq task functions (research, scoring, creation, publishing, analytics)
│   │   │   └── worker.py       # arq WorkerSettings (concurrency, cron, Redis)
│   │   ├── config.py           # pydantic-settings Settings class
│   │   └── utils/              # Logging, Slack alerts, cost formatting
│   ├── tests/                  # 327 tests across all agents and API routes
│   └── pyproject.toml
└── frontend/
    ├── app/
    │   ├── api/proxy/          # Server-side catch-all proxy to backend (path allowlist)
    │   ├── components/
    │   │   ├── GlobalJobMonitor.tsx   # Sidebar live job status (adaptive polling)
    │   │   └── JobStatusBadge.tsx
    │   ├── hooks/
    │   │   └── useJobStatus.ts        # Per-job polling hook with store integration
    │   ├── lib/
    │   │   ├── api.ts                 # Typed API client (all backend calls)
    │   │   └── jobStore.ts            # localStorage-backed cross-tab job tracker
    │   ├── ideas/page.tsx             # Gate 1 — idea approval (with SWR + React.memo)
    │   ├── drafts/page.tsx            # Gate 2 — draft approval
    │   ├── orchestrator/page.tsx      # Chat interface to the LangGraph agent
    │   ├── tables/[table]/page.tsx    # Generic admin browser for all 15 DB tables
    │   ├── page.tsx                   # Dashboard — trigger buttons, run logs, cost
    │   └── layout.tsx                 # Sidebar nav + GlobalJobMonitor mount
    └── package.json
```

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- Redis (local or remote)
- Supabase project with the schema applied
- Anthropic API key

---

## Setup

### 1. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -e ".[dev]"
```

Create `backend/.env`:

```env
# Required
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
ANTHROPIC_API_KEY=sk-ant-...
REDIS_URL=redis://localhost:6379

# Optional
API_KEY=your-admin-secret          # Enables X-Api-Key auth on all routes
TAVILY_API_KEY=tvly-...            # Web search (falls back to DuckDuckGo)
SLACK_WEBHOOK_URL=https://hooks.slack.com/...  # Cost + paywall alerts
GOOGLE_API_KEY=...                 # Gemini embeddings (falls back to local BAAI model)

# Tuning (all have defaults)
ARTICLES_PER_SITE=5                # Max articles fetched per site per run
ARTICLE_MIN_WORDS=400
ARTICLE_MAX_AGE_DAYS=7
DEFAULT_PRE_SCORE_THRESHOLD=4.0
DAILY_COST_ALERT_USD=5.0
```

### 2. Frontend

```powershell
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
BACKEND_URL=http://127.0.0.1:8000
BACKEND_API_KEY=your-admin-secret   # Must match API_KEY in backend/.env
```

---

## Running

You need **two terminal windows** running simultaneously.

**Terminal 1 — API server:**

```powershell
cd backend
python -m uvicorn app.api.main:app --reload --port 8000
```

**Terminal 2 — arq worker** (executes all pipeline jobs):

```powershell
cd backend
python -m arq app.queue.worker.WorkerSettings
```

**Terminal 3 — Frontend:**

```powershell
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

> The arq worker **must** be running for any pipeline job to execute. Without it, triggered jobs will queue in Redis and never complete.

---

## Usage

### Dashboard

- **Trigger Research** — scrapes all active curated sites, scores articles, stores new content
- **Trigger Scoring** — generates ideas from unprocessed articles
- Run logs and daily cost summary are displayed live

### Gate 1 — Ideas (`/ideas`)

- Browse pending, approved, and rejected ideas
- Click **Approve** to edit the angle and send to Gate 2, or **Reject**
- Select multiple approved ideas → **Send to Creation** → choose content type (news-driven, KB-driven, combined)

### Gate 2 — Drafts (`/drafts`)

- Review generated drafts per platform
- Approve with optional scheduled publish time, or reject

### Orchestrator (`/orchestrator`)

Natural language chat with full pipeline control. Examples:

```
"Show me the 5 highest-scored pending ideas"
"Approve the SEBI one and reject the rest"
"Write a LinkedIn post about RBI's rate decision today"
"Add subscriber test@example.com"
"Trigger research and tell me when it's done"
```

### Admin Tables (`/tables/*`)

Browse and edit all 15 database tables directly: raw_content, ideas, drafts, published_posts, brand_memory, curated_sites, email_subscribers, knowledge_base, run_logs, cost_log, and more.

---

## Pipeline configuration

### Adding a news source

Via orchestrator: `"Add ET Markets at https://economictimes.com/markets with threshold 5"`

Or via the Curated Sites table.

### Brand voice

Upload past posts as brand memory examples via the orchestrator:
```
"Save this LinkedIn post as a brand memory example: [paste your best post]"
```

The creation agent uses these as style references.

### Knowledge base

Upload PDFs or text files via `/knowledge-base` — they are chunked, embedded, and available for `kb_driven` and `combined` content generation.

### Paywalled sites

```
"Login to https://www.livemint.com"
```
A browser window opens on the worker machine. Log in once — sessions are saved to `~/.config/contentautomation/browser_sessions/` and reused on all future scrapes.

---

## Security

All API routes require `X-Api-Key: <API_KEY>` when `API_KEY` is set in the environment. The frontend proxy forwards this automatically. The `/subscribers/unsubscribe` endpoint is intentionally public (used from email links).

To enable auth:
```env
# backend/.env
API_KEY=generate-a-strong-secret-here

# frontend/.env.local
BACKEND_API_KEY=generate-a-strong-secret-here
```

---

## Architecture notes

**Parallel pipeline** — The research task processes all sites concurrently via `asyncio.gather`. Each site scrapes, scores, deduplicates, fetches, and summarises in parallel. The creation task processes all approved ideas concurrently with a concurrency cap of 3.

**Non-blocking** — All Anthropic API calls use `AsyncAnthropic`. All Supabase calls (synchronous client) are wrapped in `asyncio.to_thread` so the arq event loop is never blocked.

**Job persistence** — Job status persists across page navigation and browser restarts via localStorage (`jobStore.ts`). `GlobalJobMonitor` polls active jobs every 2s and idles at 10s when the pipeline is quiet.

**Orchestrator memory** — Conversation history is stored in-process (`MemorySaver`). History is lost on worker restart. For production multi-instance deployments, replace with a Redis or Postgres checkpointer.

---

## Tests

```powershell
cd backend
python -m pytest                          # all 327 tests
python -m pytest tests/agents/research/   # research pipeline only
python -m pytest tests/api/ -v            # API integration tests
```

---

## Cost

Typical per-run costs (7 sites, 5 articles each):

| Step | Model | Approx cost |
|------|-------|------------|
| Pre-score headlines (7 calls) | Claude Haiku | ~$0.001 |
| Summarise articles (35 calls) | Claude Sonnet | ~$0.05–0.15 |
| Generate ideas (35 calls) | Claude Sonnet | ~$0.05–0.10 |
| Generate drafts (per idea) | Claude Sonnet | ~$0.03–0.05 each |

Set `DAILY_COST_ALERT_USD` to receive a Slack alert if a single run exceeds the threshold.
