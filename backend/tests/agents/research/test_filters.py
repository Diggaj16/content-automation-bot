"""Unit tests for app.agents.research.filters."""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

from app.agents.research.filters import (
    is_url_seen,
    is_article_fresh,
    is_article_long_enough,
)


# ── is_url_seen ───────────────────────────────────────────────────────────────

def _make_supabase_mock(rows: list[dict]) -> MagicMock:
    """Supabase mock whose .execute().data returns `rows`."""
    mock = MagicMock()
    (
        mock.table.return_value
        .select.return_value
        .eq.return_value
        .limit.return_value
        .execute.return_value
        .data
    ) = rows
    return mock


class TestIsUrlSeen:
    def test_returns_false_when_not_in_db(self):
        sb = _make_supabase_mock(rows=[])
        assert is_url_seen("https://example.com/article", sb) is False

    def test_returns_true_when_found(self):
        sb = _make_supabase_mock(rows=[{"id": "abc123"}])
        assert is_url_seen("https://example.com/article", sb) is True

    def test_calls_correct_table(self):
        sb = _make_supabase_mock(rows=[])
        is_url_seen("https://example.com/article", sb)
        sb.table.assert_called_once_with("raw_content")

    def test_queries_normalized_url_field(self):
        sb = _make_supabase_mock(rows=[])
        is_url_seen("https://example.com/article", sb)
        sb.table.return_value.select.return_value.eq.assert_called_once_with(
            "normalized_url", "https://example.com/article"
        )

    def test_limits_to_one_row(self):
        sb = _make_supabase_mock(rows=[])
        is_url_seen("https://example.com/article", sb)
        sb.table.return_value.select.return_value.eq.return_value.limit.assert_called_once_with(1)


# ── is_article_fresh ─────────────────────────────────────────────────────────

_NOW = datetime(2025, 5, 15, 12, 0, 0, tzinfo=timezone.utc)


class TestIsArticleFresh:
    def test_fresh_article_within_limit(self):
        pub = _NOW - timedelta(days=3)
        assert is_article_fresh(pub, max_age_days=7, now=_NOW) is True

    def test_article_exactly_at_limit_is_fresh(self):
        pub = _NOW - timedelta(days=7)
        assert is_article_fresh(pub, max_age_days=7, now=_NOW) is True

    def test_article_one_day_over_limit_is_stale(self):
        pub = _NOW - timedelta(days=8)
        assert is_article_fresh(pub, max_age_days=7, now=_NOW) is False

    def test_none_publication_date_is_treated_as_fresh(self):
        assert is_article_fresh(None, max_age_days=7, now=_NOW) is True

    def test_future_dated_article_is_fresh(self):
        pub = _NOW + timedelta(days=1)
        assert is_article_fresh(pub, max_age_days=7, now=_NOW) is True

    def test_naive_datetime_treated_as_utc(self):
        naive_pub = datetime(2025, 5, 14, 12, 0, 0)  # 1 day before _NOW, no tzinfo
        assert is_article_fresh(naive_pub, max_age_days=7, now=_NOW) is True

    def test_stale_naive_datetime(self):
        naive_pub = datetime(2025, 5, 7, 12, 0, 0)  # 8 days before _NOW
        assert is_article_fresh(naive_pub, max_age_days=7, now=_NOW) is False


# ── is_article_long_enough ───────────────────────────────────────────────────

class TestIsArticleLongEnough:
    def test_word_count_above_minimum(self):
        assert is_article_long_enough(500, min_words=400) is True

    def test_word_count_exactly_at_minimum(self):
        assert is_article_long_enough(400, min_words=400) is True

    def test_word_count_one_below_minimum(self):
        assert is_article_long_enough(399, min_words=400) is False

    def test_zero_words(self):
        assert is_article_long_enough(0, min_words=400) is False

    def test_min_words_zero_always_passes(self):
        assert is_article_long_enough(0, min_words=0) is True
