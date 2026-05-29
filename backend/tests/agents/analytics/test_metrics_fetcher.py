"""Tests for analytics metrics_fetcher module."""
from app.agents.analytics.metrics_fetcher import (
    fetch_metrics,
    calculate_performance_score,
)


def test_fetch_metrics_linkedin_returns_required_keys():
    metrics = fetch_metrics("linkedin", "li-stub-abc", "24h")
    assert "impressions" in metrics
    assert "reactions" in metrics
    assert "comments" in metrics
    assert "shares" in metrics


def test_fetch_metrics_twitter_returns_required_keys():
    metrics = fetch_metrics("twitter", "tw-stub-abc", "72h")
    assert "likes" in metrics
    assert "retweets" in metrics
    assert "impressions" in metrics
    assert "bookmarks" in metrics


def test_fetch_metrics_blog_returns_required_keys():
    metrics = fetch_metrics("blog", "blog-stub-abc", "7d")
    assert "page_views" in metrics
    assert "sessions" in metrics
    assert "avg_engagement_time_seconds" in metrics


def test_fetch_metrics_email_returns_required_keys():
    metrics = fetch_metrics("email", "email-stub-abc", "24h")
    assert "open_rate" in metrics
    assert "click_rate" in metrics
    assert "unsubscribes" in metrics


def test_fetch_metrics_unknown_platform_returns_empty_dict():
    metrics = fetch_metrics("unknown", "id-abc", "24h")
    assert metrics == {}


def test_fetch_metrics_never_raises():
    # Should not raise on any input
    metrics = fetch_metrics("linkedin", "", "invalid_period")
    assert isinstance(metrics, dict)


def test_calculate_performance_score_linkedin_range():
    metrics = {"impressions": 1000, "reactions": 50, "comments": 10, "shares": 5}
    score = calculate_performance_score("linkedin", metrics)
    assert 0.0 <= score <= 10.0


def test_calculate_performance_score_zero_impressions():
    metrics = {"impressions": 0, "reactions": 5, "comments": 1, "shares": 0}
    score = calculate_performance_score("linkedin", metrics)
    assert score == 0.0


def test_calculate_performance_score_unknown_platform_returns_zero():
    score = calculate_performance_score("unknown", {})
    assert score == 0.0


def test_calculate_performance_score_twitter():
    metrics = {"impressions": 500, "likes": 25, "retweets": 10, "bookmarks": 5}
    score = calculate_performance_score("twitter", metrics)
    assert 0.0 <= score <= 10.0
