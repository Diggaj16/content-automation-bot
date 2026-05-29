# Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the monorepo, create all 15 database tables with pgvector in Supabase, define all Pydantic models, wire the arq job queue skeleton, and seed initial curated sites plus brand voice data.

**Architecture:** Monorepo with `backend/` (FastAPI + agents + arq workers) and `frontend/` (Next.js, empty for now). All DB operations go through a singleton Supabase client (supabase-py sync). arq handles all scheduled and event-driven tasks via local Redis. Vector similarity search uses Postgres functions called via supabase.rpc().

**Tech Stack:** Python 3.11, supabase-py 2.x, pydantic 2.x + pydantic-settings, arq 0.26.x, redis-py 5.x, pytest + pytest-mock

---

## File Map

```
D:\Intern\content-automation-bot\
├── backend\
│   ├── app\
│   │   ├── __init__.py
│   │   ├── config.py                        # All env vars via pydantic-settings
│   │   ├── db\
│   │   │   ├── __init__.py
│   │   │   ├── client.py                    # Supabase client singleton
│   │   │   ├── models.py                    # Pydantic models for every table
│   │   │   └── migrations\
│   │   │       └── 001_initial.sql          # All CREATE TABLE + indexes + pg functions
│   │   ├── queue\
│   │   │   ├── __init__.py
│   │   │   ├── worker.py                    # arq WorkerSettings + cron schedule
│   │   │   └── tasks.py                     # Stub task functions (one per agent)
│   │   └── utils\
│   │       ├── __init__.py
│   │       └── logging.py                   # Structured logging helper
│   ├── scripts\
│   │   └── seed.py                          # Seeds curated_sites + brand_memory
│   ├── tests\
│   │   ├── __init__.py
│   │   ├── conftest.py                      # pytest fixtures + markers
│   │   ├── test_config.py
│   │   ├── test_db_client.py
│   │   └── test_models.py
│   ├── pyproject.toml
│   ├── .env.example
│   └── .env                                 # Real credentials — NEVER commit this
├── frontend\                                # Empty — filled in Plan 6
├── docs\
│   └── superpowers\
│       └── plans\
│           └── 2026-05-29-foundation.md     # This file
└── .gitignore
```

---

### Task 1: Root scaffold + .gitignore

**Files:**
- Create: `D:\Intern\content-automation-bot\.gitignore`
- Create: All `__init__.py` stubs and empty directories listed in the file map

- [ ] **Step 1: Create directory tree**

```powershell
cd D:\Intern\content-automation-bot

New-Item -ItemType Directory -Force backend\app\db\migrations
New-Item -ItemType Directory -Force backend\app\queue
New-Item -ItemType Directory -Force backend\app\utils
New-Item -ItemType Directory -Force backend\scripts
New-Item -ItemType Directory -Force backend\tests
New-Item -ItemType Directory -Force frontend
```

- [ ] **Step 2: Create all `__init__.py` files**

```powershell
"" | Out-File -Encoding utf8 backend\app\__init__.py
"" | Out-File -Encoding utf8 backend\app\db\__init__.py
"" | Out-File -Encoding utf8 backend\app\queue\__init__.py
"" | Out-File -Encoding utf8 backend\app\utils\__init__.py
"" | Out-File -Encoding utf8 backend\tests\__init__.py
```

- [ ] **Step 3: Write `.gitignore`**

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/
.venv/
venv/
env/

# Env files — NEVER commit real credentials
backend/.env
.env

# Test + coverage
.pytest_cache/
.coverage
htmlcov/

# Node / Next.js
frontend/node_modules/
frontend/.next/
frontend/.env.local

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
```

- [ ] **Step 4: Commit**

```bash
cd D:/Intern/content-automation-bot
git init
git add .gitignore docs/
git commit -m "chore: initialise repo with gitignore and plan docs"
```

---

### Task 2: pyproject.toml + install dependencies

**Files:**
- Create: `D:\Intern\content-automation-bot\backend\pyproject.toml`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=65", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "content-automation-backend"
version = "0.1.0"
description = "Indian finance content automation backend"
requires-python = ">=3.11"
dependencies = [
    "supabase>=2.3.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "arq>=0.26.1",
    "redis>=5.0.0",
    "anthropic>=0.40.0",
    "voyageai>=0.3.0",
    "python-dotenv>=1.0.0",
    "httpx>=0.26.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.12.0",
]
local-embeddings = [
    "sentence-transformers>=2.7.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.setuptools.packages.find]
where = ["."]
include = ["app*"]
```

- [ ] **Step 2: Create and activate a virtual environment**

```powershell
cd D:\Intern\content-automation-bot\backend
python -m venv .venv
.venv\Scripts\Activate.ps1
```

- [ ] **Step 3: Install dependencies**

```powershell
pip install -e ".[dev]"
```

- [ ] **Step 4: Verify install**

```powershell
python -c "import supabase, pydantic, arq, redis, anthropic; print('All core deps OK')"
```

Expected output:
```
All core deps OK
```

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml
git commit -m "chore: add backend pyproject.toml with all dependencies"
```

---

### Task 3: Configuration management

**Files:**
- Create: `D:\Intern\content-automation-bot\backend\.env.example`
- Create: `D:\Intern\content-automation-bot\backend\.env`  (real values — already gitignored)
- Create: `D:\Intern\content-automation-bot\backend\app\config.py`
- Create: `D:\Intern\content-automation-bot\backend\tests\test_config.py`

- [ ] **Step 1: Write `.env.example`**

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here

# Anthropic
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# Voyage AI (for embeddings — fallback to local all-MiniLM-L6-v2 if not set)
VOYAGE_API_KEY=

# Redis (local)
REDIS_URL=redis://localhost:6379

# Slack (optional — for alerts)
SLACK_WEBHOOK_URL=

# Cost alerts
DAILY_COST_ALERT_USD=5.0

# Models
CLAUDE_MODEL_HEAVY=claude-sonnet-4-5
CLAUDE_MODEL_LIGHT=claude-haiku-4-5

# Research agent
ARTICLE_MIN_WORDS=400
ARTICLE_MAX_AGE_DAYS=7
DEFAULT_PRE_SCORE_THRESHOLD=4.0

# Site health
SITE_FAILURE_PAUSE_THRESHOLD=5
```

- [ ] **Step 2: Create your real `.env` file**

Copy `.env.example` to `.env` and fill in:
- `SUPABASE_URL=https://nenvkgxpvygxskrrvkyc.supabase.co`
- `SUPABASE_SERVICE_ROLE_KEY=` (the service role JWT from Supabase dashboard)
- `ANTHROPIC_API_KEY=` (your key)
- Leave `VOYAGE_API_KEY` blank for now — the embedding plan will add it

- [ ] **Step 3: Write `app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Supabase
    supabase_url: str = Field(..., alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(..., alias="SUPABASE_SERVICE_ROLE_KEY")

    # Anthropic
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")

    # Voyage AI
    voyage_api_key: Optional[str] = Field(None, alias="VOYAGE_API_KEY")

    # Redis
    redis_url: str = Field("redis://localhost:6379", alias="REDIS_URL")

    # Slack
    slack_webhook_url: Optional[str] = Field(None, alias="SLACK_WEBHOOK_URL")

    # Cost alerts
    daily_cost_alert_usd: float = Field(5.0, alias="DAILY_COST_ALERT_USD")

    # Models
    claude_model_heavy: str = Field("claude-sonnet-4-5", alias="CLAUDE_MODEL_HEAVY")
    claude_model_light: str = Field("claude-haiku-4-5", alias="CLAUDE_MODEL_LIGHT")

    # Research agent
    article_min_words: int = Field(400, alias="ARTICLE_MIN_WORDS")
    article_max_age_days: int = Field(7, alias="ARTICLE_MAX_AGE_DAYS")
    default_pre_score_threshold: float = Field(4.0, alias="DEFAULT_PRE_SCORE_THRESHOLD")

    # Site health
    site_failure_pause_threshold: int = Field(5, alias="SITE_FAILURE_PAUSE_THRESHOLD")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Write `tests/test_config.py`**

```python
import pytest
import os


