"""
Platform metrics fetcher stubs for the analytics agent.

These return simulated engagement data. Replace with real API calls
when platform credentials (LinkedIn API, Twitter API, etc.) are configured.
"""
import random
from app.utils.logging import get_logger

logger = get_logger(__name__)


def fetch_metrics(platform: str, post_identifier: str, measurement_period: str) -> dict:
    """
    Fetch engagement metrics for a published post.

    Currently returns randomised stub data. In production, replace each branch
    with a real API call using the post_identifier.

    Returns an empty dict for unknown platforms or on error. Never raises.
    """
    try:
        if platform == "linkedin":
            return {
                "impressions": random.randint(200, 5000),
                "reactions":   random.randint(5, 300),
                "comments":    random.randint(0, 80),
                "shares":      random.randint(0, 50),
            }
        elif platform == "twitter":
            return {
                "impressions": random.randint(100, 10000),
                "likes":       random.randint(2, 500),
                "retweets":    random.randint(0, 100),
                "bookmarks":   random.randint(0, 80),
            }
        elif platform == "blog":
            return {
                "page_views":                  random.randint(50, 3000),
                "sessions":                    random.randint(30, 2000),
                "avg_engagement_time_seconds": round(random.uniform(30, 300), 1),
            }
        elif platform == "email":
            return {
                "open_rate":    round(random.uniform(0.10, 0.55), 3),
                "click_rate":   round(random.uniform(0.01, 0.15), 3),
                "unsubscribes": random.randint(0, 10),
            }
        else:
            logger.warning(f"fetch_metrics: unknown platform | platform={platform}")
            return {}
    except Exception as exc:
        logger.error(f"fetch_metrics: error | platform={platform} | err={exc}")
        return {}


def calculate_performance_score(platform: str, metrics: dict) -> float:
    """
    Calculate a 0–10 performance score from engagement metrics.

    Each platform uses its primary engagement signals.
    Returns 0.0 for unknown platforms or when impressions are zero.
    Never raises.
    """
    try:
        if platform == "linkedin":
            impressions = metrics.get("impressions", 0)
            if impressions == 0:
                return 0.0
            engagement = (
                metrics.get("reactions", 0)
                + metrics.get("comments", 0) * 2
                + metrics.get("shares", 0) * 3
            )
            rate = engagement / impressions
            return round(min(10.0, rate * 100), 2)

        elif platform == "twitter":
            impressions = metrics.get("impressions", 0)
            if impressions == 0:
                return 0.0
            engagement = (
                metrics.get("likes", 0)
                + metrics.get("retweets", 0) * 2
                + metrics.get("bookmarks", 0)
            )
            rate = engagement / impressions
            return round(min(10.0, rate * 100), 2)

        elif platform == "blog":
            page_views = metrics.get("page_views", 0)
            if page_views == 0:
                return 0.0
            avg_time = metrics.get("avg_engagement_time_seconds", 0)
            # Score: 5 for >60s average time, 10 for >300s
            time_score = min(10.0, avg_time / 30.0)
            return round(time_score, 2)

        elif platform == "email":
            open_rate = metrics.get("open_rate", 0.0)
            click_rate = metrics.get("click_rate", 0.0)
            # Industry average open rate ~20%, click rate ~2.5%
            score = (open_rate / 0.20) * 5 + (click_rate / 0.025) * 5
            return round(min(10.0, score), 2)

        else:
            return 0.0

    except Exception as exc:
        logger.error(f"calculate_performance_score: error | platform={platform} | err={exc}")
        return 0.0
