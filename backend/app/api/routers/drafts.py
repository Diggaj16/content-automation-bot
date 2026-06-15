"""
Gate 2 — Drafts approval router.

GET  /drafts             — list drafts with pagination (newest first)
PATCH /drafts/{draft_id} — approve or reject a draft, optionally with edited content + schedule
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.api.deps import get_supabase
from app.db.models import DraftApproval, DraftStatus
from app.utils.logging import get_logger

router = APIRouter(prefix="/drafts", tags=["Gate 2 — Drafts"])

logger = get_logger(__name__)


@router.get("")
def list_drafts(
    status: Optional[str] = Query(
        default=DraftStatus.PENDING.value,
        description="Filter by approval_status. Pass empty string to skip filter.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    supabase: Client = Depends(get_supabase),
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
        # Build the base query
        base_query = supabase.table("drafts")

        # Count total matching records
        count_query = base_query.select("id", count="exact")
        if status:
            count_query = count_query.eq("approval_status", status)
        count_resp = count_query.execute()
        # Supabase returns count in the response body for Python client
        total = len(count_resp.data) if count_resp.data else 0
        # Try to get the actual count from the response object
        if hasattr(count_resp, 'count') and count_resp.count is not None:
            total = count_resp.count

        # Get paginated results, newest first
        query = base_query.select("*")
        if status:
            query = query.eq("approval_status", status)
        offset = (page - 1) * limit
        resp = (
            query
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        import math
        return {
            "data": resp.data or [],
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
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Approve or reject a draft. Optionally supply edited content_text and/or scheduled_at."""
    update: dict = {"approval_status": payload.approval_status}
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
        logger.warning("approve_draft failed", extra={"draft_id": str(draft_id), "error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")