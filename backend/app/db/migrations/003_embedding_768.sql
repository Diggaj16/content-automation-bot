-- Migration 003: Change embedding dimensions from 1024 (Voyage AI) to 768 (Gemini / fastembed bge-base)
--
-- Run this in the Supabase SQL editor BEFORE restarting the worker.
-- It will NULL out all existing embeddings (they need to be re-generated at the new dimension).
-- Brand memory and knowledge_base items will be re-embedded on next pipeline run.

-- 1. Drop vector indexes (can't change column type while indexes exist)
DROP INDEX IF EXISTS idx_brand_memory_embedding;
DROP INDEX IF EXISTS idx_knowledge_base_embedding;

-- 2. Drop RPC functions that reference vector(1024)
DROP FUNCTION IF EXISTS match_brand_memory(vector, integer, text, integer);
DROP FUNCTION IF EXISTS match_brand_memory(vector(1024), integer, text, integer);
DROP FUNCTION IF EXISTS check_recent_brand_coverage(vector, text, double precision, integer);
DROP FUNCTION IF EXISTS check_recent_brand_coverage(vector(1024), text, double precision, integer);
DROP FUNCTION IF EXISTS match_knowledge_base(vector, integer);
DROP FUNCTION IF EXISTS match_knowledge_base(vector(1024), integer);

-- 3. Change column dimensions (NULL out existing data — old 1024-dim vectors are invalid)
ALTER TABLE brand_memory
    ALTER COLUMN embedding TYPE vector(768) USING NULL;

ALTER TABLE knowledge_base
    ALTER COLUMN embedding TYPE vector(768) USING NULL;

-- 4. Recreate HNSW indexes for new dimension
CREATE INDEX IF NOT EXISTS idx_brand_memory_embedding
    ON brand_memory USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_knowledge_base_embedding
    ON knowledge_base USING hnsw (embedding vector_cosine_ops);

-- 5. Recreate RPC functions with vector(768) signatures

CREATE OR REPLACE FUNCTION match_brand_memory(
    query_embedding  vector(768),
    match_count      INT     DEFAULT 5,
    filter_platform  TEXT    DEFAULT NULL,
    days_back        INT     DEFAULT 90
)
RETURNS TABLE (
    id                  UUID,
    content             TEXT,
    platform            TEXT,
    published_at        TIMESTAMPTZ,
    performance_metrics JSONB,
    similarity          FLOAT
)
LANGUAGE plpgsql
AS $$
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
             OR bm.published_at IS NULL
             OR bm.published_at >= NOW() - (days_back || ' days')::INTERVAL)
    ORDER BY bm.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;


CREATE OR REPLACE FUNCTION check_recent_brand_coverage(
    topic_embedding      vector(768),
    platform_filter      TEXT,
    similarity_threshold DOUBLE PRECISION DEFAULT 0.85,
    days_back            INT              DEFAULT 14
)
RETURNS TABLE (
    id          UUID,
    content     TEXT,
    similarity  FLOAT
)
LANGUAGE plpgsql
AS $$
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
    query_embedding  vector(768),
    match_count      INT DEFAULT 8
)
RETURNS TABLE (
    id           UUID,
    content      TEXT,
    source_file  TEXT,
    chunk_index  INT,
    similarity   FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        kb.id,
        kb.content,
        kb.source_file,
        kb.chunk_index,
        1 - (kb.embedding <=> query_embedding) AS similarity
    FROM knowledge_base kb
    WHERE kb.embedding IS NOT NULL
    ORDER BY kb.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
