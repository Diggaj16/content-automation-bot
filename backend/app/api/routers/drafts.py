"""
Gate 2 — Drafts approval router.

GET  /drafts             — list drafts filtered by approval_status (default: pending_approval)
PATCH /drafts/{draft_id} — approve or reject a draft, optionally with edited content + schedule
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.api.deps import get_supabase
from app.db.models import DraftApproval, DraftStatus

router = APIRouter(prefix="/drafts", tags=["Gate 2 — Drafts"])


@router.get("")
def list_drafts(
    status: Optional[str] = Query(
        default=DraftStatus.PENDING.value,
        description="Filter by approval_status. Pass empty string to skip filter.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    supabase: Client = Depends(get_supabase),
) -> list[dict]:
    """Return drafts filtered by approval status."""
    try:
        query = supabase.table("drafts").select("*").limit(limit)
        if status:
            query = query.eq("approval_status", status)
        resp = query.execute()
        return resp.data or []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/{draft_id}")
def approve_draft(
    draft_id: UUID,
    payload: DraftApproval,
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Approve or reject a draft. Optionally supply edited content_text and/or scheduled_at."""
    update: dict = {"approval_status": payload.approval_status.value}
    if payload.content_text is not None:
        update["content_text"] = payload.content_text
    if payload.scheduled_at is not None:
        update["scheduled_at"] = payload.scheduled_at.isoformat()

    try:
        resp = (
            supabase.table("drafts")
            .update(update)
            .eq("id", str(draft_id))
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=404, detail="Draft not found")
        return resp.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
