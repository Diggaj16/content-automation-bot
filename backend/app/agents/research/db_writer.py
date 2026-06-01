"""
DB write helpers for the research agent.

All functions are synchronous (supabase-py). Call from async arq tasks directly —
each is a single fast HTTP call to Supabase.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from supabase import Client

from app.agents.research.extractor import ArticleContent
from app.db.models import StructuredSummary
from app.utils.logging import get_logger

logger = get_logger(__name__)


def upsert_raw_content(
    supabase: Client,
    content: ArticleContent,
    summary: StructuredSummary,
    pre_score: float,
    source_name: str = "",
) -> Optional[str]:
    """
    INSERT a new row into raw_content.

    Returns the UUID string of the created row, or None on failure.
    The caller should not retry on None — the pipeline continues without this article.
    """
    payload = {
        "url":                  content.url,
        "normalized_url":       content.normalized_url,
        "title":                content.title,
        "source_name":          source_name,
        "full_text":            content.full_text,
        "word_count":           content.word_count,
        "pre_score":            pre_score,
        "structured_summary":   summary.model_dump(),
        "vision_fallback_used": False,
        "paywall_detected":     content.paywall_detected,
    }
    if content.publication_date:
        payload["publication_date"] = content.publication_date.isoformat()

    try:
        # Use upsert with ON CONFLICT on normalized_url so that if the same article
        # URL reaches this point twice (race condition, is_url_seen DB error, etc.)
        # Postgres updates the existing row instead of raising a unique violation.
        resp = (
            supabase.table("raw_content")
            .upsert(payload, on_conflict="normalized_url")
            .execute()
        )
        if not resp.data:
            logger.warning("upsert_raw_content: upsert returned empty data", extra={"url": content.url})
            return None
        article_id: str = resp.data[0]["id"]
        logger.info("upsert_raw_content: stored", extra={"id": article_id, "url": content.url})
        return article_id
    except Exception as exc:
        logger.warning("upsert_raw_content failed", extra={"url": content.url, "error": str(exc)})
        return None


def record_site_success(supabase: Client, site_id: UUID) -> None:
    """
    Reset consecutive_failures to 0, set last_run_at to now, insert success health log row.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        supabase.table("curated_sites").update({
            "consecutive_failures": 0,
            "last_run_at": now_iso,
        }).eq("id", str(site_id)).execute()

        supabase.table("site_health_log").insert({
            "site_id": str(site_id),
            "success": True,
        }).execute()
    except Exception as exc:
        logger.warning("record_site_success failed", extra={"site_id": str(site_id), "error": str(exc)})


def record_site_failure(
    supabase: Client,
    site_id: UUID,
    error: str,
    failure_threshold: int,
) -> bool:
    """
    Increment consecutive_failures. Deactivate the site if failures >= threshold.

    Returns True if the site was deactivated (so the caller can log it).
    """
    deactivated = False
    try:
        # Read current failure count
        resp = supabase.table("curated_sites").select("id, consecutive_failures").eq("id", str(site_id)).limit(1).execute()
        if not resp.data:
            return False

        current_failures = resp.data[0].get("consecutive_failures", 0)
        new_failures = current_failures + 1

        update_payload: dict = {"consecutive_failures": new_failures}
        if new_failures >= failure_threshold:
            update_payload["active"] = False
            deactivated = True
            logger.warning(
                "record_site_failure: site deactivated",
                extra={"site_id": str(site_id), "failures": new_failures},
            )

        supabase.table("curated_sites").update(update_payload).eq("id", str(site_id)).execute()

        supabase.table("site_health_log").insert({
            "site_id": str(site_id),
            "success": False,
            "error_message": error[:500],  # cap length
        }).execute()
    except Exception as exc:
        logger.warning("record_site_failure failed", extra={"site_id": str(site_id), "error": str(exc)})
        deactivated = False  # DB write may not have completed; don't report deactivation that didn't happen

    return deactivated


def upsert_cost_log(
    supabase: Client,
    agent_name: str,
    total_usd: float,
    token_count: int,
) -> None:
    """
    Increment today's cost_log row for this agent (or create it if not present).

    Uses read-then-write since supabase-py's .upsert() cannot do incremental
    arithmetic updates. Safe for single-process arq workers.
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
                "token_count": row["token_count"] + token_count,
                "estimated_cost_usd": round(row["estimated_cost_usd"] + total_usd, 6),
            }).eq("id", row["id"]).execute()
        else:
            supabase.table("cost_log").insert({
                "agent_name": agent_name,
                "date": today,
                "token_count": token_count,
                "estimated_cost_usd": round(total_usd, 6),
            }).execute()
    except Exception as exc:
        logger.warning("upsert_cost_log failed", extra={"agent": agent_name, "error": str(exc)})
