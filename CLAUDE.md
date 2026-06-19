# content-automation-bot — Claude Reference

## What This Is
AI-powered content pipeline for **Growthvine Capital** (Indian wealth-management). Discovers Indian finance news, generates platform-specific content ideas and drafts, routes through two human approval gates, then publishes to LinkedIn/Twitter/Blog/Email.

---

## Stack

| Layer | Tech |
|-------|------|
| API | FastAPI + uvicorn (port 8000) |
| Task queue | arq (Redis-backed, 5 dedicated workers) |
| LLM | Anthropic Claude — Sonnet (generation) + Haiku (scoring) |
| Orchestrator | LangGraph ReAct agent (30+ tools) |
| Embeddings | Gemini text-embedding-004 (768-dim) → fastembed BGE fallback |
| DB | PostgreSQL + pgvector (self-hosted). Supabase client still present — migration in progress |
| Scraping | Playwright (Microsoft Edge channel) |
| Web search | Tavily → DuckDuckGo fallback |
| Frontend | Next.js 14 App Router + Tailwind + SWR (port 3000) |
| Infra | Docker Compose (7 services) |

---

## Pipeline (6 Agents, 2 Human Gates)

```
[Research]      Daily 6 AM IST cron
  Scrape 8 curated sites → pre-score headlines (Haiku) → fetch articles → summarize (Sonnet) → raw_content

[Scoring]       Auto-chains after Research
  Embed → check duplicate coverage → generate 3 ideas/article (Sonnet) → ideas (pending_approval)

  ⏸ GATE 1 — human approves/rejects ideas via /ideas

[Creation]      Triggered manually or via orchestrator
  Fetch approved ideas → brand voice RAG → KB RAG → generate draft (Sonnet) → flag finance claims → drafts (pending_approval)

  ⏸ GATE 2 — human approves/rejects drafts via /drafts

[Publishing]    Every 15 min cron
  Post approved drafts where scheduled_at <= now() → published_posts → schedule analytics

[Analytics]     Deferred at +24h / +72h / +7d from publish
  Fetch metrics → performance_score → update style_guide at 7d mark

[Orchestrator]  Always-on conversational agent
  Chat interface to control entire pipeline (trigger, approve, generate, search, manage KB/sites)
```

---

## Entry Points

```bash
# Backend API
cd backend && python -m uvicorn app.api.main:app --reload --port 8000

# arq worker (all agents)
cd backend && python -m arq app.queue.worker.WorkerSettings

# Dedicated workers (one per agent type — preferred in prod)
python -m arq app.queue.research_worker.ResearchWorkerSettings
python -m arq app.queue.scoring_worker.ScoringWorkerSettings
python -m arq app.queue.creation_worker.CreationWorkerSettings
python -m arq app.queue.publishing_worker.PublishingWorkerSettings
python -m arq app.queue.analytics_worker.AnalyticsWorkerSettings

# Frontend
cd frontend && npm run dev

# Full stack
docker compose up --build
```

---

## Key Files

| Purpose | File |
|---------|------|
| Settings (all env vars) | `backend/app/config.py` |
| All 6 agent tasks | `backend/app/queue/tasks.py` |
| Pydantic DB models | `backend/app/db/models.py` |
| SQLAlchemy ORM | `backend/app/db/orm.py` |
| DB session factory | `backend/app/db/session.py` |
| API factory | `backend/app/api/main.py` |
| Gate 1 router | `backend/app/api/routers/ideas.py` |
| Gate 2 router | `backend/app/api/routers/drafts.py` |
| Agent trigger router | `backend/app/api/routers/triggers.py` |
| LangGraph agent builder | `backend/app/agents/orchestrator/agent.py` |
| 30+ orchestrator tools | `backend/app/agents/orchestrator/tools.py` |
| Article scraper | `backend/app/agents/research/scraper.py` |
| Article extractor | `backend/app/agents/research/extractor.py` |
| Idea generator | `backend/app/agents/scoring/idea_generator.py` |
| Draft generator | `backend/app/agents/creation/content_generator.py` |
| Publishing stubs | `backend/app/agents/publishing/poster.py` |
| Analytics stubs | `backend/app/agents/analytics/metrics_fetcher.py` |
| Cost logging | `backend/app/utils/logging.py` |
| DB init script | `backend/scripts/init_db.py` |
| Seed script | `backend/scripts/seed.py` |

---

## Database (15 Tables)

`curated_sites`, `raw_content`, `ideas`, `drafts`, `published_posts`, `content_analytics`, `style_guide`, `brand_memory` (768-dim vectors), `knowledge_base` (768-dim vectors), `user_decision_summaries`, `topic_performance_model`, `email_subscribers`, `run_logs`, `cost_log`

Migrations: `backend/app/db/migrations/001–005` (raw SQL, no Alembic)

---

## Required Env Vars

```env
DATABASE_URL=postgresql+psycopg://...
ANTHROPIC_API_KEY=sk-ant-...
REDIS_URL=redis://localhost:6379

# Optional but needed for full function
SUPABASE_URL=...                  # legacy — migration in progress
SUPABASE_SERVICE_ROLE_KEY=...     # legacy
GOOGLE_API_KEY=...                # Gemini embeddings (falls back to fastembed)
TAVILY_API_KEY=...                # web search (falls back to DuckDuckGo)
SLACK_WEBHOOK_URL=...             # cost alerts
BACKEND_API_KEY=...               # shared secret for frontend proxy

# Model selection
CLAUDE_MODEL_HEAVY=claude-sonnet-4-6
CLAUDE_MODEL_LIGHT=claude-haiku-4-5-20251001
```

---

## Active Migration: Supabase → Self-Hosted Postgres

**Status:** In progress. Both systems coexist.
- New code: SQLAlchemy ORM (`app/db/orm.py`, `app/db/session.py`)
- Old code: ~27 Supabase client imports still throughout backend
- `seed.py` still writes to Supabase; `init_db.py` targets Postgres
- Do NOT assume a route uses SQLAlchemy — check which client it imports

---

## What's Stubbed (Not Production-Ready)

| Feature | File | Status |
|---------|------|--------|
| LinkedIn posting | `publishing/poster.py` | Returns fake ID |
| Twitter posting | `publishing/poster.py` | Returns fake ID |
| Blog/CMS posting | `publishing/poster.py` | Returns fake ID |
| Email sending | `publishing/poster.py` | Returns fake ID |
| Analytics metrics | `analytics/metrics_fetcher.py` | Returns random mock data |
| Reddit scraping | `research/reddit_scraper.py` | Dead code stub |

---

## Known Issues

1. **Zero test coverage** — `backend/tests/` has mock infra but no test cases
2. **Supabase→Postgres migration incomplete** — dual-stack, risk of divergent writes
3. **`backend/package.json` typo** — `"srw": "^0.0.4"` (not a real package), breaks Docker npm ci
4. **`BACKEND_API_KEY` undocumented** — not in docker-compose.yml, causes 403s from frontend
5. **Stale model IDs in `.env.example`** — defaults to `claude-sonnet-4-5`, use `4-6`
6. **No CI/CD** — no GitHub Actions, all deploys manual
7. **No Alembic** — SQL migrations managed manually, no rollback support
8. **Broad `except Exception`** — throughout agents, swallows unexpected failures
