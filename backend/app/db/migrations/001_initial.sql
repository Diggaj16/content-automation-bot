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
    structured_summary    JSONB,
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
    embedding           vector(1024),
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
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name       TEXT NOT NULL,
    trigger_type     TEXT NOT NULL
                         CHECK (trigger_type IN
                                ('cron','event','manual','orchestrator')),
    processed_count  INTEGER NOT NULL DEFAULT 0,
    success_count    INTEGER NOT NULL DEFAULT 0,
    failure_count    INTEGER NOT NULL DEFAULT 0,
    duration_seconds FLOAT,
    reasoning_trace  TEXT,
    errors           JSONB NOT NULL DEFAULT '[]',
    token_cost       JSONB NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
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

-- HNSW vector indexes (no minimum row count, better recall than IVFFlat)
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

CREATE OR REPLACE FUNCTION check_recent_brand_coverage(
    topic_embedding      vector(1024),
    platform_filter      TEXT,
    days_back            INT   DEFAULT 30,
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
