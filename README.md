# content-automation-bot — Growthvine Capital Content Pipeline

An end-to-end AI pipeline that discovers Indian finance news, generates platform-specific content ideas, writes drafts in Growthvine Capital's brand voice, and routes everything through two human approval gates before publishing.

---

## Pipeline Overview

```
Curated News Sites
       │
       ▼
 Research Agent  (daily 6 AM IST)
   Scrape section pages → pre-score headlines (Haiku) →
   fetch articles (HTTP + browser fallback) → summarise (Sonnet) → store raw_content
       │
       ▼  (auto-chains)
 Scoring Agent
   Read unprocessed articles → embed → generate 2 ideas/article
   (Sonnet, aware of your past rejections + brand memory) → store ideas
       │
       ▼  GATE 1 — you approve / reject / edit ideas via Orchestrator chat
       │
 Creation Agent  (triggered on approved ideas)
   Fetch article context + brand voice (brand_memory) →
   generate platform draft (Sonnet) → detect finance flags → store draft
       │
       ▼  GATE 2 — you approve / reject / schedule drafts via Orchestrator chat
       │
 Publishing Agent  (every 15 min)
   Post to platform → record in published_posts →
   schedule analytics at 24h / 72h / 7d
       │
       ▼
 Analytics Agent  (deferred events)
   Fetch engagement metrics → score performance →
   update platform style guide at 7-day mark
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI |
| Task queue | arq (async Redis queue) |
| Database | Supabase (PostgreSQL + pgvector) |
| LLM | Anthropic Claude (Sonnet 4.5 for generation, Haiku 4.5 for scoring) |
| Browser automation | Playwright (Microsoft Edge, raw — no crawl4ai) |
| Embeddings | Google Gemini text-embedding-004 (768-dim) with local fastembed fallback |
| Orchestrator | LangGraph ReAct agent |
| Web search | Tavily (primary) / DuckDuckGo (fallback) |
| Frontend | Next.js 14 (App Router) + Tailwind CSS |

---

## Project Structure

```
content-automation-bot/
├── backend/
│   └── app/
│       ├── config.py                    # All settings (env vars)
│       ├── db/
│       │   ├── client.py                # Supabase singleton
│       │   ├── models.py                # Pydantic models for every table
│       │   └── migrations/              # SQL migrations (run in order: 001 → 004)
│       ├── queue/
│       │   ├── worker.py                # arq WorkerSettings + cron schedule
│       │   └── tasks.py                 # All 6 agent task functions
│       ├── api/
│       │   ├── main.py                  # FastAPI app factory + lifespan
│       │   ├── deps.py                  # Dependency injection (auth, DB, queue)
│       │   └── routers/
│       │       ├── ideas.py             # Gate 1: approve / reject ideas
│       │       ├── drafts.py            # Gate 2: approve / reject drafts
│       │       ├── triggers.py          # Trigger agents + poll job status
│       │       ├── orchestrator.py      # LangGraph chat endpoint
│       │       ├── tables.py            # Generic admin table browser
│       │       ├── subscribers.py       # Email subscriber management
│       │       └── knowledge_base.py    # KB file upload + management
│       ├── agents/
│       │   ├── research/
│       │   │   ├── scraper.py           # Section page → article links (Playwright)
│       │   │   ├── extractor.py         # URL → article text + metadata (HTTP + browser)
│       │   │   ├── filters.py           # Freshness / length / dedup checks
│       │   │   ├── prescorer.py         # Batch headline scoring with Haiku
│       │   │   ├── summariser.py        # Article → structured summary (Sonnet)
│       │   │   └── db_writer.py         # Write raw_content + site health
│       │   ├── scoring/
│       │   │   ├── idea_generator.py    # Article → 2 content ideas (Sonnet)
│       │   │   ├── embedder.py          # Single-text embedding helper
│       │   │   ├── coverage_checker.py  # Detect recently covered topics
│       │   │   ├── decision_summary.py  # Rejection pattern summariser (Haiku)
│       │   │   └── db_writer.py         # Write ideas to DB
│       │   ├── creation/
│       │   │   ├── content_generator.py # Idea → platform draft (Sonnet)
│       │   │   ├── brand_context.py     # Fetch brand voice examples from DB
│       │   │   ├── finance_flags.py     # Flag financial claims in draft text
│       │   │   └── db_writer.py         # Write drafts to DB
│       │   ├── publishing/
│       │   │   ├── poster.py            # Post to platforms [STUB — needs API credentials]
│       │   │   └── db_writer.py         # Record published posts
│       │   ├── analytics/
│       │   │   ├── metrics_fetcher.py   # Fetch engagement metrics [STUB]
│       │   │   └── db_writer.py         # Write analytics + update style guide
│       │   ├── embedding/
│       │   │   └── client.py            # Gemini / fastembed factory (768-dim)
│       │   └── orchestrator/
│       │       ├── agent.py             # Build LangGraph ReAct agent
│       │       ├── tools.py             # 30+ LangChain tool functions
│       │       └── kb_ingester.py       # PDF/TXT → chunks → DB
│       └── utils/
│           ├── logging.py               # Structured JSON decision logging
│           └── slack.py                 # Slack alert helper
└── frontend/
    └── app/
        ├── page.tsx                     # Dashboard (trigger buttons, run logs, cost)
        ├── layout.tsx                   # Root layout + sidebar nav
        ├── ideas/page.tsx               # Gate 1 approval UI
        ├── drafts/page.tsx              # Gate 2 approval UI
        ├── orchestrator/page.tsx        # Chat UI for LangGraph agent
        ├── tables/[table]/page.tsx      # Generic admin browser for all DB tables
        ├── knowledge-base/page.tsx      # KB file upload + management
        ├── subscribers/page.tsx         # Email subscriber list
        ├── api/proxy/[...path]/         # Server-side proxy to backend (adds API key)
        ├── components/                  # Shared UI (TableBrowser, JobStatusBadge, GlobalJobMonitor)
        ├── hooks/useJobStatus.ts        # Per-job polling hook with localStorage store
        └── lib/                         # api.ts HTTP client, jobStore.ts cross-tab state