def test_settings_load():
    from app.config import get_settings
    settings = get_settings()
    assert settings.supabase_url.startswith("https://")
    assert len(settings.supabase_service_role_key) > 50
    assert settings.redis_url == "redis://localhost:6379"
    assert settings.article_min_words == 400
    assert settings.article_max_age_days == 7
    assert settings.default_pre_score_threshold == 4.0
    assert settings.site_failure_pause_threshold == 5
    assert settings.claude_model_heavy == "claude-sonnet-4-5"
    assert settings.claude_model_light == "claude-haiku-4-5"


def test_settings_is_cached():
    from app.config import get_settings
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_voyage_api_key_optional():
    from app.config import get_settings
    settings = get_settings()
    # OK to be None — embedding plan handles fallback
    assert settings.voyage_api_key is None or isinstance(settings.voyage_api_key, str)
```

- [ ] **Step 5: Run tests**

```powershell
cd D:\Intern\content-automation-bot\backend
pytest tests/test_config.py -v
```

Expected output:
```
tests/test_config.py::test_settings_load PASSED
tests/test_config.py::test_settings_is_cached PASSED
tests/test_config.py::test_voyage_api_key_optional PASSED
3 passed
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/.env.example backend/tests/test_config.py
git commit -m "feat: add configuration management with pydantic-settings"
```

---

### Task 4: Supabase client singleton

**Files:**
- Create: `D:\Intern\content-automation-bot\backend\app\db\client.py`
- Create: `D:\Intern\content-automation-bot\backend\tests\test_db_client.py`

- [ ] **Step 1: Write `app/db/client.py`**

```python
from supabase import create_client, Client
from app.config import get_settings
from typing import Optional

