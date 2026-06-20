"""
DB write helpers for the research agent.

All functions are synchronous (SQLAlchemy). Call from async arq tasks via
asyncio.to_thread, or directly if already on a worker thread.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.agents.research.extractor import ArticleContent
from app.db.models import StructuredSummary
from app.db.orm import CostLog, CuratedSite, RawContent, SiteHealthLog
from app.utils.logging import get_logger

logger = get_logger(__name__)


def upsert_raw_content(
    db: Session,
    content: ArticleContent,
    summary: StructuredSummary,
    pre_score: float,
    source_name: str = "",
) -> Optional[str]:
    """
    INSERT a new row into raw_content.

    Returns the UUID string of the created row, or None on failure.
    The caller should not retry on None — the pipeline continues without this article.
    """
    payload: dict = {
        "url":                  content.url,
        "normalized_url":       content.normalized_url,
        "title":                content.title,
        "source_name":          source_name,
        "full_text":            content.full_text,
        "word_count":           content.word_count,
        "pre_score":            pre_score,
        "structured_summary":   summary.model_dump(),
        "vision_fallback_used": False,
        "paywall_detected":     content.paywall_detected,
    }
    if content.publication_date:
        payload["publication_date"] = content.publication_date

    try:
        # ON CONFLICT on normalized_url so that if the same article URL reaches
        # this point twice (race condition, is_url_seen DB error, etc.) Postgres
        # updates the existing row instead of raising a unique violation.
        stmt = (
            pg_insert(RawContent)
            .values(**payload)
            .on_conflict_do_update(index_elements=["normalized_url"], set_=payload)
            .returning(RawContent.id)
        )
        row = db.execute(stmt).first()
        db.commit()
        if not row:
            logger.warning("upsert_raw_content: upsert returned empty data", extra={"url": content.url})
            return None
        article_id = str(row[0])
        logger.info("upsert_raw_content: stored", extra={"id": article_id, "url": content.url})
        return article_id
    except Exception as exc:
        db.rollback()
        logger.warning("upsert_raw_content failed", extra={"url": content.url, "error": str(exc)})
        return None


def record_site_success(db: Session, site_id: UUID) -> None:
    """
    Reset consecutive_failures to 0, set last_run_at to now, insert success health log row.
    """
    now = datetime.now(timezone.utc)
    try:
        site = db.get(CuratedSite, site_id)
        if site is None:
            return
        site.consecutive_failures = 0
        site.last_run_at = now
        db.add(SiteHealthLog(site_id=site_id, success=True))
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("record_site_success failed", extra={"site_id": str(site_id), "error": str(exc)})


def record_site_failure(
    db: Session,
    site_id: UUID,
    error: str,
    failure_threshold: int,
) -> bool:
    """
    Increment consecutive_failures. Deactivate the site if failures >= threshold.

    Returns True if the site was deactivated (so the caller can log it).
    """
    deactivated = False
    try:
        site = db.get(CuratedSite, site_id)
        if site is None:
            return False

        new_failures = site.consecutive_failures + 1
        site.consecutive_failures = new_failures
        if new_failures >= failure_threshold:
            site.active = False
            deactivated = True
            logger.warning(
                "record_site_failure: site deactivated",
                extra={"site_id": str(site_id), "failures": new_failures},
            )

        db.add(SiteHealthLog(site_id=site_id, success=False, error_message=error[:500]))
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("record_site_failure failed", extra={"site_id": str(site_id), "error": str(exc)})
        deactivated = False  # DB write may not have completed; don't report deactivation that didn't happen

    return deactivated


def upsert_cost_log(
    db: Session,
    agent_name: str,
    total_usd: float,
    token_count: int,
) -> None:
    """
    Increment today's cost_log row for this agent (or create it if not present).

    Read-then-write inside one transaction. Safe for single-process arq workers.
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
