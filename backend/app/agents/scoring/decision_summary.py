"""
Generates rejection pattern summaries from Gate 1 idea rejections.
Called by the ideas router after each rejection when the unsummarized count
reaches REJECTION_BATCH_SIZE.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from anthropic import Anthropic
from supabase import Client

from app.utils.logging import get_logger

logger = get_logger(__name__)


def count_unsummarized_rejections(supabase: Client) -> tuple[int, Optional[datetime]]:
    """
    Return (count, since_ts) where count is rejections after the last summary
    and since_ts is that summary's timestamp (None if no summary exists yet).
    """
    try:
        last = (
            supabase.table("user_decision_summaries")
            .select("created_at")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        since_ts: Optional[datetime] = None
        if last.data:
            since_ts = datetime.fromisoformat(last.data[0]["created_at"])

        query = (
            supabase.table("ideas")
            .select("id", count="exact")
            .eq("approval_status", "rejected")
        )
        if since_ts:
            query = query.gt("updated_at", since_ts.isoformat())

        resp = query.execute()
        return (resp.count or 0), since_ts
    except Exception as exc:
        logger.warning("count_unsummarized_rejections failed", extra={"error": str(exc)})
        return 0, None


_MAX_FETCH_LIMIT = 200  # Safety cap so the first-ever run never pulls unbounded history


def fetch_recent_rejections(
    supabase: Client,
    since_ts: Optional[datetime],
    limit: int,
) -> list[dict]:
    """Fetch recently rejected ideas returning angle, platform, agent_reasoning.

    The limit is capped at _MAX_FETCH_LIMIT so the first-ever summary run
    (no since_ts) cannot pull the entire historical rejection log into the
    Claude prompt.
    """
    try:
        query = (
            supabase.table("ideas")
            .select("angle, platform, agent_reasoning")
            .eq("approval_status", "rejected")
            .order("updated_at", desc=True)
            .limit(min(limit, _MAX_FETCH_LIMIT))
        )
        if since_ts:
            query = query.gt("updated_at", since_ts.isoformat())
        resp = query.execute()
        return resp.data or []
    except Exception as exc:
        logger.warning("fetch_recent_rejections failed", extra={"error": str(exc)})
        return []


def generate_decision_summary(
    rejected_ideas: list[dict],
    client: Anthropic,
    model: str,
) -> str:
    """
    Call Claude Haiku to write a 2-3 sentence rejection pattern summary.
    Returns empty string on failure or empty input — never raises.
    """
    if not rejected_ideas:
        return ""

    ideas_text = "\n".join(
        f"- [{r.get('platform', '?')}] {r.get('angle', '')}"
        for r in rejected_ideas
    )

    try:
        message = client.messages.create(
            model=model,
            max_tokens=256,
            system=(
                "You analyse rejected content ideas for an Indian finance newsletter. "
                "Identify common patterns in what gets rejected and write a short summary "
                "to help an AI agent understand what kind of ideas to avoid. "
                "Be specific: mention angle types, platforms, and topic patterns. "
                "Write 2-3 sentences only."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"These {len(rejected_ideas)} ideas were recently rejected:\n\n"
                    f"{ideas_text}\n\n"
                    "Summarise the rejection patterns in 2-3 sentences."
                ),
            }],
        )
        return message.content[0].text.strip() if message.content else ""
    except Exception as exc:
        logger.warning("generate_decision_summary: Claude call failed", extra={"error": str(exc)})
        return ""


def write_summary(supabase: Client, summary_text: str, rejection_count: int) -> None:
    """Insert a row into user_decision_summaries. Never raises."""
    if not summary_text:
        return
    try:
        supabase.table("user_decision_summaries").insert({
            "summary_text": summary_text,
            "rejection_count": rejection_count,
        }).execute()
    except Exception as exc:
        logger.warning("write_summary failed", extra={"error": str(exc)})