_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Returns a singleton Supabase client using the service role key.
    Service role bypasses Row Level Security — correct for backend agents.
    """
    global _client
    if _client is None:
        settings = get_settings()
        _client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
    return _client


def reset_client() -> None:
    """Force a new client on next call. Used in tests."""
    global _client
    _client = None
```

- [ ] **Step 2: Write `tests/test_db_client.py`**

```python
import pytest


def test_client_is_singleton(mocker):
    """get_supabase_client returns the same instance on repeated calls."""
    from app.db import client as client_module
    client_module.reset_client()

    mock_create = mocker.patch("app.db.client.create_client")
    mock_create.return_value = object()  # unique object

    from app.db.client import get_supabase_client
    c1 = get_supabase_client()
    c2 = get_supabase_client()

    assert c1 is c2
    assert mock_create.call_count == 1  # create_client called exactly once

    client_module.reset_client()


def test_client_uses_service_role_key(mocker):
    """Client is created with the service role key, not the anon key."""
    from app.db import client as client_module
    client_module.reset_client()

    mock_create = mocker.patch("app.db.client.create_client")
    mock_create.return_value = object()

    from app.db.client import get_supabase_client
    get_supabase_client()

    call_kwargs = mock_create.call_args
    # Second argument is the key
    key_used = call_kwargs[0][1]
    assert len(key_used) > 50  # service role JWTs are long
    assert key_used != "anon"

    client_module.reset_client()


@pytest.mark.integration
def test_client_can_query_supabase():
    """Real connection smoke test — requires .env with valid credentials."""
    from app.db import client as client_module
    client_module.reset_client()

    from app.db.client import get_supabase_client
    db = get_supabase_client()

    # curated_sites table must exist after migration
    result = db.table("curated_sites").select("id").limit(1).execute()
    assert result is not None
    assert hasattr(result, "data")

    client_module.reset_client()
```

- [ ] **Step 3: Run unit tests (no real DB needed)**

```powershell
cd D:\Intern\content-automation-bot\backend
pytest tests/test_db_client.py -v -m "not integration"
```

Expected output:
```
tests/test_db_client.py::test_client_is_singleton PASSED
tests/test_db_client.py::test_client_uses_service_role_key PASSED
2 passed
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/client.py backend/tests/test_db_client.py
git commit -m "feat: add Supabase client singleton"
```

---

### Task 5: Database migration SQL

**Files:**
- Create: `D:\Intern\content-automation-bot\backend\app\db\migrations\001_initial.sql`

- [ ] **Step 1: Write `001_initial.sql`**

```sql
-- ============================================================
-- 001_initial.sql
-- Run once in Supabase SQL Editor (Dashboard → SQL Editor → New Query)
-- ============================================================

-- Enable pgvector extension (required for brand_memory and knowledge_base)
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS curated_sites (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_name             TEXT NOT NULL,
    section_url           TEXT NOT NULL UNIQUE,
    active                BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at           TIMESTAMPTZ,
    consecutive_failures  INTEGER NOT NULL DEFAULT 0,
    pre_score_threshold   FLOAT NOT NULL DEFAULT 4.0,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw_content (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url                   TEXT NOT NULL,
    normalized_url        TEXT NOT NULL UNIQUE,
    title                 TEXT NOT NULL,
    source_name           TEXT NOT NULL,
    publication_date      TIMESTAMPTZ,
    fetch_date            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    full_text             TEXT NOT NULL,
    structured_summary    JSONB,          -- StructuredSummary shape
    word_count            INTEGER NOT NULL DEFAULT 0,
    pre_score             FLOAT,
    vision_fallback_used  BOOLEAN NOT NULL DEFAULT FALSE,
    paywall_detected      BOOLEAN NOT NULL DEFAULT FALSE,
    processed             BOOLEAN NOT NULL DEFAULT FALSE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ideas (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform              TEXT NOT NULL
                              CHECK (platform IN ('linkedin','twitter','blog','email')),
    angle                 TEXT NOT NULL,
    edited_angle          TEXT,
    source_article_id     UUID REFERENCES raw_content(id) ON DELETE SET NULL,
    agent_reasoning       TEXT NOT NULL,
    source_article_date   TIMESTAMPTZ,
    approval_status       TEXT NOT NULL DEFAULT 'pending_approval'
                              CHECK (approval_status IN
                                     ('pending_approval','approved','rejected')),
    score                 FLOAT,
    recent_coverage_flag  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_decision_summaries (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    summary_text     TEXT NOT NULL,
    rejection_count  INTEGER NOT NULL DEFAULT 1,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS drafts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform                TEXT NOT NULL
                                CHECK (platform IN ('linkedin','twitter','blog','email')),
    content_text            TEXT NOT NULL,
    agent_reasoning         TEXT NOT NULL,
    source_idea_id          UUID REFERENCES ideas(id) ON DELETE SET NULL,
    finance_flags           JSONB NOT NULL DEFAULT '[]',
    suggested_publish_time  TIMESTAMPTZ,
    scheduled_at            TIMESTAMPTZ,
    approval_status         TEXT NOT NULL DEFAULT 'pending_approval'
                                CHECK (approval_status IN
                                       ('pending_approval','approved','rejected',
                                        'published','failed')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS published_posts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform         TEXT NOT NULL,
    post_identifier  TEXT NOT NULL,
    published_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    draft_id         UUID REFERENCES drafts(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS content_analytics (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id            UUID REFERENCES published_posts(id) ON DELETE CASCADE,
    platform           TEXT NOT NULL,
    measurement_period TEXT NOT NULL
                           CHECK (measurement_period IN ('24h','72h','7d')),
    metrics            JSONB NOT NULL DEFAULT '{}',
    performance_score  FLOAT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (post_id, measurement_period)
);

CREATE TABLE IF NOT EXISTS email_subscribers (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email            TEXT NOT NULL UNIQUE,
    name             TEXT,
    subscribed_date  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source           TEXT NOT NULL DEFAULT 'manual'
                         CHECK (source IN ('manual','website_form')),
    active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS style_guide (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform    TEXT NOT NULL UNIQUE
                    CHECK (platform IN ('linkedin','twitter','blog','email','general')),
    insights    JSONB NOT NULL DEFAULT '{}',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS topic_performance_model (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_category    TEXT NOT NULL UNIQUE,
    performance_score FLOAT NOT NULL DEFAULT 0.5,
    sample_count      INTEGER NOT NULL DEFAULT 0,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Vector store: every published post embedded for RAG
CREATE TABLE IF NOT EXISTS brand_memory (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content             TEXT NOT NULL,
    platform            TEXT NOT NULL
                            CHECK (platform IN ('linkedin','twitter','blog','email')),
    published_at        TIMESTAMPTZ,
    performance_metrics JSONB NOT NULL DEFAULT '{}',
    embedding           vector(1024),   -- voyage-3 dimension
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Vector store: uploaded PDFs and TXT files, chunked
CREATE TABLE IF NOT EXISTS knowledge_base (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_file  TEXT NOT NULL,
    chunk_index  INTEGER NOT NULL,
    content      TEXT NOT NULL,
    embedding    vector(1024),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_file, chunk_index)
);

CREATE TABLE IF NOT EXISTS run_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name      TEXT NOT NULL,
    trigger_type    TEXT NOT NULL
                        CHECK (trigger_type IN
                               ('cron','event','manual','orchestrator')),
    processed_count INTEGER NOT NULL DEFAULT 0,
    success_count   INTEGER NOT NULL DEFAULT 0,
    failure_count   INTEGER NOT NULL DEFAULT 0,
    duration_seconds FLOAT,
    reasoning_trace TEXT,
    errors          JSONB NOT NULL DEFAULT '[]',
    token_cost      JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS site_health_log (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id        UUID REFERENCES curated_sites(id) ON DELETE CASCADE,
    success        BOOLEAN NOT NULL,
    error_message  TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cost_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name          TEXT NOT NULL,
    date                DATE NOT NULL DEFAULT CURRENT_DATE,
    token_count         INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd  FLOAT NOT NULL DEFAULT 0.0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (agent_name, date)
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_raw_content_normalized_url
    ON raw_content(normalized_url);
CREATE INDEX IF NOT EXISTS idx_raw_content_unprocessed
    ON raw_content(processed) WHERE processed = FALSE;
CREATE INDEX IF NOT EXISTS idx_raw_content_fetch_date
    ON raw_content(fetch_date DESC);

CREATE INDEX IF NOT EXISTS idx_ideas_approval_status
    ON ideas(approval_status);
CREATE INDEX IF NOT EXISTS idx_ideas_created_at
    ON ideas(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_drafts_due
    ON drafts(scheduled_at)
    WHERE approval_status = 'approved';

CREATE INDEX IF NOT EXISTS idx_published_posts_draft_id
    ON published_posts(draft_id);

CREATE INDEX IF NOT EXISTS idx_content_analytics_post_id
    ON content_analytics(post_id);

CREATE INDEX IF NOT EXISTS idx_brand_memory_platform
    ON brand_memory(platform);
CREATE INDEX IF NOT EXISTS idx_brand_memory_published_at
    ON brand_memory(published_at DESC);

CREATE INDEX IF NOT EXISTS idx_run_logs_agent_created
    ON run_logs(agent_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_site_health_site_created
    ON site_health_log(site_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_cost_log_date
    ON cost_log(date DESC);

-- HNSW vector indexes (works with any row count, better recall than IVFFlat)
CREATE INDEX IF NOT EXISTS idx_brand_memory_embedding
    ON brand_memory USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_knowledge_base_embedding
    ON knowledge_base USING hnsw (embedding vector_cosine_ops);

-- ============================================================
-- UPDATED_AT TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_curated_sites_updated_at
    BEFORE UPDATE ON curated_sites
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_ideas_updated_at
    BEFORE UPDATE ON ideas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_drafts_updated_at
    BEFORE UPDATE ON drafts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- VECTOR SIMILARITY SEARCH FUNCTIONS
-- Called via supabase.rpc() from Python
-- ============================================================

-- Find top-k similar past posts for few-shot examples
CREATE OR REPLACE FUNCTION match_brand_memory(
    query_embedding  vector(1024),
    match_count      INT     DEFAULT 5,
    filter_platform  TEXT    DEFAULT NULL,
    days_back        INT     DEFAULT NULL
)
RETURNS TABLE (
    id                  UUID,
    content             TEXT,
    platform            TEXT,
    published_at        TIMESTAMPTZ,
    performance_metrics JSONB,
    similarity          FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        bm.id,
        bm.content,
        bm.platform,
        bm.published_at,
        bm.performance_metrics,
        1 - (bm.embedding <=> query_embedding) AS similarity
    FROM brand_memory bm
    WHERE
        bm.embedding IS NOT NULL
        AND (filter_platform IS NULL OR bm.platform = filter_platform)
        AND (days_back IS NULL
             OR bm.published_at >= NOW() - (days_back || ' days')::INTERVAL)
    ORDER BY bm.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Check if we've covered a similar angle recently (30-day overlap check)
CREATE OR REPLACE FUNCTION check_recent_brand_coverage(
    topic_embedding  vector(1024),
    platform_filter  TEXT,
    days_back        INT DEFAULT 30,
    similarity_threshold FLOAT DEFAULT 0.85
)
RETURNS TABLE (
    id          UUID,
    content     TEXT,
    similarity  FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        bm.id,
        bm.content,
        1 - (bm.embedding <=> topic_embedding) AS similarity
    FROM brand_memory bm
    WHERE
        bm.embedding IS NOT NULL
        AND bm.platform = platform_filter
        AND bm.published_at >= NOW() - (days_back || ' days')::INTERVAL
        AND 1 - (bm.embedding <=> topic_embedding) >= similarity_threshold
    ORDER BY bm.embedding <=> topic_embedding
    LIMIT 3;
END;
$$;

-- Retrieve relevant knowledge base chunks for content enrichment
CREATE OR REPLACE FUNCTION match_knowledge_base(
    query_embedding  vector(1024),
    match_count      INT DEFAULT 8
)
RETURNS TABLE (
    id           UUID,
    source_file  TEXT,
    chunk_index  INT,
    content      TEXT,
    similarity   FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        kb.id,
        kb.source_file,
        kb.chunk_index,
        kb.content,
        1 - (kb.embedding <=> query_embedding) AS similarity
    FROM knowledge_base kb
    WHERE kb.embedding IS NOT NULL
    ORDER BY kb.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
```

- [ ] **Step 2: Apply the migration in Supabase**

1. Open https://supabase.com/dashboard/project/nenvkgxpvygxskrrvkyc
2. Click **SQL Editor** in the left sidebar
3. Click **New query**
4. Paste the entire contents of `001_initial.sql`
5. Click **Run** (or Ctrl+Enter)

Expected: `Success. No rows returned.`

- [ ] **Step 3: Verify tables exist**

In the same SQL Editor, run:
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

Expected — you should see all 15 table names:
```
brand_memory
content_analytics
cost_log
curated_sites
drafts
email_subscribers
ideas
knowledge_base
published_posts
raw_content
run_logs
site_health_log
style_guide
topic_performance_model
user_decision_summaries
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/migrations/001_initial.sql
git commit -m "feat: add initial DB migration with all 15 tables and pgvector"
```

---

### Task 6: Pydantic models for all tables

**Files:**
- Create: `D:\Intern\content-automation-bot\backend\app\db\models.py`
- Create: `D:\Intern\content-automation-bot\backend\tests\test_models.py`

- [ ] **Step 1: Write `app/db/models.py`**

```python
"""
Pydantic models for every database table.

Convention:
  - `<Table>`       — full DB row (includes id, created_at, DB-generated fields)
  - `<Table>Create` — data required to INSERT a new row
  - `<Table>Update` — optional fields for partial updates (where needed)