```

---

## File-by-File Reference

### `app/config.py`

Loads all configuration from environment variables via Pydantic BaseSettings.

| Symbol | Description |
|---|---|
| `Settings` | Central config class. Fields: `supabase_url`, `supabase_service_role_key`, `anthropic_api_key`, `google_api_key`, `tavily_api_key`, `redis_url`, `slack_webhook_url`, `daily_cost_alert_usd`, `claude_model_heavy` (Sonnet), `claude_model_light` (Haiku), `article_min_words`, `article_max_age_days`, `default_pre_score_threshold`, `articles_per_site`, `max_ideas_per_site`, `rejection_batch_size`, `browser_sessions_dir`, `site_failure_pause_threshold`. |
| `get_settings()` | LRU-cached singleton — call this everywhere instead of constructing Settings directly. |

---

### `app/db/client.py`

Singleton Supabase client using the service-role key (bypasses Row Level Security).

| Symbol | Description |
|---|---|
| `get_supabase_client()` | Returns cached Supabase client, creating it on first call. |
| `reset_client()` | Clears the cache to force a fresh connection. |
| `get_supabase_client_fresh()` | Drops stale connection pool and returns a brand-new client. |

---

### `app/db/models.py`

Pydantic models for every database table.
Convention: `<Table>` = full DB row (includes id, timestamps), `<Table>Create` = insert payload.

| Model | Table | Key Fields |
|---|---|---|
| `CuratedSite` / `CuratedSiteCreate` | `curated_sites` | `section_url`, `active`, `pre_score_threshold`, `consecutive_failures`, `last_run_at` |
| `RawContent` / `RawContentCreate` | `raw_content` | `url`, `normalized_url`, `title`, `full_text`, `structured_summary` (nested JSON), `pre_score`, `processed`, `source_name` |
| `StructuredSummary` | nested JSONB | `story_narrative`, `key_data_points[]`, `mechanism`, `implications`, `content_angles[]` |
| `Idea` / `IdeaCreate` / `IdeaApproval` | `ideas` | `angle`, `edited_angle`, `platform`, `score`, `approval_status`, `recent_coverage_flag`, `source_article_id` |
| `Draft` / `DraftCreate` / `DraftApproval` | `drafts` | `content_text`, `platform`, `finance_flags[]`, `approval_status`, `scheduled_at`, `source_idea_id` |
| `FinanceFlag` | nested JSONB | `flag_type`, `text`, `severity` |
| `PublishedPost` | `published_posts` | `platform`, `post_identifier`, `draft_id` |
| `ContentAnalytics` | `content_analytics` | `post_id`, `measurement_period` (24h/72h/7d), `metrics` (JSONB), `performance_score` |
| `StyleGuide` | `style_guide` | `platform`, `top_performing_angles`, `optimal_length`, `format_preferences` |
| `RunLog` / `RunLogCreate` | `run_logs` | `agent_name`, `trigger_type`, `processed_count`, `success_count`, `failure_count`, `reasoning_trace`, `errors`, `token_cost` |
| `CostLog` | `cost_log` | `agent_name`, `date`, `token_count`, `estimated_cost_usd` |
| `EmailSubscriber` | `email_subscribers` | `email`, `name`, `active`, `source` |
| `BrandMemory` | `brand_memory` | `content`, `platform`, `embedding` (vector 768), `performance_metrics` |
| **Enums** | — | `Platform` (linkedin/twitter/blog/email), `ApprovalStatus` (pending_approval/approved/rejected), `DraftStatus`, `TriggerType` (cron/event/manual/orchestrator), `ContentType` (news_driven/kb_driven/combined) |

---

### `app/queue/worker.py`

arq worker configuration. Start with: `python -m arq app.queue.worker.WorkerSettings`

| Symbol | Description |
|---|---|
| `startup(ctx)` | Initialises Supabase client and Settings in `ctx` dict on worker boot. Reconfigures stdout/stderr to UTF-8 to handle Playwright Unicode output on Windows. |
| `shutdown(ctx)` | Cleanup hook (currently no-op). |
| `WorkerSettings` | Registers 6 task functions (`research_agent_task`, `scoring_agent_task`, `creation_agent_task`, `publishing_agent_task`, `analytics_agent_task`, `login_site_task`). `max_jobs=10`, `job_timeout=2400s` (40 min). Cron: research daily at 00:30 UTC (6 AM IST), publishing every 15 min (0, 15, 30, 45). |

---

### `app/queue/tasks.py`

Six async agent task functions executed by the arq worker.

#### `research_agent_task(ctx, topic=None, url=None)`
Trigger: Daily cron or manual `POST /trigger/research`

1. Fetch all active curated sites from DB
2. Launch one shared Playwright/Edge browser for all section page scrapes
3. For each site (all 8 in parallel):
   - Scrape section page with `scrape_homepage()` — dismiss popups, extract internal article links
4. Pre-score all headlines in batches of 40 with Claude Haiku; retry on rate limits with exponential backoff
5. Filter: `score >= site.pre_score_threshold` + skip known non-article URL patterns (calculators, tickers, etc.)
6. Batch dedup check against `raw_content.normalized_url`
7. Cap to `articles_per_site` (default 5), ranked by pre-score descending
8. Fetch each article with `fetch_article()`: try plain HTTP first (~1-2s), fall back to Playwright browser if content is thin (<200 words)
9. Filter: paywall (`word_count < 80`), staleness (`> article_max_age_days`), length (`< article_min_words`)
10. Summarise each passing article with Claude Sonnet → `StructuredSummary`
11. Write to `raw_content`; update site health (`record_site_success` / `record_site_failure`)
12. Auto-chain to `scoring_agent_task`

#### `scoring_agent_task(ctx)`
Trigger: Event after research, or manual `POST /trigger/scoring`

1. Fetch up to 50 unprocessed `raw_content` rows
2. Fetch latest rejection summary from `user_decision_summaries` (injected into prompt to avoid repeating rejected angles)
3. For each article:
   - Embed `title + story_narrative` using `embed_text()`
   - Check `check_recent_coverage()` via pgvector RPC — flag if similar content was recently published
   - Call `generate_ideas()` with article summary + rejection context → exactly 2 ideas per article
4. Cap per-site ideas (`max_ideas_per_site=5` across one run)
5. Write ideas to `ideas` table with `approval_status=pending_approval`
6. Mark article as `processed=true`

#### `creation_agent_task(ctx, idea_ids, content_type="news_driven")`
Trigger: Manual via orchestrator `send_ideas_to_creation` tool with approved idea IDs

1. Batch-fetch all requested ideas in one query
2. For each idea (up to 3 concurrent):
   - Fetch source article's `structured_summary` for grounding facts
   - Embed idea text; retrieve top-5 similar brand memory posts via `match_brand_memory` RPC for style matching
   - If `content_type` is `kb_driven` or `combined`: retrieve KB chunks via `match_knowledge_base` RPC
   - Generate draft with Claude Sonnet (brand voice + article facts + optional KB context)
   - Run `detect_finance_flags()` on draft text — flags company names, ₹ figures, regulatory claims, investment advice
   - Write draft to `drafts` table with `approval_status=pending_approval`

#### `publishing_agent_task(ctx)`
Trigger: Cron every 15 min (minutes 0, 15, 30, 45)

1. Fetch drafts with `approval_status=approved` AND `scheduled_at <= now()`
2. For each draft: call `post_to_platform()` → returns `post_identifier` **[STUB — no real API wired]**
3. Write to `published_posts`; update draft status to `published`
4. Enqueue `analytics_agent_task` deferred by 24h, 72h, 7d

#### `analytics_agent_task(ctx, post_id, measurement_period)`
Trigger: Deferred events from publishing agent at +24h, +72h, +7d

1. Fetch published post record
2. Call `fetch_metrics()` **[STUB — returns randomized mock data]**
3. Calculate `performance_score` (0–100 weighted by platform's key metric)
4. Write to `content_analytics`
5. If `measurement_period == "7d"`: call `update_style_guide()` to refresh platform style insights

#### `login_site_task(ctx, login_url)`
Trigger: Manual via orchestrator `login_to_site` tool

Opens a visible (non-headless) Edge browser at `login_url` with a persistent profile saved to `browser_sessions_dir/{domain}`. Polls for successful auth redirect (URL leaves login/signin path) for up to 5 minutes, then saves session cookies for future scrapes.

---

### `app/api/main.py`

FastAPI application factory.

| Symbol | Description |
|---|---|
| `lifespan(app)` | Context manager: creates arq connection pool on startup, closes on shutdown. |
| `create_app()` | Returns configured FastAPI instance — mounts all routers, sets CORS (all origins in dev), applies API key guard. |
| `app` | Module-level instance consumed by uvicorn. |

---

### `app/api/deps.py`

FastAPI dependency injection helpers, imported by every router.

| Symbol | Description |
|---|---|
| `get_settings()` | Returns cached `Settings`. |
| `get_supabase()` | Returns Supabase client singleton. |
| `get_arq_pool(request)` | Returns arq Redis pool from `app.state` (or `None` if Redis unavailable). |
| `verify_api_key(x_api_key, settings)` | Enforces `X-Api-Key` header when `API_KEY` env var is set; passes through in dev. |

---

### `app/api/routers/ideas.py`

Gate 1 — idea review and approval.

| Endpoint | Description |
|---|---|
| `GET /ideas` | Return ideas filtered by `approval_status`, `platform`, `limit`. Includes joined source article title and date. |
| `PATCH /ideas/{idea_id}` | Approve (optionally with `edited_angle`) or reject. After rejection, check if unsummarised rejection count hit `rejection_batch_size` → auto-generate rejection summary with Haiku and store in `user_decision_summaries`. |

---

### `app/api/routers/drafts.py`

Gate 2 — draft review and scheduling.

| Endpoint | Description |
|---|---|
| `GET /drafts` | Return drafts filtered by `approval_status`, `platform`, `limit`. |
| `PATCH /drafts/{draft_id}` | Approve (optionally with `content_text` override and `scheduled_at`) or reject. |

---

### `app/api/routers/triggers.py`

Agent control and job monitoring.

| Endpoint | Description |
|---|---|
| `POST /trigger/research` | Enqueue `research_agent_task` immediately. Returns `job_id`. |
| `POST /trigger/scoring` | Enqueue `scoring_agent_task`. Returns `job_id`. |
| `POST /trigger/creation` | Enqueue `creation_agent_task` with `idea_ids` (max 50) and `content_type`. |
| `GET /jobs/{job_id}` | Poll arq job: returns status (`queued / in_progress / complete / failed`) and result when done. |
| `GET /status` | Returns recent `run_logs` (default 10, max 100) and today's `cost_log` per agent. |

---

### `app/api/routers/orchestrator.py`

LangGraph conversational agent endpoint.

| Endpoint | Description |
|---|---|
| `POST /orchestrate` | Send `message` + optional `thread_id`. Returns `response` text, `tools_used` list, `thread_id` for conversation continuity. Agent compiled once on first call; subsequent calls reuse cached graph. |

---

### `app/api/routers/knowledge_base.py`

Knowledge base document management for RAG-grounded content.

| Endpoint | Description |
|---|---|
| `POST /knowledge-base/upload` | Upload PDF or TXT (max 50 MB). Extract text → split into ~500-word chunks → embed each → write to `knowledge_base` table. Returns `source_file` and `chunks_ingested`. |
| `GET /knowledge-base` | List all ingested files grouped by `source_file`. |
| `DELETE /knowledge-base/{source_file}` | Delete all chunks for a source file. |

---

### `app/api/routers/subscribers.py`

Email newsletter subscriber management. The unsubscribe endpoint is intentionally public (used from email footer links).

---

### `app/api/routers/tables.py`

Generic admin table browser. Supports reading all 15 DB tables with pagination, filtering, and column visibility. `VECTOR_COLUMNS` maps tables with vector columns (`brand_memory`, `knowledge_base`) so embeddings are excluded from display.

---

### `app/agents/research/scraper.py`

Fetches a news site's section page and extracts article links using Playwright.

| Symbol | Description |
|---|---|
| `BROWSER_ARGS` | Chromium launch flags: `--no-proxy-server`, `--disable-ipv6`, `--disable-blink-features=AutomationControlled`. Shared with extractor and tasks. |
| `USER_AGENT` | Windows Edge user agent string. Shared with extractor. |
| `_SKIP_URL_RE` | Regex filtering non-article URLs: `/page/`, `/tag/`, `/calculator/`, `/podcast/`, `share-price-\d+` (BS stock ticker pages), etc. |
| `_ARTICLE_URL_RE` | Regex identifying article URLs: date-based paths (`/2024/06/`), `/news/`, `/article`, `/story`, `.html` extension, 5+ digit IDs (Financial Express style). |
| `_DISMISS_POPUPS_JS` | JavaScript injected post-load to click cookie consent buttons (`#onetrust-accept-btn-handler`, `.login_close_btn`, etc.) and force-remove overlays covering >50% of viewport. Fixes MoneyControl, ET, Financial Express, The Hindu. Also re-enables body scrolling. |
| `ArticleLink` | Pydantic model: `url`, `title`, `source_name`. |
| `_looks_like_article(href, text)` | Returns `True` if href passes skip/article regexes and headline text is ≥ 20 chars. |
| `_scrape_with_browser(section_url, site_name, browser, timeout_ms)` | Core scraping logic using an existing Playwright Browser. Creates new context/page, navigates, dismisses popups, extracts all `<a href>` elements, filters to same-domain article links. Closes context when done. |
| `scrape_homepage(section_url, site_name, browser=None, timeout_ms=30000)` | Public entry point. Pass `browser` to reuse a shared instance (fast, ~1.5s per site). Without `browser`, creates own Playwright process (~10s). Never raises — returns `[]` on any failure. |

