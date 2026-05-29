"""
Article filters: cheap checks that run before the expensive full-article fetch.

Execution order in the research pipeline (cheapest first):
  1. is_url_seen      — Supabase SELECT on normalized_url (skip if already stored)
  2. is_article_fresh — datetime comparison against publication_date
  3. is_article_long_enough — word count check (after full article is fetched)

All functions are synchronous. is_url_seen uses the synchronous supabase-py client
directly; the single HTTP call per article is fast enough to call from async code.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from supabase import Client

from app.utils.logging import get_logger

logger = get_logger(__name__)


def is_url_seen(normalized_url: str, supabase: Client) -> bool:
    """
    Return True if this normalized_url already exists in raw_content.

    Performs an exact-match SELECT on the normalized_url column (unique index).
    Uses LIMIT 1 so the DB returns as soon as any row is found.
    """
    response = (
        supabase
        .table("raw_content")
        .select("id")
        .eq("normalized_url", normalized_url)
        .limit(1)
        .execute()
    )
    seen = len(response.data) > 0
    if seen:
        logger.info(
            "is_url_seen: duplicate skipped",
            extra={"normalized_url": normalized_url},
        )
    return seen


def is_article_fresh(
    publication_date: Optional[datetime],
    max_age_days: int,
    *,
    now: Optional[datetime] = None,
) -> bool:
    """
    Return True if the article is within max_age_days of `now`.

    Articles with no publication_date are treated as fresh — we cannot reject
    them without fetching the full article first. Age is re-verified in Part 3
    after the fetch if the date is still missing.

    Naive datetimes are assumed to be UTC.
    """
    if publication_date is None:
        return True

    reference = now or datetime.now(timezone.utc)

    # Normalise to UTC-aware for safe subtraction
    if publication_date.tzinfo is None:
        publication_date = publication_date.replace(tzinfo=timezone.utc)

    age_days = (reference - publication_date).days
    fresh = age_days <= max_age_days

    if not fresh:
        logger.info(
            "is_article_fresh: stale article skipped",
            extra={"age_days": age_days, "max_age_days": max_age_days},
        )
    return fresh


def is_article_long_enough(word_count: int, min_words: int) -> bool:
    """Return True if word_count >= min_words."""
    long_enough = word_count >= min_words
    if not long_enough:
        logger.info(
            "is_article_long_enough: short article skipped",
            extra={"word_count": word_count, "min_words": min_words},
        )
    return long_enough