"""
from __future__ import annotations

from datetime import datetime, date
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field
from enum import Enum


# ──────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────

class Platform(str, Enum):
    LINKEDIN = "linkedin"
    TWITTER  = "twitter"
    BLOG     = "blog"
    EMAIL    = "email"


class ApprovalStatus(str, Enum):
    PENDING  = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class DraftStatus(str, Enum):
    PENDING   = "pending_approval"
    APPROVED  = "approved"
    REJECTED  = "rejected"
    PUBLISHED = "published"
    FAILED    = "failed"


class TriggerType(str, Enum):
    CRON         = "cron"
    EVENT        = "event"
    MANUAL       = "manual"
    ORCHESTRATOR = "orchestrator"


class MeasurementPeriod(str, Enum):
    H24 = "24h"
    H72 = "72h"
    D7  = "7d"


class SubscriberSource(str, Enum):
    MANUAL       = "manual"
    WEBSITE_FORM = "website_form"


# ──────────────────────────────────────────────────────────────
# curated_sites
# ──────────────────────────────────────────────────────────────

class CuratedSite(BaseModel):
    id:                   UUID
    site_name:            str
    section_url:          str
    active:               bool
    last_run_at:          Optional[datetime]
    consecutive_failures: int
    pre_score_threshold:  float
    created_at:           datetime
    updated_at:           datetime


class CuratedSiteCreate(BaseModel):
    site_name:           str
    section_url:         str
    active:              bool  = True
    pre_score_threshold: float = 4.0


class CuratedSiteUpdate(BaseModel):
    active:               Optional[bool]     = None
    last_run_at:          Optional[datetime] = None
    consecutive_failures: Optional[int]      = None
    pre_score_threshold:  Optional[float]    = None


# ──────────────────────────────────────────────────────────────
# raw_content
# ──────────────────────────────────────────────────────────────

class StructuredSummary(BaseModel):
    """Five-section summary written by the research agent."""
    story_narrative: str            # 2-3 sentence hook
    key_data_points: list[str]      # specific numbers, dates, names
    mechanism:       str            # underlying cause
    implications:    str            # what this means for the audience
    content_angles:  list[str]      # 2-3 rough angles worth pursuing


class RawContent(BaseModel):
    id:                   UUID
    url:                  str
    normalized_url:       str
    title:                str
    source_name:          str
    publication_date:     Optional[datetime]
    fetch_date:           datetime
    full_text:            str
    structured_summary:   Optional[StructuredSummary]
    word_count:           int
    pre_score:            Optional[float]
    vision_fallback_used: bool
    paywall_detected:     bool
    processed:            bool
    created_at:           datetime


class RawContentCreate(BaseModel):
    url:                  str
    normalized_url:       str
    title:                str
    source_name:          str
    publication_date:     Optional[datetime]       = None
    full_text:            str
    structured_summary:   Optional[StructuredSummary] = None
    word_count:           int                      = 0
    pre_score:            Optional[float]          = None
    vision_fallback_used: bool                     = False
    paywall_detected:     bool                     = False


# ──────────────────────────────────────────────────────────────
# ideas
# ──────────────────────────────────────────────────────────────

class Idea(BaseModel):
    id:                   UUID
    platform:             Platform
    angle:                str
    edited_angle:         Optional[str]
    source_article_id:    Optional[UUID]
    agent_reasoning:      str
    source_article_date:  Optional[datetime]
    approval_status:      ApprovalStatus
    score:                Optional[float]
    recent_coverage_flag: bool
    created_at:           datetime
    updated_at:           datetime


class IdeaCreate(BaseModel):
    platform:             Platform
    angle:                str
    source_article_id:    Optional[UUID]     = None
    agent_reasoning:      str
    source_article_date:  Optional[datetime] = None
    score:                Optional[float]    = None
    recent_coverage_flag: bool               = False


class IdeaApproval(BaseModel):
    """Payload from the human at Gate 1."""
    approval_status: ApprovalStatus
    edited_angle:    Optional[str] = None  # human's rewrite, if any


# ──────────────────────────────────────────────────────────────
# user_decision_summaries
# ──────────────────────────────────────────────────────────────

class UserDecisionSummary(BaseModel):
    id:              UUID
    summary_text:    str
    rejection_count: int
    created_at:      datetime


class UserDecisionSummaryCreate(BaseModel):
    summary_text:    str
    rejection_count: int = 1


# ──────────────────────────────────────────────────────────────
# drafts
# ──────────────────────────────────────────────────────────────

class FinanceFlag(BaseModel):
    """A single flagged item within a draft."""
    flag_type: str   # "company_name" | "financial_figure" | "regulatory_claim" | "investment_advice"
    content:   str   # the flagged text
    context:   str   # surrounding sentence for human review


class Draft(BaseModel):
    id:                     UUID
    platform:               Platform
    content_text:           str
    agent_reasoning:        str
    source_idea_id:         Optional[UUID]
    finance_flags:          list[FinanceFlag]
    suggested_publish_time: Optional[datetime]
    scheduled_at:           Optional[datetime]
    approval_status:        DraftStatus
    created_at:             datetime
    updated_at:             datetime


class DraftCreate(BaseModel):
    platform:               Platform
    content_text:           str
    agent_reasoning:        str
    source_idea_id:         Optional[UUID]            = None
    finance_flags:          list[FinanceFlag]         = Field(default_factory=list)
    suggested_publish_time: Optional[datetime]        = None


class DraftApproval(BaseModel):
    """Payload from the human at Gate 2."""
    approval_status:  DraftStatus
    content_text:     Optional[str]      = None   # if human edited content
    scheduled_at:     Optional[datetime] = None   # confirm or override schedule


# ──────────────────────────────────────────────────────────────
# published_posts
# ──────────────────────────────────────────────────────────────

class PublishedPost(BaseModel):
    id:              UUID
    platform:        str
    post_identifier: str   # LinkedIn URN / tweet ID / blog URL
    published_at:    datetime
    draft_id:        Optional[UUID]
    created_at:      datetime


class PublishedPostCreate(BaseModel):
    platform:        str
    post_identifier: str
    draft_id:        Optional[UUID] = None


# ──────────────────────────────────────────────────────────────
# content_analytics
# ──────────────────────────────────────────────────────────────

class LinkedInMetrics(BaseModel):
    impressions: int   = 0
    reactions:   int   = 0
    comments:    int   = 0
    shares:      int   = 0


class TwitterMetrics(BaseModel):
    likes:       int   = 0
    retweets:    int   = 0
    impressions: int   = 0
    bookmarks:   int   = 0


class BlogMetrics(BaseModel):
    page_views:                int   = 0
    sessions:                  int   = 0
    avg_engagement_time_seconds: float = 0.0


class ContentAnalytics(BaseModel):
    id:                UUID
    post_id:           UUID
    platform:          str
    measurement_period: MeasurementPeriod
    metrics:           dict[str, Any]
    performance_score: Optional[float]
    created_at:        datetime


class ContentAnalyticsCreate(BaseModel):
    post_id:            UUID
    platform:           str
    measurement_period: MeasurementPeriod
    metrics:            dict[str, Any]
    performance_score:  Optional[float] = None


# ──────────────────────────────────────────────────────────────
# email_subscribers
# ──────────────────────────────────────────────────────────────

class EmailSubscriber(BaseModel):
    id:              UUID
    email:           str
    name:            Optional[str]
    subscribed_date: datetime
    source:          SubscriberSource
    active:          bool
    created_at:      datetime


class EmailSubscriberCreate(BaseModel):
    email:  str
    name:   Optional[str]          = None
    source: SubscriberSource       = SubscriberSource.MANUAL


# ──────────────────────────────────────────────────────────────
# style_guide
# ──────────────────────────────────────────────────────────────

class StyleGuideInsights(BaseModel):
    """Updated by analytics agent at the 7-day analytics mark."""
    optimal_length_range:     Optional[str]       = None   # e.g. "800-1200 words"
    top_performing_angles:    list[str]            = Field(default_factory=list)
    format_preferences:       list[str]            = Field(default_factory=list)
    engagement_patterns:      list[str]            = Field(default_factory=list)
    last_30_day_summary:      Optional[str]        = None


class StyleGuide(BaseModel):
    id:         UUID
    platform:   str
    insights:   StyleGuideInsights
    updated_at: datetime


# ──────────────────────────────────────────────────────────────
# topic_performance_model
# ──────────────────────────────────────────────────────────────

class TopicPerformanceModel(BaseModel):
    id:                UUID
    topic_category:    str
    performance_score: float   # 0-1 normalised
    sample_count:      int
    updated_at:        datetime


class TopicPerformanceUpsert(BaseModel):
    topic_category:    str
    performance_score: float
    sample_count:      int


# ──────────────────────────────────────────────────────────────
# brand_memory  (vector store)
# ──────────────────────────────────────────────────────────────

class BrandMemory(BaseModel):
    """DB row. embedding field excluded — it's a vector type not natively supported by Pydantic."""
    id:                  UUID
    content:             str
    platform:            Platform
    published_at:        Optional[datetime]
    performance_metrics: dict[str, Any]
    created_at:          datetime


