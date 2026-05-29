"""
DB write operations for the analytics agent.
"""
from typing import Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)


def write_analytics(
    supabase,
    post_id: str,
    platform: str,
    measurement_period: str,
    metrics: dict,
    performance_score: float,
) -> Optional[str]:
    """
    Insert a content_analytics row.
    Returns the new record UUID string on success, or None on failure. Never raises.
    """
    try:
        payload = {
            "post_id":            post_id,
            "platform":           platform,
            "measurement_period": measurement_period,
            "metrics":            metrics,
            "performance_score":  performance_score,
        }
        resp = supabase.table("content_analytics").insert(payload).execute()
        if not resp.data:
            logger.warning("write_analytics: insert returned no data")
            return None
        return resp.data[0]["id"]
    except Exception as exc:
        logger.error(f"write_analytics: failed | post_id={post_id} | period={measurement_period} | err={exc}")
        return None


def update_style_guide(supabase, platform: str, performance_score: float) -> None:
    """
    Update the style_guide for the platform based on the latest 7d performance.

    Uses read-then-write: fetches the existing row, updates top_performing data.
    Creates a new record if none exists. Never raises.
    """
    try:
        existing = (
            supabase.table("style_guide")
            .select("*")
            .eq("platform", platform)
            .execute()
        )

        if existing.data:
            row = existing.data[0]
            current_insights = row.get("insights") or {}
            # Increment insights with this performance data point
            scores = current_insights.get("recent_scores", [])
            scores.append(round(performance_score, 2))
            # Keep last 30 scores
            scores = scores[-30:]
            avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
            updated_insights = {
                **current_insights,
                "recent_scores":    scores,
                "avg_score_30d":    avg_score,
                "last_updated_by":  "analytics_agent",
            }
            supabase.table("style_guide").update(
                {"insights": updated_insights}
            ).eq("platform", platform).execute()
        else:
            initial_insights = {
                "recent_scores":   [round(performance_score, 2)],
                "avg_score_30d":   round(performance_score, 2),
                "last_updated_by": "analytics_agent",
            }
            supabase.table("style_guide").insert(
                {"platform": platform, "insights": initial_insights}
            ).execute()

    except Exception as exc:
        logger.error(f"update_style_guide: failed | platform={platform} | err={exc}")
