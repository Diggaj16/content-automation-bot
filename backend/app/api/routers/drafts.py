"""
Gate 2 — Drafts approval router.

GET  /drafts             — list drafts with pagination (newest first)
PATCH /drafts/{draft_id} — approve or reject a draft, optionally with edited content + schedule
"""
import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import DraftApproval, DraftStatus
from app.db.orm import Draft, Idea, RawContent
from app.utils.logging import get_logger

router = APIRouter(prefix="/drafts", tags=["Gate 2 — Drafts"])

logger = get_logger(__name__)


def _draft_to_dict(draft: Draft) -> dict:
    return {
        "id": str(draft.id),
        "platform": draft.platform,
        "content_text": draft.content_text,
        "target_persona": draft.target_persona,
        "compliance_status": draft.compliance_status,
        "agent_reasoning": draft.agent_reasoning,
        "source_idea_id": str(draft.source_idea_id) if draft.source_idea_id else None,
        "finance_flags": draft.finance_flags,
        "suggested_publish_time": draft.suggested_publish_time,
        "scheduled_at": draft.scheduled_at,
        "approval_status": draft.approval_status,
        "created_at": draft.created_at,
        "updated_at": draft.updated_at,
    }


_ARTICLE_FIELDS = (
    "id", "url", "title", "source_name", "publication_date", "full_text",
    "structured_summary", "word_count", "pre_score", "vision_fallback_used", "paywall_detected",
)


def _article_to_dict(article: RawContent) -> dict:
    return {f: getattr(article, f) for f in _ARTICLE_FIELDS}


def _attach_source_articles(db: Session, drafts: list[dict]) -> None:
    """
    Populate each draft's `source_article` by following draft.source_idea_id ->
    ideas.source_article_id -> raw_content. Mutates drafts in place; never raises.
    Drafts with no resolvable article get source_article=None.
    """
    for d in drafts:
        d["source_article"] = None
    try:
        idea_ids = list({d["source_idea_id"] for d in drafts if d.get("source_idea_id")})
        if not idea_ids:
            return

        # idea_id -> source_article_id
        idea_rows = db.execute(
            select(Idea.id, Idea.source_article_id).where(Idea.id.in_(idea_ids))
        ).all()
        article_id_by_idea = {str(r.id): r.source_article_id for r in idea_rows if r.source_article_id}
        if not article_id_by_idea:
            return

        article_ids = list(set(article_id_by_idea.values()))
        articles = db.execute(select(RawContent).where(RawContent.id.in_(article_ids))).scalars().all()
        articles_by_id = {a.id: _article_to_dict(a) for a in articles}

        for d in drafts:
            article_id = article_id_by_idea.get(d.get("source_idea_id"))
            if article_id:
                d["source_article"] = articles_by_id.get(article_id)
    except Exception as exc:
        logger.warning("_attach_source_articles failed", extra={"error": str(exc)})


@router.get("")
def list_drafts(
    status: Optional[str] = Query(
        default=DraftStatus.PENDING.value,
        description="Filter by approval_status. Pass empty string to skip filter.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Return drafts with pagination, newest first.

    Response shape:
    {
        "data": [...],      # list of draft records
        "total": 127,       # total matching records
        "page": 1,          # current page
        "limit": 50,        # items per page
        "total_pages": 3    # ceil(total / limit)
    }
    """
    try:
        count_stmt = select(func.count()).select_from(Draft)
        if status:
            count_stmt = count_stmt.where(Draft.approval_status == status)
        total = db.execute(count_stmt).scalar_one()

        offset = (page - 1) * limit
        query = select(Draft).order_by(Draft.created_at.desc()).offset(offset).limit(limit)
        if status:
            query = query.where(Draft.approval_status == status)
        drafts_rows = db.execute(query).scalars().all()
        drafts = [_draft_to_dict(d) for d in drafts_rows]

        # Attach the scraped source article via draft -> idea -> raw_content (two-hop join)
        _attach_source_articles(db, drafts)

        return {
            "data": drafts,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": max(1, math.ceil(total / limit)) if total > 0 else 1,
        }
    except Exception as exc:
        logger.warning("list_drafts failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{draft_id}")
def approve_draft(
    draft_id: UUID,
    payload: DraftApproval,
    db: Session = Depends(get_db),
) -> dict:
    """Approve or reject a draft. Optionally supply edited content_text and/or scheduled_at."""
    try:
        draft = db.get(Draft, draft_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="Draft not found")

        draft.approval_status = payload.approval_status
        if payload.content_text is not None:
            draft.content_text = payload.content_text
        if payload.scheduled_at is not None:
            draft.scheduled_at = payload.scheduled_at
        db.commit()
        return _draft_to_dict(draft)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.warning("approve_draft failed", extra={"draft_id": str(draft_id), "error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")
