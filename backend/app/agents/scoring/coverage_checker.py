"""
Recent brand coverage checker for the scoring agent.

Checks whether similar content has already been published by the brand on a
given platform within the last N days, via pgvector cosine similarity.
Returns True if similar content was found (flag the idea), False otherwise.

Usage:
    from app.agents.scoring.coverage_checker import check_recent_coverage
    already_covered = check_recent_coverage(embedding, platform.value, db)
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.vector_search import check_recent_brand_coverage
from app.utils.logging import get_logger

logger = get_logger(__name__)


def check_recent_coverage(
    embedding: list[float],
    platform: str,
    db: Session,
    *,
    days_back: int = 30,
    threshold: float = 0.85,
) -> bool:
    """
    Return True if brand-published content similar to `embedding` exists on
    `platform` within the last `days_back` days (similarity >= `threshold`).

    If `embedding` is empty (Voyage AI unavailable), returns False immediately
    without touching the database.

    Never raises — returns False on any error.
    """
    if not embedding:
        return False

    try:
        rows = check_recent_brand_coverage(
            db,
            topic_embedding=embedding,
            platform_filter=platform,
            similarity_threshold=threshold,
            days_back=days_back,
        )
        return bool(rows)
    except Exception as exc:
        logger.warning(
            "check_recent_coverage failed",
            extra={"platform": platform, "error": str(exc)},
        )
        return False
