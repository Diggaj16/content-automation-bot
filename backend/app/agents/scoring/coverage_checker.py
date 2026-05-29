"""
Recent brand coverage checker for the scoring agent.

Calls the Postgres RPC function `check_recent_brand_coverage` to detect whether
similar content has already been published by the brand on a given platform within
the last N days. Returns True if similar content was found (flag the idea),
False otherwise.

Usage:
    from app.agents.scoring.coverage_checker import check_recent_coverage
    already_covered = check_recent_coverage(embedding, platform.value, supabase)
"""
from __future__ import annotations

from supabase import Client

from app.utils.logging import get_logger

logger = get_logger(__name__)


def check_recent_coverage(
    embedding: list[float],
    platform: str,
    supabase: Client,
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
        resp = supabase.rpc(
            "check_recent_brand_coverage",
            {
                "topic_embedding":      embedding,
                "platform_filter":      platform,
                "days_back":            days_back,
                "similarity_threshold": threshold,
            },
        ).execute()
        return bool(resp.data)
    except Exception as exc:
        logger.warning(
            "check_recent_coverage failed",
            extra={"platform": platform, "error": str(exc)},
        )
        return False
