"""
Gate 1 — Ideas approval router.

GET  /ideas            — list ideas with source article data joined
PATCH /ideas/{idea_id} — approve or reject an idea, optionally with an edited angle
"""
from typing import Optional
from uuid import UUID

from anthropic import Anthropic
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings
from app.config import Settings
from app.db.models import ApprovalStatus, IdeaApproval
from app.db.orm import Idea, RawContent
from app.db.session import session_scope
from app.utils.logging import get_logger

router = APIRouter(prefix="/ideas", tags=["Gate 1 — Ideas"])

logger = get_logger(__name__)


def _idea_to_dict(idea: Idea) -> dict:
    return {
        "id": str(idea.id),
        "platform": idea.platform,
        "angle": idea.angle,
        "edited_angle": idea.edited_angle,
        "target_persona": idea.target_persona,
        "source_article_id": str(idea.source_article_id) if idea.source_article_id else None,
        "agent_reasoning": idea.agent_reasoning,
        "source_article_date": idea.source_article_date,
        "approval_status": idea.approval_status,
        "draft_status": idea.draft_status,
        "score": idea.score,
        "recent_coverage_flag": idea.recent_coverage_flag,
        "created_at": idea.created_at,
        "updated_at": idea.updated_at,
    }


def _article_to_dict(article: RawContent) -> dict:
    return {
        "id": str(article.id),
        "url": article.url,
        "title": article.title,
        "source_name": article.source_name,
        "publication_date": article.publication_date,
        "full_text": article.full_text,
        "structured_summary": article.structured_summary,
        "word_count": article.word_count,
        "pre_score": article.pre_score,
        "vision_fallback_used": article.vision_fallback_used,
        "paywall_detected": article.paywall_detected,
    }


@router.get("")
def list_ideas(
    status: Optional[str] = Query(
        default=ApprovalStatus.PENDING.value,
        description="Filter by approval_status. Pass empty string to skip filter.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
) -> dict:
    """Return ideas with their source article scraped data joined, newest first."""
    try:
        offset = (page - 1) * limit

        query = db.query(Idea)
        if status:
            query = query.filter(Idea.approval_status == status)

        total = query.count()
        ideas = query.order_by(Idea.created_at.desc()).limit(limit).offset(offset).all()

        article_ids = list({i.source_article_id for i in ideas if i.source_article_id})

        articles_by_id: dict = {}
        if article_ids:
            articles = db.query(RawContent).filter(RawContent.id.in_(article_ids)).all()
            articles_by_id = {a.id: _article_to_dict(a) for a in articles}

        result = []
        for idea in ideas:
            d = _idea_to_dict(idea)
            d["source_article"] = articles_by_id.get(idea.source_article_id) if idea.source_article_id else None
            result.append(d)

        import math
        return {
            "data": result,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": max(1, math.ceil(total / limit)),
        }
    except Exception as exc:
        logger.warning("list_ideas failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{idea_id}")
async def approve_idea(
    idea_id: UUID,
    payload: IdeaApproval,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Approve or reject an idea. Optionally supply an edited_angle.

    Approving an idea discards its still-pending sibling ideas (same source
    article) outright — they lost to the chosen angle, not "rejected" by the
    user, so they're deleted rather than marked rejected and never feed the
    rejection-pattern summary.
    """
    discarded_siblings = 0
    try:
        idea = db.get(Idea, idea_id)
        if idea is None:
            raise HTTPException(status_code=404, detail="Idea not found")

        idea.approval_status = payload.approval_status
        if payload.edited_angle is not None:
            idea.edited_angle = payload.edited_angle

        if payload.approval_status == ApprovalStatus.APPROVED and idea.source_article_id:
            siblings = (
                db.query(Idea)
                .filter(
                    Idea.source_article_id == idea.source_article_id,
                    Idea.id != idea.id,
                    Idea.approval_status == ApprovalStatus.PENDING.value,
                )
                .all()
            )
            for sib in siblings:
                db.delete(sib)
            discarded_siblings = len(siblings)

        db.commit()
        result = _idea_to_dict(idea)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.warning("approve_idea failed", extra={"idea_id": str(idea_id), "error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")

    if payload.approval_status == ApprovalStatus.REJECTED:
        background_tasks.add_task(_maybe_generate_summary, settings)

    result["discarded_siblings"] = discarded_siblings
    return result


def _maybe_generate_summary(settings: Settings) -> None:
    """
    If unsummarized rejections >= rejection_batch_size, generate and store a summary.
    Failures are silently logged — never propagated to the caller.

    Opens its own DB session: this runs as a BackgroundTask after the response
    is sent, by which point the request-scoped `db` dependency has been closed.
    """
    from app.agents.scoring.decision_summary import (
        count_unsummarized_rejections,
        fetch_recent_rejections,
        generate_decision_summary,
        write_summary,
    )
    log = get_logger(__name__)
    try:
        with session_scope() as db:
            count, since_ts = count_unsummarized_rejections(db)
            if count < settings.rejection_batch_size:
                return
            rejected = fetch_recent_rejections(db, since_ts, count)
            client = Anthropic(api_key=settings.anthropic_api_key)
            summary = generate_decision_summary(rejected, client, settings.claude_model_light)
            write_summary(db, summary, count)
        log.info("_maybe_generate_summary: wrote summary", extra={"rejection_count": count})
    except Exception as exc:
        log.warning("_maybe_generate_summary failed", extra={"error": str(exc)})