class BrandMemoryCreate(BaseModel):
    content:             str
    platform:            Platform
    published_at:        Optional[datetime]  = None
    performance_metrics: dict[str, Any]      = Field(default_factory=dict)
    # embedding is set separately after Voyage AI call


# ──────────────────────────────────────────────────────────────
# knowledge_base  (vector store)
# ──────────────────────────────────────────────────────────────

class KnowledgeBaseChunk(BaseModel):
    id:          UUID
    source_file: str
    chunk_index: int
    content:     str
    created_at:  datetime


class KnowledgeBaseChunkCreate(BaseModel):
    source_file: str
    chunk_index: int
    content:     str
    # embedding is set separately after Voyage AI call


# ──────────────────────────────────────────────────────────────
# run_logs
# ──────────────────────────────────────────────────────────────

class RunLog(BaseModel):
    id:               UUID
    agent_name:       str
    trigger_type:     TriggerType
    processed_count:  int
    success_count:    int
    failure_count:    int
    duration_seconds: Optional[float]
    reasoning_trace:  Optional[str]
    errors:           list[dict[str, Any]]
    token_cost:       dict[str, Any]   # {"input": 1234, "output": 567, "model": "claude-sonnet-4-5"}
    created_at:       datetime


class RunLogCreate(BaseModel):
    agent_name:       str
    trigger_type:     TriggerType
    processed_count:  int                    = 0
    success_count:    int                    = 0
    failure_count:    int                    = 0
    duration_seconds: Optional[float]        = None
    reasoning_trace:  Optional[str]          = None
    errors:           list[dict[str, Any]]   = Field(default_factory=list)
    token_cost:       dict[str, Any]         = Field(default_factory=dict)


# ──────────────────────────────────────────────────────────────
# site_health_log
# ──────────────────────────────────────────────────────────────

class SiteHealthLog(BaseModel):
    id:            UUID
    site_id:       UUID
    success:       bool
    error_message: Optional[str]
    created_at:    datetime


class SiteHealthLogCreate(BaseModel):
    site_id:       UUID
    success:       bool
    error_message: Optional[str] = None


# ──────────────────────────────────────────────────────────────
# cost_log
# ──────────────────────────────────────────────────────────────

class CostLog(BaseModel):
    id:                 UUID
    agent_name:         str
    date:               date
    token_count:        int
    estimated_cost_usd: float
    created_at:         datetime


class CostLogUpsert(BaseModel):
    """Use with ON CONFLICT (agent_name, date) DO UPDATE."""
    agent_name:         str
    date:               date
    token_count:        int
    estimated_cost_usd: float
```

- [ ] **Step 2: Write `tests/test_models.py`**

```python
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.db.models import (
    Platform,
    ApprovalStatus,
    DraftStatus,
    TriggerType,
    MeasurementPeriod,
    CuratedSiteCreate,
    StructuredSummary,
    RawContentCreate,
    IdeaCreate,
    IdeaApproval,
    FinanceFlag,
    DraftCreate,
    DraftApproval,
    PublishedPostCreate,
    ContentAnalyticsCreate,
    LinkedInMetrics,
    TwitterMetrics,
    BlogMetrics,
    EmailSubscriberCreate,
    SubscriberSource,
    StyleGuideInsights,
    TopicPerformanceUpsert,
    BrandMemoryCreate,
    KnowledgeBaseChunkCreate,
    RunLogCreate,
    SiteHealthLogCreate,
    CostLogUpsert,
)
from datetime import date


# ── Enums ────────────────────────────────────────────────────

def test_platform_values():
    assert Platform.LINKEDIN == "linkedin"
    assert Platform.TWITTER  == "twitter"
    assert Platform.BLOG     == "blog"
    assert Platform.EMAIL    == "email"


def test_approval_status_values():
    assert ApprovalStatus.PENDING  == "pending_approval"
    assert ApprovalStatus.APPROVED == "approved"
    assert ApprovalStatus.REJECTED == "rejected"


def test_draft_status_includes_published_and_failed():
    assert DraftStatus.PUBLISHED == "published"
    assert DraftStatus.FAILED    == "failed"


def test_trigger_type_values():
    assert TriggerType.CRON         == "cron"
    assert TriggerType.EVENT        == "event"
    assert TriggerType.MANUAL       == "manual"
    assert TriggerType.ORCHESTRATOR == "orchestrator"


def test_measurement_period_values():
    assert MeasurementPeriod.H24 == "24h"
    assert MeasurementPeriod.H72 == "72h"
    assert MeasurementPeriod.D7  == "7d"


# ── CuratedSite ──────────────────────────────────────────────

def test_curated_site_create_defaults():
    site = CuratedSiteCreate(
        site_name="LiveMint Stock Market",
        section_url="https://www.livemint.com/market/stock-market-news",
    )
    assert site.active is True
    assert site.pre_score_threshold == 4.0


def test_curated_site_create_custom_threshold():
    site = CuratedSiteCreate(
        site_name="LiveMint India News",
        section_url="https://www.livemint.com/news/india",
        pre_score_threshold=6.0,
    )
    assert site.pre_score_threshold == 6.0


# ── RawContent ───────────────────────────────────────────────

def test_structured_summary_all_fields():
    s = StructuredSummary(
        story_narrative="SEBI banned X.",
        key_data_points=["₹500 crore fine", "effective 1 June 2026"],
        mechanism="Regulatory action triggered by audit findings.",
        implications="Retail investors face higher transaction costs.",
        content_angles=["Why this hurts retail more than institutions"],
    )
    assert len(s.key_data_points) == 2
    assert len(s.content_angles) == 1


def test_raw_content_create_minimal():
    rc = RawContentCreate(
        url="https://livemint.com/article/123",
        normalized_url="livemint.com/article/123",
        title="SEBI bans X",
        source_name="LiveMint",
        full_text="Full article text here.",
    )
    assert rc.vision_fallback_used is False
    assert rc.paywall_detected is False
    assert rc.word_count == 0


# ── Idea ─────────────────────────────────────────────────────

def test_idea_create():
    idea = IdeaCreate(
        platform=Platform.LINKEDIN,
        angle="Why SEBI's new F&O rules will hurt retail traders more than protect them",
        agent_reasoning="Unexpectedness 9/10 — mainstream narrative says protection, actual effect is opposite",
        score=8.5,
    )
    assert idea.platform == Platform.LINKEDIN
    assert idea.score == 8.5
    assert idea.recent_coverage_flag is False


def test_idea_approval_with_edited_angle():
    approval = IdeaApproval(
        approval_status=ApprovalStatus.APPROVED,
        edited_angle="SEBI's F&O rules: protection framing vs. retail reality",
    )
    assert approval.approval_status == ApprovalStatus.APPROVED
    assert approval.edited_angle is not None


def test_idea_rejection_no_edit():
    rejection = IdeaApproval(approval_status=ApprovalStatus.REJECTED)
    assert rejection.edited_angle is None


# ── Draft ────────────────────────────────────────────────────

def test_draft_create_with_finance_flags():
    flag = FinanceFlag(
        flag_type="financial_figure",
        content="₹500 crore",
        context="The regulator imposed a ₹500 crore fine on the firm.",
    )
    draft = DraftCreate(
        platform=Platform.LINKEDIN,
        content_text="Post body here.",
        agent_reasoning="Used contrarian framing based on style guide preference.",
        finance_flags=[flag],
    )
    assert len(draft.finance_flags) == 1
    assert draft.finance_flags[0].flag_type == "financial_figure"


