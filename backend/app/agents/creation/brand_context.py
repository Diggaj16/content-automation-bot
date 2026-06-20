"""
Brand context retrieval for content generation.

Finds semantically similar past published content via pgvector cosine
similarity, then formats it as a prompt context string.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.db.vector_search import match_brand_memory
from app.utils.logging import get_logger

logger = get_logger(__name__)


def get_brand_context(
    embedding: Optional[list[float]],
    platform: str,
    db: Session,
    match_count: int = 5,
) -> str:
    """
    Retrieve relevant past brand content using vector similarity.

    Args:
        embedding:   Embedding of the idea text (768-dim).
                     Empty list or None → return "" immediately, no query run.
        platform:    Platform string used to filter brand_memory results.
        db:          SQLAlchemy session.
        match_count: Number of similar examples to retrieve (default 5).

    Returns:
        Formatted string of past content examples, or "" if none found.
        Never raises.
    """
    if not embedding:
        return ""

    try:
        # days_back=None matches the original RPC's default (no time filter) —
        # the vector_search helper defaults to 90 days for other callers, but
        # brand context retrieval should draw on the brand's entire history.
        rows = match_brand_memory(
            db, embedding, match_count=match_count, filter_platform=platform, days_back=None
        )

        if not rows:
            return ""

        lines = [f"- {item['content']}" for item in rows]
        return "Past brand content examples:\n" + "\n".join(lines)

    except Exception as exc:
        logger.warning(f"get_brand_context: query failed | platform={platform} | err={exc}")
        return ""
