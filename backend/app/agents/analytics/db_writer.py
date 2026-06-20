"""
DB write operations for the analytics agent.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.orm import ContentAnalytics, StyleGuide
from app.utils.logging import get_logger

logger = get_logger(__name__)


def write_analytics(
    db: Session,
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
        row = ContentAnalytics(
            post_id=post_id,
            platform=platform,
            measurement_period=measurement_period,
            metrics=metrics,
            performance_score=performance_score,
        )
        db.add(row)
        db.commit()
        return str(row.id)
    except Exception as exc:
        db.rollback()
        logger.error(f"write_analytics: failed | post_id={post_id} | period={measurement_period} | err={exc}")
        return None


def update_style_guide(db: Session, platform: str, performance_score: float) -> None:
    """
    Update the style_guide for the platform based on the latest 7d performance.

    Read-then-write in one transaction: fetches the existing row, updates
    top_performing data. Creates a new record if none exists. Never raises.
    """
    try:
        row = db.execute(select(StyleGuide).where(StyleGuide.platform == platform)).scalar_one_or_none()

        if row is not None:
            current_insights = row.insights or {}
            scores = current_insights.get("recent_scores", [])
            scores.append(round(performance_score, 2))
            scores = scores[-30:]  # keep last 30 scores
            avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
            row.insights = {
                **current_insights,
                "recent_scores": scores,
                "avg_score_30d": avg_score,
                "last_updated_by": "analytics_agent",
            }
        else:
            db.add(StyleGuide(
                platform=platform,
                insights={
                    "recent_scores": [round(performance_score, 2)],
                    "avg_score_30d": round(performance_score, 2),
                    "last_updated_by": "analytics_agent",
                },
            ))
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"update_style_guide: failed | platform={platform} | err={exc}")
