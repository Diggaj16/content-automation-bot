"""
Gate 1 — Ideas approval router.

GET  /ideas            — list ideas with source article data joined
PATCH /ideas/{idea_id} — approve or reject an idea, optionally with an edited angle
"""
from typing import Optional
from uuid import UUID

from anthropic import Anthropic
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from supabase import Client

from app.api.deps import get_supabase, get_settings
from app.config import Settings
from app.db.models import ApprovalStatus, IdeaApproval
from app.utils.logging import get_logger

router = APIRouter(prefix="/ideas", tags=["Gate 1 — Ideas"])

logger = get_logger(__name__)


@router.get("")
def list_ideas(
    status: Optional[str] = Query(
        default=ApprovalStatus.PENDING.value,
        description="Filter by approval_status. Pass empty string to skip filter.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    supabase: Client = Depends(get_supabase),
) -> list[dict]:
    """Return ideas with their source article scraped data joined."""
    try:
        query = supabase.table("ideas").select("*").limit(limit)
        if status:
            query = query.eq("approval_status", status)
        resp = query.execute()
        ideas = resp.data or []

        article_ids = list({
            i["source_article_id"]
            for i in ideas
            if i.get("source_article_id")
        })

        articles_by_id: dict[str, dict] = {}
        if article_ids:
            art_resp = (
                supabase.table("raw_content")
                .select("id, url, title, source_name, publication_date, full_text, structured_summary, word_count, pre_score, vision_fallback_used, paywall_detected")
                .in_("id", article_ids)
                .execute()
            )
            for a in (art_resp.data or []):
                articles_by_id[a["id"]] = a

        for idea in ideas:
            aid = idea.get("source_article_id")
            idea["source_article"] = articles_by_id.get(aid) if aid else None

        return ideas
    except Exception as exc:
        logger.warning("list_ideas failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{idea_id}")
async def approve_idea(
    idea_id: UUID,
    payload: IdeaApproval,
    background_tasks: BackgroundTasks, 
    supabase: Client = Depends(get_supabase),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Approve or reject an idea. Optionally supply an edited_angle."""
    update: dict = {"approval_status": payload.approval_status}
    if payload.edited_angle is not None:
        update["edited_angle"] = payload.edited_angle

    try:
        resp = (
            supabase.table("ideas")
            .update(update)
            .eq("id", str(idea_id))
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Idea not found")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("approve_idea failed", extra={"idea_id": str(idea_id), "error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")

    if payload.approval_status == ApprovalStatus.REJECTED:
        background_tasks.add_task(_maybe_generate_summary,supabase, settings)

    return resp.data[0]


def _maybe_generate_summary(supabase: Client, settings: Settings) -> None:
    """
    If unsummarized rejections >= rejection_batch_size, generate and store a summary.
    Failures are silently logged — never propagated to the caller.
    """
    from app.agents.scoring.decision_summary import (
        count_unsummarized_rejections,
        fetch_recent_rejections,
        generate_decision_summary,
        write_summary,
    )
    log = get_logger(__name__)
    try:
        count, since_ts = count_unsummarized_rejections(supabase)
        if count < settings.rejection_batch_size:
            return
        rejected = fetch_recent_rejections(supabase, since_ts, count)
        client = Anthropic(api_key=settings.anthropic_api_key)
        summary = generate_decision_summary(rejected, client, settings.claude_model_light)
        write_summary(supabase, summary, count)
        log.info("_maybe_generate_summary: wrote summary", extra={"rejection_count": count})
    except Exception as exc:
        log.warning("_maybe_generate_summary failed", extra={"error": str(exc)})
