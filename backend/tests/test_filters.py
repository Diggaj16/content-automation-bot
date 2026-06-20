"""
Pure-logic tests for app.agents.research.filters — no network, no DB.
"""
from datetime import datetime, timedelta, timezone

from app.agents.research.filters import is_article_fresh, is_article_long_enough


class TestIsArticleFresh:
    def test_none_date_treated_as_fresh(self):
        assert is_article_fresh(None, max_age_days=7) is True

    def test_within_window_is_fresh(self):
        now = datetime(2026, 6, 20, tzinfo=timezone.utc)
        pub = now - timedelta(days=3)
        assert is_article_fresh(pub, max_age_days=7, now=now) is True

    def test_outside_window_is_stale(self):
        now = datetime(2026, 6, 20, tzinfo=timezone.utc)
        pub = now - timedelta(days=10)
        assert is_article_fresh(pub, max_age_days=7, now=now) is False

    def test_exactly_at_boundary_is_fresh(self):
        now = datetime(2026, 6, 20, tzinfo=timezone.utc)
        pub = now - timedelta(days=7)
        assert is_article_fresh(pub, max_age_days=7, now=now) is True

    def test_naive_datetime_assumed_utc(self):
        now = datetime(2026, 6, 20, tzinfo=timezone.utc)
        pub_naive = datetime(2026, 6, 18)  # 2 days before `now`, no tzinfo
        assert is_article_fresh(pub_naive, max_age_days=7, now=now) is True

    def test_future_publication_date_is_fresh(self):
        # Negative age (clock skew, scheduled posts) should not be flagged stale.
        now = datetime(2026, 6, 20, tzinfo=timezone.utc)
        pub = now + timedelta(days=1)
        assert is_article_fresh(pub, max_age_days=7, now=now) is True


class TestIsArticleLongEnough:
    def test_above_threshold_passes(self):
        assert is_article_long_enough(500, min_words=400) is True

    def test_below_threshold_fails(self):
        assert is_article_long_enough(100, min_words=400) is False

    def test_exactly_at_threshold_passes(self):
        assert is_article_long_enough(400, min_words=400) is True

    def test_zero_words_fails(self):
        assert is_article_long_enough(0, min_words=400) is False
