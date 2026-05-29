"""
DB write operations for the publishing agent.
"""
from typing import Optional
from uuid import UUID

from app.utils.logging import get_logger

logger = get_logger(__name__)


def write_published_post(
    supabase,
    platform: str,
    post_identifier: str,
    draft_id: Optional[UUID],
) -> Optional[str]:
    """
    Insert a record into published_posts.
    Returns the new post UUID string on success, or None on failure. Never raises.
    """
    try:
        payload = {
            "platform":        platform,
            "post_identifier": post_identifier,
            "draft_id":        str(draft_id) if draft_id else None,
        }
        resp = supabase.table("published_posts").insert(payload).execute()
        if not resp.data:
            logger.warning("write_published_post: insert returned no data")
            return None
        return resp.data[0]["id"]
    except Exception as exc:
        logger.error(f"write_published_post: failed | platform={platform} | err={exc}")
        return None


def update_draft_published(supabase, draft_id: UUID) -> None:
    """
    Set the draft's approval_status to 'published'. Never raises.
    """
    try:
        supabase.table("drafts").update(
            {"approval_status": "published"}
        ).eq("id", str(draft_id)).execute()
    except Exception as exc:
        logger.error(f"update_draft_published: failed | id={draft_id} | err={exc}")