def test_draft_create_no_flags_by_default():
    draft = DraftCreate(
        platform=Platform.TWITTER,
        content_text="Short tweet.",
        agent_reasoning="News-driven, punchy single claim.",
    )
    assert draft.finance_flags == []


# ── Analytics ────────────────────────────────────────────────

def test_linkedin_metrics_defaults():
    m = LinkedInMetrics()
    assert m.impressions == 0
    assert m.reactions == 0


def test_twitter_metrics_defaults():
    m = TwitterMetrics()
    assert m.bookmarks == 0


def test_blog_metrics_defaults():
    m = BlogMetrics()
    assert m.avg_engagement_time_seconds == 0.0


def test_content_analytics_create():
    ca = ContentAnalyticsCreate(
        post_id=uuid4(),
        platform="linkedin",
        measurement_period=MeasurementPeriod.D7,
        metrics=LinkedInMetrics(impressions=5000, reactions=120).model_dump(),
        performance_score=0.72,
    )
    assert ca.measurement_period == MeasurementPeriod.D7
    assert ca.metrics["impressions"] == 5000


# ── RunLog ───────────────────────────────────────────────────

def test_run_log_create():
    log = RunLogCreate(
        agent_name="research_agent",
        trigger_type=TriggerType.CRON,
        processed_count=40,
        success_count=38,
        failure_count=2,
        duration_seconds=187.3,
        reasoning_trace="Processed 7 sites. 3 vision fallbacks triggered.",
        token_cost={"input": 12000, "output": 4000, "model": "claude-haiku-4-5"},
    )
    assert log.failure_count == 2
    assert log.token_cost["input"] == 12000


# ── BrandMemory ──────────────────────────────────────────────

def test_brand_memory_create():
    bm = BrandMemoryCreate(
        content="Most people think helium is for balloons...",
        platform=Platform.LINKEDIN,
    )
    assert bm.performance_metrics == {}
    assert bm.published_at is None


# ── KnowledgeBase ────────────────────────────────────────────

def test_knowledge_base_chunk_create():
    chunk = KnowledgeBaseChunkCreate(
        source_file="india_mutual_fund_regulations_2025.pdf",
        chunk_index=3,
        content="SEBI circular dated 15 Jan 2025 mandates that...",
    )
    assert chunk.chunk_index == 3


# ── CostLog ──────────────────────────────────────────────────

def test_cost_log_upsert():
    log = CostLogUpsert(
        agent_name="scoring_agent",
        date=date(2026, 5, 29),
        token_count=8500,
        estimated_cost_usd=0.043,
    )
    assert log.estimated_cost_usd == pytest.approx(0.043)
```

- [ ] **Step 3: Run tests**

```powershell
cd D:\Intern\content-automation-bot\backend
pytest tests/test_models.py -v
```

Expected output: `30+ passed` (one per test function)

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/models.py backend/tests/test_models.py
git commit -m "feat: add Pydantic models for all 15 database tables"
```

---

### Task 7: Structured logging helper

**Files:**
- Create: `D:\Intern\content-automation-bot\backend\app\utils\logging.py`

- [ ] **Step 1: Write `app/utils/logging.py`**

```python
"""
Structured logging for agent decisions.
Every key decision an agent makes gets logged via log_agent_decision().
These strings feed into the reasoning_trace field of run_logs.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any


def get_logger(name: str) -> logging.Logger:
    """Get a named logger with a consistent format."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def log_agent_decision(
    logger: logging.Logger,
    decision: str,
    reasoning: str,
    context: dict[str, Any] | None = None,
) -> str:
    """
    Log a structured agent decision and return it as a JSON string
    so the caller can accumulate these into a reasoning_trace.

    Usage:
        trace_entries = []
        entry = log_agent_decision(logger, "discard_article", "Below pre_score threshold", {"score": 3.2})
        trace_entries.append(entry)
        ...
        reasoning_trace = "\\n".join(trace_entries)
    """
    entry = {
        "ts":        datetime.now(timezone.utc).isoformat(),
        "decision":  decision,
        "reasoning": reasoning,
        "context":   context or {},
    }
    logger.info(json.dumps(entry))
    return json.dumps(entry)


def format_token_cost(
    input_tokens: int,
    output_tokens: int,
    model: str,
) -> dict[str, Any]:
    """
    Build the token_cost dict written to run_logs.
    Approximate USD costs — update rates when Anthropic changes pricing.
    """
    rates = {
        "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},   # per million tokens
        "claude-haiku-4-5":  {"input": 0.25, "output": 1.25},
    }
    rate = rates.get(model, {"input": 3.00, "output": 15.00})
    cost = (input_tokens * rate["input"] + output_tokens * rate["output"]) / 1_000_000

    return {
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "model":         model,
        "estimated_usd": round(cost, 6),
    }
```

- [ ] **Step 2: Verify import**

```powershell
cd D:\Intern\content-automation-bot\backend
python -c "from app.utils.logging import get_logger, log_agent_decision, format_token_cost; print('logging utils OK')"
```

Expected:
```
logging utils OK
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/utils/logging.py
git commit -m "feat: add structured logging helper for agent decisions"
```

---

### Task 8: arq worker skeleton

**Files:**
- Create: `D:\Intern\content-automation-bot\backend\app\queue\tasks.py`
- Create: `D:\Intern\content-automation-bot\backend\app\queue\worker.py`

- [ ] **Step 1: Write `app/queue/tasks.py`**

```python
"""
Stub arq task functions — one per agent.
Each agent plan replaces its stub with the real implementation.
All stubs log that they ran so the worker health check can verify routing.
"""
import logging

logger = logging.getLogger(__name__)


async def research_agent_task(
    ctx: dict,
    topic: str | None = None,
    url: str | None = None,
) -> dict:
    """
    Research agent — discovers and extracts articles from curated sites.
    Triggered: daily cron at 6 AM IST, or on-demand by orchestrator.
    Args:
        topic: Optional topic hint for targeted research (e.g. "SEBI announcement")
        url:   Optional specific URL to fast-track (e.g. breaking news)
    Returns stub until Plan 2 (Research Agent) is implemented.
    """
    logger.info(f"research_agent_task called | topic={topic} | url={url}")
    return {"status": "stub", "agent": "research"}


async def scoring_agent_task(ctx: dict) -> dict:
    """
    Scoring agent — reads unprocessed raw_content, scores, generates ideas.
    Triggered: by event after research_agent_task completes.
    Returns stub until Plan 3 (Scoring Agent) is implemented.
    """
    logger.info("scoring_agent_task called")
    return {"status": "stub", "agent": "scoring"}


async def creation_agent_task(
    ctx: dict,
    idea_ids: list[str],
) -> dict:
    """
    Content creation agent — generates platform drafts for approved ideas.
    Triggered: by orchestrator after weekly plan is approved.
    Args:
        idea_ids: List of approved idea UUIDs to generate content for.
    Returns stub until Plan 5 (Content Creation Agent) is implemented.
    """
    logger.info(f"creation_agent_task called | idea_ids={idea_ids}")
    return {"status": "stub", "agent": "creation"}


async def publishing_agent_task(ctx: dict) -> dict:
    """
    Publishing agent — posts approved drafts that are due.
    Triggered: every 15 minutes by cron.
    Returns stub until Plan 7 (Publishing Agent) is implemented.
    """
    logger.info("publishing_agent_task called")
    return {"status": "stub", "agent": "publishing"}


async def analytics_agent_task(
    ctx: dict,
    post_id: str,
    measurement_period: str,
) -> dict:
    """
    Analytics agent — pulls metrics for one post at one time window.
    Triggered: by publishing agent 24h, 72h, and 7d after publish.
    Args:
        post_id:            UUID of the published_post record.
        measurement_period: "24h", "72h", or "7d"
    Returns stub until Plan 8 (Analytics Agent) is implemented.
    """
    logger.info(f"analytics_agent_task called | post_id={post_id} | period={measurement_period}")
    return {"status": "stub", "agent": "analytics"}
```

- [ ] **Step 2: Write `app/queue/worker.py`**

