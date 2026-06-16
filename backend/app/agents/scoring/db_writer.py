"""
DB write helpers for the scoring agent.

All functions are synchronous (supabase-py). Never raise.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from supabase import Client

from app.db.client import table_has_column
from app.db.models import IdeaCreate
from app.utils.logging import get_logger

logger = get_logger(__name__)


def write_ideas(
    supabase: Client,
    ideas: list[IdeaCreate],
    article_id: UUID,
    publication_date: Optional[datetime],
) -> list[str]:
    """
    INSERT each idea into the ideas table one by one.

    Returns a list of created row UUIDs. If an individual idea fails,
    it is skipped and the loop continues — partial success is acceptable.
    """
    if not ideas:
        return []

    created_ids: list[str] = []
    pub_date_iso = publication_date.isoformat() if publication_date else None

    for idea in ideas:
        payload = {
            "platform":             idea.platform.value,
            "angle":                idea.angle,
            "source_article_id":    str(article_id),
            "agent_reasoning":      idea.agent_reasoning,
            "source_article_date":  pub_date_iso,
            "score":                idea.score,
            "recent_coverage_flag": idea.recent_coverage_flag,
        }
        # target_persona only exists after migration 005 — include it when present.
        if table_has_column("ideas", "target_persona"):
            payload["target_persona"] = idea.target_persona
        try:
            resp = supabase.table("ideas").insert(payload).execute()
            if resp.data:
                created_ids.append(resp.data[0]["id"])
            else:
                logger.warning("write_ideas: insert returned no data", extra={"angle": idea.angle})
        except Exception as exc:
            logger.warning(
                "write_ideas: failed to insert idea",
                extra={"angle": idea.angle, "error": str(exc)},
            )

    return created_ids


def mark_article_processed(supabase: Client, article_id: UUID) -> None:
    """Mark a raw_content row as processed=True. Never raises."""
    try:
        supabase.table("raw_content").update({"processed": True}).eq(
            "id", str(article_id)
        ).execute()
    except Exception as exc:
        logger.warning(
            "mark_article_processed failed",
            extra={"article_id": str(article_id), "error": str(exc)},
        )


def upsert_cost_log(
    supabase: Client,
    agent_name: str,
    total_usd: float,
    token_count: int,
) -> None:
    """
    Increment today's cost_log row for this agent (or create if not present).
    Read-then-write pattern. Safe for single-process arq workers.
    """
    today = str(datetime.now(timezone.utc).date())
    try:
        existing = (
            supabase.table("cost_log")
            .select("id, token_count, estimated_cost_usd")
            .eq("agent_name", agent_name)
            .eq("date", today)
            .limit(1)
            .execute()
        )
        if existing.data:
            row = existing.data[0]
            supabase.table("cost_log").update({
                "token_count":        row["token_count"] + token_count,
                "estimated_cost_usd": round(row["estimated_cost_usd"] + total_usd, 6),
            }).eq("id", row["id"]).execute()
        else:
            supabase.table("cost_log").insert({
                "agent_name":         agent_name,
                "date":               today,
                "token_count":        token_count,
                "estimated_cost_usd": round(total_usd, 6),
            }).execute()
    except Exception as exc:
        logger.warning("upsert_cost_log failed", extra={"agent": agent_name, "error": str(exc)})