---

### `app/agents/research/extractor.py`

Fetches a single article URL and extracts its text content, title, and publication date.

| Symbol | Description |
|---|---|
| `BROWSER_ARGS` | Shared browser launch flags (imported by scraper.py and tasks.py). |
| `USER_AGENT` | Shared user agent string. |
| `_CONTENT_SELECTORS` | Ordered list of CSS selectors tried for content extraction: `article`, `[class*=articleBody]`, `[class*=story-body]`, `main`, `[role=main]`, `#content`, etc. First selector returning ≥80 words wins. |
| `_EXPAND_JS` | JavaScript that: (1) clicks "read more" / "show more" buttons; (2) force-removes large popup overlays; (3) re-enables body scrolling; (4) scrolls page to trigger lazy-loaded content. |
| `_TRACKING_PARAMS` | Set of UTM and tracking query params stripped during URL normalisation. |
| `_HTTP_WORD_THRESHOLD = 200` | If HTTP extraction returns fewer words, trigger browser fallback. |
| `_PAYWALL_WORD_THRESHOLD = 80` | Below this, mark `paywall_detected=True`. |
| `ArticleContent` | Pydantic model: `url`, `normalized_url`, `title`, `full_text`, `word_count`, `paywall_detected`, `publication_date`. |
| `normalize_url(url)` | Strip fragment, tracking params, trailing slash; lowercase scheme+host. Used for DB deduplication. |
| `_extract_from_html(html)` | Parse HTML with BeautifulSoup. Try article selectors then body fallback (strips `script/style/nav/header/footer/aside`). Returns `(full_text, title, raw_date_str)`. |
| `_fetch_via_http(url, timeout_s=12)` | Fetch page HTML with httpx (no JavaScript, ~1-2s). Raises on failure so caller can fall back to browser. |
| `_fetch_via_browser(url, timeout_ms, browser)` | Navigate with Playwright, run `_EXPAND_JS`, get full rendered HTML, call `_extract_from_html`. Accepts optional shared browser (creates new context/page, closes after). |
| `fetch_article(url, timeout_ms=30000, browser=None)` | Primary entry point. Tries HTTP first; if `word_count < _HTTP_WORD_THRESHOLD`, falls back to Playwright browser. Pass `browser` to reuse shared instance. Never raises — returns `paywall_detected=True` on any failure. |