```python
"""
arq WorkerSettings.

Run the worker from the backend/ directory:
    python -m arq app.queue.worker.WorkerSettings

Prerequisites:
    - Redis running locally: redis-server (or redis-server.exe on Windows)
    - .env file present with REDIS_URL set
"""
from arq import cron
from arq.connections import RedisSettings

from app.queue.tasks import (
    analytics_agent_task,
    creation_agent_task,
    publishing_agent_task,
    research_agent_task,
    scoring_agent_task,
)


async def startup(ctx: dict) -> None:
    """Initialise shared resources available to all task functions via ctx."""
    from app.db.client import get_supabase_client
    from app.config import get_settings
    ctx["supabase"] = get_supabase_client()
    ctx["settings"] = get_settings()


async def shutdown(ctx: dict) -> None:
    pass


def _parse_redis_settings() -> RedisSettings:
    """Parse REDIS_URL env var into arq RedisSettings."""
    from app.config import get_settings
    url = get_settings().redis_url
    # Expected format: redis://host:port  or  redis://host
    host = "localhost"
    port = 6379
    if "://" in url:
        netloc = url.split("://", 1)[1].split("/")[0]
        if ":" in netloc:
            host, port_str = netloc.rsplit(":", 1)
            port = int(port_str)
        else:
            host = netloc
    return RedisSettings(host=host, port=port)


class WorkerSettings:
    functions = [
        research_agent_task,
        scoring_agent_task,
        creation_agent_task,
        publishing_agent_task,
        analytics_agent_task,
    ]
    on_startup  = startup
    on_shutdown = shutdown
    redis_settings = _parse_redis_settings()
    max_jobs    = 10
    job_timeout = 600   # seconds — 10 min max per job

    cron_jobs = [
        # 6:00 AM IST = 00:30 UTC
        cron(research_agent_task, hour=0, minute=30),
        # Publishing queue check every 15 minutes
        cron(publishing_agent_task, minute={0, 15, 30, 45}),
    ]
```

- [ ] **Step 3: Verify arq can load the worker definition**

```powershell
cd D:\Intern\content-automation-bot\backend
python -c "from app.queue.worker import WorkerSettings; print('WorkerSettings OK'); print(f'Functions: {[f.__name__ for f in WorkerSettings.functions]}')"
```

Expected output:
```
WorkerSettings OK
Functions: ['research_agent_task', 'scoring_agent_task', 'creation_agent_task', 'publishing_agent_task', 'analytics_agent_task']
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/queue/tasks.py backend/app/queue/worker.py
git commit -m "feat: add arq worker skeleton with stub task functions for all 6 agents"
```

---

### Task 9: tests/conftest.py

**Files:**
- Create: `D:\Intern\content-automation-bot\backend\tests\conftest.py`

- [ ] **Step 1: Write `tests/conftest.py`**

```python
import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: requires a real Supabase connection and .env credentials",
    )


@pytest.fixture
def mock_supabase(mocker):
    """
    Pytest fixture: injects a MagicMock Supabase client.
    Use in tests that shouldn't hit the real DB.

    Usage:
        def test_something(mock_supabase):
            mock_supabase.table.return_value.select.return_value.execute.return_value.data = []
            ...
    """
    from app.db import client as client_module
    client_module.reset_client()

    mock = mocker.MagicMock()
    mocker.patch("app.db.client.get_supabase_client", return_value=mock)
    yield mock

    client_module.reset_client()


@pytest.fixture
def sample_curated_site_data() -> dict:
    return {
        "site_name":           "LiveMint Stock Market",
        "section_url":         "https://www.livemint.com/market/stock-market-news",
        "active":              True,
        "pre_score_threshold": 4.0,
    }


@pytest.fixture
def sample_brand_voice() -> list[dict]:
    return [
        {
            "content":  "Most people think helium is for balloons. It's actually for chips, MRI machines, and rockets.",
            "platform": "linkedin",
        },
        {
            "content":  "The rupee didn't just quietly slip to ₹95 against the dollar.",
            "platform": "linkedin",
        },
    ]
```

- [ ] **Step 2: Run all unit tests together**

```powershell
cd D:\Intern\content-automation-bot\backend
pytest tests/ -v -m "not integration"
```

Expected output: all tests pass (config, db_client unit tests, all model tests).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: add conftest with integration marker and shared fixtures"
```

---

### Task 10: Seed script

**Files:**
- Create: `D:\Intern\content-automation-bot\backend\scripts\seed.py`

- [ ] **Step 1: Write `scripts/seed.py`**

```python
"""
Seeds initial data into Supabase.

Run from backend/ with venv active:
    python scripts/seed.py

What it seeds:
  1. curated_sites  — 7 initial Indian finance sites
  2. brand_memory   — 5 brand voice samples (no embeddings yet;
                      embeddings added in Plan 4 / Knowledge Base setup)
  3. style_guide    — empty baseline rows for each platform
  4. topic_performance_model — default 0.5 score rows for 8 topic categories
"""
import sys
import os

# Allow running from scripts/ or backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.client import get_supabase_client

INITIAL_SITES = [
    {
        "site_name":           "LiveMint Stock Market",
        "section_url":         "https://www.livemint.com/market/stock-market-news",
        "active":              True,
        "pre_score_threshold": 4.0,
    },
    {
        "site_name":           "LiveMint IPO",
        "section_url":         "https://www.livemint.com/topic/ipo",
        "active":              True,
        "pre_score_threshold": 4.0,
    },
    {
        "site_name":           "LiveMint Bonds",
        "section_url":         "https://www.livemint.com/market/bonds",
        "active":              True,
        "pre_score_threshold": 4.0,
    },
    {
        "site_name":           "LiveMint India News",
        "section_url":         "https://www.livemint.com/news/india",
        "active":              True,
        "pre_score_threshold": 6.0,  # Higher — too much general news noise
    },
    {
        "site_name":           "Business Standard Today",
        "section_url":         "https://www.business-standard.com/todays-paper",
        "active":              True,
        "pre_score_threshold": 4.0,
    },
    {
        "site_name":           "Business Standard",
        "section_url":         "https://www.business-standard.com",
        "active":              True,
        "pre_score_threshold": 4.0,
    },
    {
        "site_name":           "Business Standard Mutual Fund",
        "section_url":         "https://www.business-standard.com/markets/mutual-fund",
        "active":              True,
        "pre_score_threshold": 4.0,
    },
]

BRAND_VOICE_SAMPLES = [
    {
        "content": (
            "Most people think helium is for balloons. It's actually for chips, MRI machines, and rockets.\n\n"
            "India produces zero helium domestically. Every cubic metre comes from imports, more than half of it "
            "from Qatar alone. With the Middle East now disrupted and India's semiconductor ambitions growing fast, "
            "this quiet dependency is becoming a serious problem.\n\n"
            "The gas you never think about could quietly hold back everything India is trying to build, "
            "in healthcare, space, and the chip industry."
        ),
        "platform":            "linkedin",
        "published_at":        None,
        "performance_metrics": {},
    },
    {
        "content": (
            "Did you know the IPL is now the second most valuable sports media property in the world, "
            "per match behind only the NFL?\n\n"
            "What started as a cricket tournament in 2008 is now a $18.5 billion business ecosystem. "
            "The $6.2 billion media rights deal signed in 2022 repriced every franchise overnight. "
            "Rajasthan Royals just sold for $1.63 billion. Blackstone one of the world's largest private "
            "equity firms is in the room bidding for RCB.\n\n"
            "This isn't entertainment anymore. It's infrastructure for capital."
        ),
        "platform":            "linkedin",
        "published_at":        None,
        "performance_metrics": {},
    },
    {
        "content": (
            "Investing becomes meaningful when it helps you stop postponing your dreams.\n\n"
            "A 55-year-old woman wanted to plan a Europe trip with her family, but arranging ₹10 lakhs "
            "together felt overwhelming. Instead of delaying it again, we helped her build a goal-based "
            "SIP portfolio designed around that dream.\n\n"
            "Because wealth creation is important, but so is creating memories."
        ),
        "platform":            "linkedin",
        "published_at":        None,
        "performance_metrics": {},
    },
    {
        "content": (
            "The rupee didn't just quietly slip to ₹95 against the dollar. "
            "There's a very specific reason it keeps falling — and it starts with a barrel of crude oil.\n\n"
            "India imports 85% of its crude oil. Every time global oil prices rise, India needs more dollars "
            "to pay for the same barrels. More dollars demanded means more rupees sold. "
            "More rupees in the market means each rupee is worth less. The math is that direct.\n\n"
            "The rupee doesn't fall randomly. It reacts to oil. And right now, oil is not being kind."
        ),
        "platform":            "linkedin",
        "published_at":        None,
        "performance_metrics": {},
    },
    {
        "content": (
            "Markets are not falling apart.\nThey are adjusting.\n\n"
            "This week had everything.\nOil moving up.\nGlobal tensions rising.\n"
            "Sector leadership quietly shifting.\n\n"
            "And yet, the bigger picture hasn't changed overnight.\n\n"
            "Broader markets are stabilising.\nDefensives are holding.\nFlows are still selective.\n\n"
            "This is what market transitions look like.\nNot loud. Not obvious. But important."
        ),
        "platform":            "linkedin",
        "published_at":        None,
        "performance_metrics": {},
    },
]

