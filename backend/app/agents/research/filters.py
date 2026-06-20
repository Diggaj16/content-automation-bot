"""
Article filters: cheap checks that run before the expensive full-article fetch.

Execution order in the research pipeline (cheapest first):
  1. batch dedup against raw_content.normalized_url (done in tasks.py, not here)
  2. is_article_fresh — datetime comparison against publication_date
  3. is_article_long_enough — word count check (after full article is fetched)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)


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
