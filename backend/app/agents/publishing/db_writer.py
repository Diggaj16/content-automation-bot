"""
DB write operations for the publishing agent.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.orm import Draft, PublishedPost
from app.utils.logging import get_logger

logger = get_logger(__name__)


def write_published_post(
    db: Session,
    platform: str,
    post_identifier: str,
    draft_id: Optional[UUID],
) -> Optional[str]:
    """
    Insert a record into published_posts.
    Returns the new post UUID string on success, or None on failure. Never raises.
    """
    try:
        row = PublishedPost(platform=platform, post_identifier=post_identifier, draft_id=draft_id)
        db.add(row)
        db.commit()
        return str(row.id)
    except Exception as exc:
        db.rollback()
        logger.error(f"write_published_post: failed | platform={platform} | err={exc}")
        return None


def update_draft_published(db: Session, draft_id: UUID) -> None:
    """
    Set the draft's approval_status to 'published'. Never raises.
    """
    try:
        draft = db.get(Draft, draft_id)
        if draft is not None:
            draft.approval_status = "published"
            db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"update_draft_published: failed | id={draft_id} | err={exc}")
