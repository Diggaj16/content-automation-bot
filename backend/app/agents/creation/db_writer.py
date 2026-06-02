"""
DB write operations for the creation agent.
"""
from typing import Optional

from app.db.models import DraftCreate
from app.utils.logging import get_logger

logger = get_logger(__name__)


def write_draft(supabase, draft_create: DraftCreate) -> Optional[str]:
    """
    Insert a new draft into the drafts table.
    Returns the new draft UUID string on success, or None on failure. Never raises.
    """
    try:
        payload = {
            "platform":               draft_create.platform.value,
            "content_text":           draft_create.content_text,
            "agent_reasoning":        draft_create.agent_reasoning,
            "source_idea_id":         str(draft_create.source_idea_id)
                                      if draft_create.source_idea_id else None,
            "finance_flags":          [f.model_dump() for f in draft_create.finance_flags],
            "suggested_publish_time": (
                draft_create.suggested_publish_time.isoformat()
                if draft_create.suggested_publish_time else None
            ),
        }
        resp = (
            supabase.table("drafts")
            .upsert(payload, on_conflict="source_idea_id,platform")
            .execute()
        )
        if not resp.data:
            logger.warning("write_draft: insert returned no data")
            return None
        return resp.data[0]["id"]
    except Exception as exc:
        logger.error(f"write_draft: failed | err={exc}")
        return None


def upsert_cost_log(supabase, agent_name: str, total_usd: float, token_count: int) -> None:
    """
    Accumulate daily cost for cost_log table.
    Read-then-write (supabase-py cannot do incremental upsert arithmetic). Never raises.
    """
    from datetime import date
    today = date.today().isoformat()
    try:
        existing = (
            supabase.table("cost_log")
            .select("token_count,estimated_cost_usd")
            .eq("agent_name", agent_name)
            .eq("date", today)
            .execute()
        )
        if existing.data:
            row = existing.data[0]
            new_tokens = row["token_count"] + token_count
            new_usd = row["estimated_cost_usd"] + total_usd
            supabase.table("cost_log").update(
                {"token_count": new_tokens, "estimated_cost_usd": round(new_usd, 6)}
            ).eq("agent_name", agent_name).eq("date", today).execute()
        else:
            supabase.table("cost_log").insert(
                {"agent_name": agent_name, "date": today,
                 "token_count": token_count, "estimated_cost_usd": round(total_usd, 6)}
            ).execute()
    except Exception as exc:
        logger.error(f"upsert_cost_log: failed | agent={agent_name} | err={exc}")