---

### `app/agents/research/filters.py`

Cheap eligibility checks run before expensive article fetching. All synchronous.

| Symbol | Description |
|---|---|
| `is_url_seen(normalized_url, supabase)` | SELECT on `raw_content.normalized_url` with LIMIT 1. Returns `True` if already stored. On DB error returns `False` (fail-open — the DB upsert handles duplicates gracefully). |
| `is_article_fresh(publication_date, max_age_days, now=None)` | Returns `True` if article is within `max_age_days`. Articles with no publication date are treated as fresh. Handles naive datetimes by assuming UTC. |
| `is_article_long_enough(word_count, min_words)` | Returns `True` if `word_count >= min_words`. |

---

### `app/agents/research/prescorer.py`

Batch-scores news headlines 0–10 with Claude Haiku before the expensive article fetch step.

| Symbol | Description |
|---|---|
| `_CHUNK_SIZE = 40` | Max headlines per API call. Prevents empty-response failures on large batches (sites with 60-80 links). |
| `_MAX_TOKENS = 1024` | Token budget per API call. |
| `_MAX_RETRIES = 3` | Retry attempts for transient errors. |
| `_BASE_BACKOFF = 15` | Base seconds for exponential backoff: 15s → 30s → 60s. |
| `PreScoreResult` | Dataclass: `scores: list[float]`, `input_tokens`, `output_tokens`, `failed: bool`. `failed=True` signals callers to bypass threshold filter so no articles are silently lost. |
| `_parse_scores(raw, expected)` | Parse JSON array from model response. Falls back to regex extraction (`[\d\s.,+-]+`) if the model wraps the array in prose. Raises `ValueError` on empty response (triggers retry). |
| `_retry_after(exc)` | Extract `Retry-After` seconds from `RateLimitError` response header (defaults to `_BASE_BACKOFF`). |
| `async_pre_score_headlines(titles, client, model)` | Main entry point. Filters blank titles before each chunk (blank titles cause Claude to respond with instructions instead of scores). Scores in chunks of 40, merges results. Retries on `RateLimitError` (header-based wait), `APIConnectionError`, `ValueError`, `JSONDecodeError`. Returns `PreScoreResult(failed=True)` only after all retries exhausted. |