INITIAL_STYLE_GUIDE = [
    {"platform": "linkedin", "insights": {}},
    {"platform": "twitter",  "insights": {}},
    {"platform": "blog",     "insights": {}},
    {"platform": "email",    "insights": {}},
    {"platform": "general",  "insights": {}},
]

INITIAL_TOPIC_CATEGORIES = [
    "regulatory_news",
    "company_strategy",
    "macroeconomic",
    "behavioral_finance",
    "market_structure",
    "personal_finance",
    "ipo_and_capital_markets",
    "global_impact_on_india",
]


def seed_curated_sites(db) -> None:
    print("\n→ Seeding curated_sites...")
    for site in INITIAL_SITES:
        try:
            db.table("curated_sites").upsert(
                site, on_conflict="section_url"
            ).execute()
            print(f"  ✓ {site['site_name']} (threshold: {site['pre_score_threshold']})")
        except Exception as e:
            print(f"  ✗ {site['site_name']}: {e}")


def seed_brand_memory(db) -> None:
    print("\n→ Seeding brand_memory (no embeddings yet — added in Plan 4)...")
    for sample in BRAND_VOICE_SAMPLES:
        try:
            # Deduplicate by first 80 chars of content
            existing = (
                db.table("brand_memory")
                .select("id")
                .ilike("content", f"{sample['content'][:80]}%")
                .execute()
            )
            if existing.data:
                print(f"  - Already exists: {sample['content'][:60]}...")
                continue
            db.table("brand_memory").insert(sample).execute()
            print(f"  ✓ {sample['content'][:60]}...")
        except Exception as e:
            print(f"  ✗ Failed: {e}")


def seed_style_guide(db) -> None:
    print("\n→ Seeding style_guide (empty baseline)...")
    for row in INITIAL_STYLE_GUIDE:
        try:
            db.table("style_guide").upsert(
                row, on_conflict="platform"
            ).execute()
            print(f"  ✓ {row['platform']}")
        except Exception as e:
            print(f"  ✗ {row['platform']}: {e}")


def seed_topic_performance_model(db) -> None:
    print("\n→ Seeding topic_performance_model (default scores)...")
    for category in INITIAL_TOPIC_CATEGORIES:
        try:
            db.table("topic_performance_model").upsert(
                {"topic_category": category, "performance_score": 0.5, "sample_count": 0},
                on_conflict="topic_category",
            ).execute()
            print(f"  ✓ {category}")
        except Exception as e:
            print(f"  ✗ {category}: {e}")


def main() -> None:
    print("Starting seed...")
    db = get_supabase_client()
    seed_curated_sites(db)
    seed_brand_memory(db)
    seed_style_guide(db)
    seed_topic_performance_model(db)
    print("\n✓ Seed complete.")
    print("\nNOTE: brand_memory rows have no embeddings.")
    print("After setting VOYAGE_API_KEY, run: python scripts/embed_brand_memory.py")
    print("(Written in Plan 4 — Orchestrator + Knowledge Base)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the seed script**

```powershell
cd D:\Intern\content-automation-bot\backend
python scripts/seed.py
```

Expected output:
```
Starting seed...

→ Seeding curated_sites...
  ✓ LiveMint Stock Market (threshold: 4.0)
  ✓ LiveMint IPO (threshold: 4.0)
  ✓ LiveMint Bonds (threshold: 4.0)
  ✓ LiveMint India News (threshold: 6.0)
  ✓ Business Standard Today (threshold: 4.0)
  ✓ Business Standard (threshold: 4.0)
  ✓ Business Standard Mutual Fund (threshold: 4.0)

→ Seeding brand_memory (no embeddings yet — added in Plan 4)...
  ✓ Most people think helium is for balloons...
  ✓ Did you know the IPL is now the second most valuable...
  ✓ Investing becomes meaningful when it helps you...
  ✓ The rupee didn't just quietly slip to ₹95...
  ✓ Markets are not falling apart...

→ Seeding style_guide (empty baseline)...
  ✓ linkedin  ✓ twitter  ✓ blog  ✓ email  ✓ general

→ Seeding topic_performance_model (default scores)...
  ✓ regulatory_news  ✓ company_strategy  ... (8 categories)

✓ Seed complete.
```

- [ ] **Step 3: Verify in Supabase dashboard**

Open https://supabase.com/dashboard/project/nenvkgxpvygxskrrvkyc → **Table Editor**

Check:
- `curated_sites`: 7 rows
- `brand_memory`: 5 rows (embedding column NULL — expected)
- `style_guide`: 5 rows
- `topic_performance_model`: 8 rows

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/seed.py
git commit -m "feat: add seed script for curated_sites, brand_memory, style_guide, topic_performance_model"
```

---

### Task 11: Integration smoke test

**Files:**
- Modify: `D:\Intern\content-automation-bot\backend\tests\test_db_client.py` (add integration test)

- [ ] **Step 1: Run the integration test (requires real DB + .env)**

```powershell
cd D:\Intern\content-automation-bot\backend
pytest tests/test_db_client.py::test_client_can_query_supabase -v -m integration
```

Expected output:
```
tests/test_db_client.py::test_client_can_query_supabase PASSED
1 passed
```

- [ ] **Step 2: Run the full unit test suite one final time**

```powershell
pytest tests/ -v -m "not integration"
```

Expected: all tests pass, 0 failures.

- [ ] **Step 3: Final commit**

```bash
git add .
git commit -m "chore: foundation complete — all 15 tables, models, arq worker, seed data"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Covered by |
|-----------------|-----------|
| All 15 data stores defined | Task 5 (SQL) + Task 6 (models) |
| pgvector for brand_memory + knowledge_base | Task 5 (HNSW indexes + match functions) |
| arq job queue | Task 8 |
| 6am IST cron for research agent | Task 8 (cron, hour=0, minute=30 UTC) |
| 15-minute publishing check | Task 8 (cron, minute={0,15,30,45}) |
| Curated sites seed with per-site threshold | Task 10 |
| Brand voice seed | Task 10 |
| Style guide + topic_performance_model baseline | Task 10 |
| Supabase client singleton | Task 4 |
| Configuration management | Task 3 |
| Structured agent logging | Task 7 |

### Placeholder scan
None found — all tasks contain complete code.

### Type consistency check
- `Platform`, `ApprovalStatus`, `DraftStatus`, `TriggerType`, `MeasurementPeriod` enums defined once in `models.py`, used consistently in all Create/Update models and tests.
- `StructuredSummary` used in `RawContentCreate.structured_summary` and referenced in test.
- `FinanceFlag` used in `DraftCreate.finance_flags` (list) — consistent with SQL `JSONB DEFAULT '[]'`.
- Vector functions `match_brand_memory`, `check_recent_brand_coverage`, `match_knowledge_base` defined in SQL with `vector(1024)` params — matches Voyage AI `voyage-3` output dimension.
