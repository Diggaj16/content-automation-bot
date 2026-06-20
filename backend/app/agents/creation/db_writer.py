"""
DB write operations for the creation agent.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DraftCreate
from app.db.orm import CostLog, Draft
from app.utils.logging import get_logger

logger = get_logger(__name__)


def write_draft(db: Session, draft_create: DraftCreate) -> Optional[str]:
    """
    Insert a new draft into the drafts table.
    Returns the new draft UUID string on success, or None on failure. Never raises.
    """
    try:
        row = Draft(
            platform=draft_create.platform.value,
            content_text=draft_create.content_text,
            target_persona=draft_create.target_persona,
            compliance_status=draft_create.compliance_status,
            agent_reasoning=draft_create.agent_reasoning,
            source_idea_id=draft_create.source_idea_id,
            finance_flags=[f.model_dump() for f in draft_create.finance_flags],
            suggested_publish_time=draft_create.suggested_publish_time,
        )
        db.add(row)
        db.commit()
        return str(row.id)
    except Exception as exc:
        db.rollback()
        logger.error(f"write_draft: failed | err={exc}")
        return None


def upsert_cost_log(db: Session, agent_name: str, total_usd: float, token_count: int) -> None:
    """
    Accumulate daily cost for cost_log table.
    Read-then-write in one transaction. Never raises.
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
        logger.error(f"upsert_cost_log: failed | agent={agent_name} | err={exc}")
