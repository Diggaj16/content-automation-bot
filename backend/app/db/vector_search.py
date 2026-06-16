"""
Vector similarity search — SQLAlchemy + pgvector replacements for the old
Postgres RPC functions (match_brand_memory, match_knowledge_base,
check_recent_brand_coverage).

All functions use cosine distance (<=>) via pgvector's `cosine_distance`, and
return plain dicts shaped like the old RPC rows so callers need minimal changes.
similarity = 1 - cosine_distance.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.orm import BrandMemory, KnowledgeBase


def match_brand_memory(
    db: Session,
    query_embedding: list[float],
    match_count: int = 5,
    filter_platform: Optional[str] = None,
    days_back: Optional[int] = 90,
) -> list[dict]:
    """Most semantically-similar brand_memory rows (cosine). Mirrors the old RPC."""
    if not query_embedding:
        return []

    distance = BrandMemory.embedding.cosine_distance(query_embedding)
    stmt = select(BrandMemory, distance.label("distance")).where(BrandMemory.embedding.is_not(None))

    if filter_platform:
        stmt = stmt.where(BrandMemory.platform == filter_platform)
    if days_back is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        # Match the RPC's lenient behavior: keep rows with no published_at
        stmt = stmt.where(
            (BrandMemory.published_at.is_(None)) | (BrandMemory.published_at >= cutoff)
        )

    stmt = stmt.order_by(distance).limit(match_count)

    rows = db.execute(stmt).all()
    return [
        {
            "id": str(bm.id),
            "content": bm.content,
            "platform": bm.platform,
            "published_at": bm.published_at.isoformat() if bm.published_at else None,
            "performance_metrics": bm.performance_metrics,
            "similarity": 1.0 - float(dist),
        }
        for bm, dist in rows
    ]


def match_knowledge_base(
    db: Session,
    query_embedding: list[float],
    match_count: int = 8,
) -> list[dict]:
    """Most semantically-similar knowledge_base chunks (cosine). Mirrors the old RPC."""
    if not query_embedding:
        return []

    distance = KnowledgeBase.embedding.cosine_distance(query_embedding)
    stmt = (
        select(KnowledgeBase, distance.label("distance"))
        .where(KnowledgeBase.embedding.is_not(None))
        .order_by(distance)
        .limit(match_count)
    )

    rows = db.execute(stmt).all()
    return [
        {
            "id": str(kb.id),
            "source_file": kb.source_file,
            "chunk_index": kb.chunk_index,
            "content": kb.content,
            "similarity": 1.0 - float(dist),
        }
        for kb, dist in rows
    ]


def check_recent_brand_coverage(
    db: Session,
    topic_embedding: list[float],
    platform_filter: str,
    similarity_threshold: float = 0.85,
    days_back: int = 14,
) -> list[dict]:
    """Recent brand posts on the same platform above a similarity threshold."""
    if not topic_embedding:
        return []

    distance = BrandMemory.embedding.cosine_distance(topic_embedding)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    stmt = (
        select(BrandMemory, distance.label("distance"))
        .where(
            BrandMemory.embedding.is_not(None),
            BrandMemory.platform == platform_filter,
            BrandMemory.published_at >= cutoff,
        )
        .order_by(distance)
        .limit(3)
    )

    rows = db.execute(stmt).all()
    return [
        {"id": str(bm.id), "content": bm.content, "similarity": 1.0 - float(dist)}
        for bm, dist in rows
        if (1.0 - float(dist)) >= similarity_threshold
    ]
