"""
Gate 1 — Ideas approval router.

GET  /ideas            — list ideas filtered by approval_status (default: pending_approval)
PATCH /ideas/{idea_id} — approve or reject an idea, optionally with an edited angle
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.api.deps import get_supabase
from app.db.models import ApprovalStatus, IdeaApproval

router = APIRouter(prefix="/ideas", tags=["Gate 1 — Ideas"])


@router.get("")
def list_ideas(
    status: Optional[str] = Query(
        default=ApprovalStatus.PENDING.value,
        description="Filter by approval_status. Pass empty string to skip filter.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    supabase: Client = Depends(get_supabase),
) -> list[dict]:
    """Return ideas filtered by approval status."""
    try:
        query = supabase.table("ideas").select("*").limit(limit)
        if status:
            query = query.eq("approval_status", status)
        resp = query.execute()
        return resp.data or []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/{idea_id}")
def approve_idea(
    idea_id: UUID,
    payload: IdeaApproval,
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Approve or reject an idea. Optionally supply an edited_angle."""
    update: dict = {"approval_status": payload.approval_status.value}
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
        return resp.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
