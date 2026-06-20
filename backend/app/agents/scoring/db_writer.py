"""
DB write helpers for the scoring agent.

All functions are synchronous (SQLAlchemy). Never raise.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IdeaCreate
from app.db.orm import CostLog, Idea, RawContent
from app.utils.logging import get_logger

logger = get_logger(__name__)


def write_ideas(
    db: Session,
    ideas: list[IdeaCreate],
    article_id: UUID,
    publication_date: Optional[datetime],
) -> list[str]:
    """
    INSERT each idea into the ideas table one by one.

    Returns a list of created row UUIDs. If an individual idea fails,
    it is skipped and the loop continues — partial success is acceptable.
    """
    if not ideas:
        return []

    created_ids: list[str] = []

    for idea in ideas:
        try:
            row = Idea(
                platform=idea.platform.value,
                angle=idea.angle,
                target_persona=idea.target_persona,
                source_article_id=article_id,
                agent_reasoning=idea.agent_reasoning,
                source_article_date=publication_date,
                score=idea.score,
                recent_coverage_flag=idea.recent_coverage_flag,
            )
            db.add(row)
            db.commit()
            created_ids.append(str(row.id))
        except Exception as exc:
            db.rollback()
            logger.warning(
                "write_ideas: failed to insert idea",
                extra={"angle": idea.angle, "error": str(exc)},
            )

    return created_ids


def mark_article_processed(db: Session, article_id: UUID) -> None:
    """Mark a raw_content row as processed=True. Never raises."""
    try:
        article = db.get(RawContent, article_id)
        if article is not None:
            article.processed = True
            db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning(
            "mark_article_processed failed",
            extra={"article_id": str(article_id), "error": str(exc)},
        )


def upsert_cost_log(
    db: Session,
    agent_name: str,
    total_usd: float,
    token_count: int,
) -> None:
    """
    Increment today's cost_log row for this agent (or create if not present).
    Read-then-write pattern in one transaction. Safe for single-process arq workers.
    """
    today = datetime.now(timezone.utc).date()
    try:
        row = db.execute(
            select(CostLog).where(CostLog.agent_name == agent_name, CostLog.date == today)
        ).scalar_one_or_none()
        if row is not None:
            row.token_count += token_count
            row.estimated_cost_usd = round(row.estimated_cost_usd + total_usd, 6)
        else:
            db.add(CostLog(
                agent_name=agent_name,
                date=today,
                token_count=token_count,
                estimated_cost_usd=round(total_usd, 6),
            ))
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("upsert_cost_log failed", extra={"agent": agent_name, "error": str(exc)})