---

### `app/agents/research/summariser.py`

Summarises article full text into structured JSON using Claude Sonnet.

| Symbol | Description |
|---|---|
| `SummariseResult` | Dataclass: `summary: StructuredSummary | None`, `input_tokens`, `output_tokens`. |
| `async_summarise_article(full_text, title, client, model)` | Truncates input to 8000 chars, calls Sonnet with a structured extraction prompt. Parses JSON response into `StructuredSummary` with `story_narrative`, `key_data_points[]`, `mechanism`, `implications`, `content_angles[]`. Returns empty result on any failure. |

---

### `app/agents/research/db_writer.py`

Persists research results and tracks site health.

| Symbol | Description |
|---|---|
| `upsert_raw_content(supabase, content, summary, score, source_name)` | INSERT or UPDATE `raw_content` keyed on `normalized_url`. Returns row UUID or `None` on failure. |
| `record_site_success(supabase, site_id)` | Set `last_run_at=now()`, `consecutive_failures=0`. |
| `record_site_failure(supabase, site_id, error_msg, pause_threshold)` | Increment `consecutive_failures`. If it reaches `pause_threshold`, set `active=false` (site paused until manually re-enabled). |
| `upsert_cost_log(supabase, agent_name, total_usd, token_count)` | Read-then-write daily cost accumulator in `cost_log` (Supabase client can't do atomic increments). |

---

### `app/agents/scoring/idea_generator.py`

Generates platform-specific content ideas from a summarised article.

| Symbol | Description |
|---|---|
| `_SYSTEM_PROMPT` | Instructs Claude to act as a content strategist for Indian retail investors. Returns exactly 2 ideas in a JSON array, each on a different platform. |
| `IdeaGenerationResult` | Dataclass: `ideas: list[IdeaCreate]`, `input_tokens`, `output_tokens`. |
| `generate_ideas(article, client, model, rejection_summary="")` | Build user prompt from article's structured summary. If `rejection_summary` is provided (fetched from `user_decision_summaries`), appends a "REJECTION PATTERNS TO AVOID" section so the model avoids angles you've previously rejected. Parses Claude's JSON into `IdeaCreate` objects, filtering unknown platforms. Returns empty result on any failure. |

---

### `app/agents/scoring/embedder.py`

Thin wrapper for embedding a single string.

| Symbol | Description |
|---|---|
| `embed_text(text, embed_client)` | Call `embed_client.embed_one(text)`. Returns embedding vector (768 floats) or `[]` on failure. Never raises. |

---

### `app/agents/scoring/coverage_checker.py`

Detects if similar content was recently published to avoid repeating topics.

| Symbol | Description |
|---|---|
| `check_recent_coverage(embedding, platform, supabase, days_back=30, threshold=0.85)` | Call `check_recent_brand_coverage` Postgres RPC. Uses cosine similarity on `brand_memory` vectors. Returns `True` if a similar post exists within `days_back` on the same `platform`. Returns `False` if embedding is empty, RPC fails, or no match found. Never raises. |

---

### `app/agents/scoring/decision_summary.py`

Builds rejection-pattern summaries that feed back into the scoring agent to improve idea quality over time.

| Symbol | Description |
|---|---|
| `count_unsummarized_rejections(supabase)` | Returns `(count, since_ts)` — number of rejected ideas since the last summary and that summary's timestamp (`None` if no summary exists yet). |
| `fetch_recent_rejections(supabase, since_ts, limit)` | Fetches rejected idea angles and platforms since `since_ts`. Capped at 200 rows to prevent an unbounded first run. |
| `generate_decision_summary(rejected_ideas, client, model)` | Calls Claude Haiku to write 2-3 sentences identifying rejection patterns (e.g., "avoid stock-specific tips, prefer macro policy angles for LinkedIn"). Returns `""` on failure. |
| `write_summary(supabase, summary_text, rejection_count)` | INSERT row into `user_decision_summaries` with the summary text and rejection count. |

---

### `app/agents/scoring/db_writer.py`

Persists scoring results to the database.

| Symbol | Description |
|---|---|
| `write_ideas(supabase, ideas, article_id, pub_date)` | Batch-insert `IdeaCreate` objects. Links to `source_article_id` and copies `source_article_date`. Returns list of created UUIDs. |
| `mark_article_processed(supabase, article_id)` | Set `raw_content.processed=true` so the article isn't scored again. |
| `upsert_cost_log(supabase, agent_name, total_usd, token_count)` | Accumulate daily cost in UTC. |

---

### `app/agents/creation/content_generator.py`

Generates the actual post content for a given platform using Claude Sonnet.

| Symbol | Description |
|---|---|
| `_PLATFORM_GUIDES` | Platform writing instructions: LinkedIn (1000-1500 chars, hook + narrative + insight + CTA), Twitter (5-7 tweet thread with 🧵), Blog (400-600 word SEO outline), Email (250-400 word newsletter section with subject + preview). |
| `ContentGenerationResult` | Dataclass: `draft_create: DraftCreate | None`, `input_tokens`, `output_tokens`. |
| `async_generate_content(idea, article_context, brand_context, client, model, kb_context="", content_type="news_driven")` | Builds prompt with: idea angle + platform guide + article context (for `news_driven`/`combined`) + brand voice examples (always) + KB context (for `kb_driven`/`combined`). Each context source is capped at 4000 chars. Calls Sonnet; parses `{"content_text": ..., "reasoning": ...}` JSON response. Returns `ContentGenerationResult` with `draft_create=None` on failure. |

---

### `app/agents/creation/brand_context.py`

Retrieves past Growthvine Capital posts as style examples for the creation agent.

| Symbol | Description |
|---|---|
| `get_brand_context(embedding, platform, supabase, match_count=5)` | Call `match_brand_memory` Postgres RPC with 768-dim query embedding and platform filter. Returns top matching posts formatted as a bullet list prefixed with "Past brand content examples:". Returns `""` if embedding is empty, RPC fails, or table is empty. |

---

### `app/agents/creation/finance_flags.py`

Flags potentially sensitive financial content in generated drafts for human review.

| Symbol | Description |
|---|---|
| `detect_finance_flags(content_text)` | Scans for: BSE/NSE company and ticker mentions, specific ₹ amounts and percentages, regulatory references (SEBI/RBI/AMFI), and investment advice language ("buy", "sell", "guaranteed returns"). Returns list of `FinanceFlag` objects each with `flag_type`, `text`, `severity`. |

---

### `app/agents/creation/db_writer.py`

Persists draft content to the database.

| Symbol | Description |
|---|---|
| `write_draft(supabase, draft_create)` | INSERT into `drafts` table. Returns draft UUID or `None` on failure. |
| `upsert_cost_log(supabase, agent_name, total_usd, token_count)` | Accumulate daily cost in UTC (`datetime.now(timezone.utc).date()`). |

---

### `app/agents/publishing/poster.py`

Platform posting functions.
**All functions are currently stubs** — they return fake identifiers without making real API calls.

| Symbol | Description |
|---|---|
| `post_linkedin(content_text, settings)` | **[STUB]** Returns `"linkedin-stub-{uuid}"`. Needs LinkedIn API credentials. |
| `post_twitter(content_text, settings)` | **[STUB]** Returns `"twitter-stub-{uuid}"`. Needs Twitter API v2 credentials. |
| `post_blog(content_text, settings)` | **[STUB]** Returns `"blog-stub-{uuid}"`. Needs CMS / WordPress API. |
| `post_email(content_text, settings)` | **[STUB]** Returns `"email-stub-{uuid}"`. Needs SendGrid / Mailchimp. |
| `post_to_platform(platform, content_text, settings)` | Dispatches to correct poster. Returns `post_identifier` string or `None` on failure. |

---

### `app/agents/publishing/db_writer.py`

Records published posts and updates draft status.

| Symbol | Description |
|---|---|
| `write_published_post(supabase, platform, post_identifier, draft_id)` | INSERT into `published_posts`. Returns UUID or `None`. |
| `update_draft_published(supabase, draft_id)` | Set `drafts.approval_status = "published"`. |

---

### `app/agents/analytics/metrics_fetcher.py`

Fetches engagement metrics for published posts.
**Currently returns randomized mock data** — real platform APIs not yet wired.

| Symbol | Description |
|---|---|
| `fetch_metrics(platform, post_identifier, measurement_period)` | **[STUB]** Returns dict with platform-appropriate mock metrics (e.g., `impressions`, `likes`, `comments`, `shares` for LinkedIn). |
| `calculate_performance_score(platform, metrics)` | Weighted score 0–100 based on platform's primary engagement metric (impressions × engagement rate). |

---

### `app/agents/analytics/db_writer.py`

Stores analytics results and updates the platform style guide.

| Symbol | Description |
|---|---|
| `write_analytics(supabase, post_id, platform, period, metrics, performance_score)` | INSERT into `content_analytics`. Returns UUID or `None`. |
| `update_style_guide(supabase, platform, performance_score)` | At the 7-day mark: reads recent analytics for the platform, derives top angles and format preferences, upserts the `style_guide` row for that platform. |

---

### `app/agents/embedding/client.py`

Embedding client factory. All embeddings are 768-dimensional (matches `vector(768)` in the Supabase schema).

| Symbol | Description |
|---|---|
| `EMBEDDING_DIMENSIONS = 768` | Shared constant — must match the DB vector column size. |
| `EmbedClient` | Abstract base class. `embed(texts, for_query=False)` → `list[list[float]]`. `embed_one(text)` → `list[float]`. |
| `GeminiEmbedder` | Uses `google-genai` SDK with `text-embedding-004`. Free tier: 1500 req/day. Batches up to 100 texts. On failure per-chunk: returns empty sub-lists and logs warning. |
| `LocalEmbedder` | Uses `fastembed` with `BAAI/bge-base-en-v1.5` (768-dim, ~430 MB, downloaded once to `~/.cache/fastembed/`). Module-level singleton — loaded once per worker process. For query mode, prepends the BGE query prefix. |
| `FallbackEmbedder` | Tries primary; if it returns all-empty vectors, logs warning and falls back to secondary. |
| `NoOpEmbedder` | Returns all-empty vectors. Used when neither Gemini nor fastembed is available. Pipeline degrades gracefully (brand context, coverage checks, KB retrieval all disabled). |
| `make_embed_client(google_api_key=None, local_model=...)` | Factory: returns `FallbackEmbedder(Gemini, Local)` if Google key is set and fastembed is installed; `LocalEmbedder` if no key; `NoOpEmbedder` if fastembed not installed. |

---

### `app/agents/orchestrator/agent.py`

Builds the LangGraph ReAct agent that serves as the conversational interface for the entire pipeline.

| Symbol | Description |
|---|---|
| `_SYSTEM_PROMPT` | System prompt for the orchestrator: defines pipeline structure, all tool capabilities (trigger, approve/reject, generate, manage), and behavioural rules (single vs bulk confirmation, tone, prompt injection guard). |
| `build_orchestrator_agent(supabase, arq_pool, anthropic_api_key, model, tavily_api_key)` | Returns a compiled LangGraph graph using `create_react_agent` with `MemorySaver` checkpointer. Thread-safe — call once at startup, pass `thread_id` in config for each conversation session. |

---

### `app/agents/orchestrator/tools.py`

30+ LangChain `@tool` functions available to the orchestrator agent. All defined as closures capturing `supabase`, `arq_pool`, `anthropic_api_key`.

| Tool Group | Tools |
|---|---|
| **Pipeline control** | `trigger_research`, `trigger_scoring`, `send_ideas_to_creation`, `trigger_creation` (legacy alias) |
| **Gate 1 — Ideas** | `get_ideas(status, platform, limit)`, `approve_idea(idea_id, edited_angle?)`, `reject_idea(idea_id)`, `bulk_reject_ideas(idea_ids[])` |
| **Gate 2 — Drafts** | `get_drafts(status, platform, limit)`, `approve_draft(draft_id, scheduled_at?)`, `reject_draft(draft_id)` |
| **Brand & audience** | `add_brand_memory(content, platform)` — embeds on insert, `list_brand_memory(platform?, limit)`, `list_subscribers(limit)`, `add_email_subscriber(email, name?)`, `remove_email_subscriber(email)` |
| **Content browsing** | `get_recent_articles(limit, source_name?)`, `get_decision_summaries(limit)`, `get_published_posts(platform, limit)` |
| **Analytics** | `get_analytics_summary()`, `get_run_logs(limit)`, `get_topic_performance()` |
| **Knowledge base** | `list_kb_files()` |
| **Curated sites** | `add_curated_site(site_name, section_url, threshold?)`, `remove_curated_site(section_url)`, `list_curated_sites()` |
| **Browser auth** | `login_to_site(url)` — opens visible Edge browser for manual login; saves session |
| **On-demand generation** | `search_web(query, max_results?)`, `search_and_scrape(query, max_results?)`, `generate_post(topic, platform?, content_type?)`, `save_draft(content, platform)` |

---

### `app/agents/orchestrator/kb_ingester.py`

Ingests documents into the knowledge base for RAG-grounded content generation.

| Symbol | Description |
|---|---|
| `extract_text(filename, content_bytes)` | Detect file type by extension. For PDF: use `pdfplumber` to extract text from all pages. For TXT: decode UTF-8. Returns plain string. |
| `ingest_file(supabase, filename, text, embed_client)` | Split text into ~500-word chunks with 50-word overlap. Embed each chunk. Insert into `knowledge_base` table with `source_file`, `chunk_index`, `content`, `embedding`. Returns total chunks ingested. |

---

### `app/utils/logging.py`

Structured logging for agent decision tracing.

| Symbol | Description |
|---|---|
| `get_logger(name)` | Returns a Python logger with format: `%(asctime)s | %(name)s | %(levelname)s | %(message)s`. |
| `log_agent_decision(logger, decision, reasoning, context)` | Logs a JSON entry `{"ts": ..., "decision": ..., "reasoning": ..., "context": {...}}` at INFO level and returns it as a string. Callers accumulate these strings into `run_logs.reasoning_trace`. |
| `format_token_cost(input_tokens, output_tokens, model)` | Calculates API cost at published rates: Sonnet $3.00/$15.00 per M tokens input/output, Haiku $0.25/$1.25 per M. Returns dict with `input_tokens`, `output_tokens`, `model`, `estimated_usd`. |

---

### `app/utils/slack.py`

Optional Slack alert helper for cost and pipeline events.

| Symbol | Description |
|---|---|
| `send_slack_alert(webhook_url, message)` | POST `message` as text to Slack incoming webhook URL. Returns `True` on HTTP 200. Returns `False` (never raises) on any error. No-op if `webhook_url` is `None`. |

---

## Database Schema

| Table | Purpose |
|---|---|
| `curated_sites` | News sources: section URLs, health tracking, per-site pre-score threshold |
| `raw_content` | Scraped articles: full text, structured summary, pre-score, processed flag |
| `ideas` | AI-generated content ideas awaiting Gate 1 human approval |
| `drafts` | AI-generated post drafts awaiting Gate 2 human approval |
| `published_posts` | Posts that have been published (or stub-published) to platforms |
| `content_analytics` | Engagement metrics per published post at 24h / 72h / 7d |
| `style_guide` | Per-platform style preferences derived from analytics at 7-day mark |
| `brand_memory` | Past Growthvine posts used as style reference — 768-dim vectors for similarity search |
| `knowledge_base` | Ingested document chunks for RAG — 768-dim vectors |
| `user_decision_summaries` | Rejection pattern summaries fed back to scoring agent |
| `topic_performance_model` | Topic category performance scores |
| `email_subscribers` | Newsletter subscriber list |
| `run_logs` | Execution history per agent run with reasoning trace and token cost |
| `cost_log` | Daily token cost per agent |

### Postgres RPC Functions

These must exist in Supabase (run `003_embedding_768.sql` if missing):

| Function | Called By | Description |
|---|---|---|
| `match_brand_memory(query_embedding, match_count, platform_filter, min_similarity)` | `brand_context.py` | Top-N cosine similarity search on `brand_memory` filtered by platform. |
| `check_recent_brand_coverage(topic_embedding, platform_filter, similarity_threshold, days_back)` | `coverage_checker.py` | Returns `true` if similar brand post exists within `days_back`. |
| `match_knowledge_base(query_embedding, match_count)` | `tasks.py` (creation) | Top-N cosine similarity search on `knowledge_base` for KB-driven generation. |

---

## Environment Variables

```env
# backend/.env

# Required
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
ANTHROPIC_API_KEY=sk-ant-...
REDIS_URL=redis://localhost:6379

# Optional — embeddings (falls back to local BAAI/bge-base-en-v1.5)
GOOGLE_API_KEY=AIza...

# Optional — web search (falls back to DuckDuckGo)
TAVILY_API_KEY=tvly-...

# Optional — alerts
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
DAILY_COST_ALERT_USD=5.0

# Optional — API key auth (leave unset in dev)
API_KEY=your-secret-key

# Models
CLAUDE_MODEL_HEAVY=claude-sonnet-4-5
CLAUDE_MODEL_LIGHT=claude-haiku-4-5

# Research agent
ARTICLE_MIN_WORDS=400
ARTICLE_MAX_AGE_DAYS=7
ARTICLES_PER_SITE=5
DEFAULT_PRE_SCORE_THRESHOLD=4.0

# Scoring
MAX_IDEAS_PER_SITE=5
REJECTION_BATCH_SIZE=5
```

```env
# frontend/.env.local
BACKEND_URL=http://127.0.0.1:8000
BACKEND_API_KEY=your-secret-key   # must match API_KEY in backend/.env
```

---

## Running Locally

```bash
# 1. Start Redis
redis-server
docker run -d --name redis -p 6379:6379 redis:alpine
# 2. Start backend API (terminal 1)
cd backend
python -m uvicorn app.api.main:app --reload --port 8000

# 3. Start arq worker (terminal 2)
cd backend
python -m arq app.queue.worker.WorkerSettings

# 4. Start frontend (terminal 3)
cd frontend
npm install
npm run dev   # http://localhost:3000
```

> The arq worker **must** be running for any pipeline job to execute. Without it, triggered jobs queue in Redis and never complete.

---

## What's Stubbed (Not Yet Implemented)

| Feature | File | Status |
|---|---|---|
| LinkedIn posting | `publishing/poster.py:post_linkedin` | Returns fake ID — needs LinkedIn API credentials |
| Twitter posting | `publishing/poster.py:post_twitter` | Returns fake ID — needs Twitter API v2 credentials |
| Blog posting | `publishing/poster.py:post_blog` | Returns fake ID — needs CMS / WordPress API |
| Email sending | `publishing/poster.py:post_email` | Returns fake ID — needs SendGrid / Mailchimp |
| Analytics metrics | `analytics/metrics_fetcher.py` | Returns random mock data — needs platform analytics APIs |

---

## Cost Reference

Typical per-run costs (8 active sites, 5 articles per site):

| Step | Model | Approx cost |
|---|---|---|
| Pre-score headlines (8 calls) | Claude Haiku | ~$0.001 |
| Summarise articles (40 calls) | Claude Sonnet | ~$0.05–0.15 |
| Generate ideas (40 calls) | Claude Sonnet | ~$0.05–0.10 |
| Generate drafts (per approved idea) | Claude Sonnet | ~$0.03–0.05 each |

Set `DAILY_COST_ALERT_USD` to receive a Slack alert if a single run exceeds the threshold.
