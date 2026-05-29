"""
Brand context retrieval for content generation.

Calls the match_brand_memory Postgres RPC to find semantically similar
past published content, then formats it as a prompt context string.
"""
from typing import Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)


def get_brand_context(
    embedding: Optional[list[float]],
    platform: str,
    supabase,
    match_count: int = 5,
) -> str:
    """
    Retrieve relevant past brand content using vector similarity.

    Args:
        embedding:   Voyage AI embedding of the idea text (1024-dim).
                     Empty list or None → return "" immediately, no RPC called.
        platform:    Platform string used to filter brand_memory results.
        supabase:    Supabase client.
        match_count: Number of similar examples to retrieve (default 5).

    Returns:
        Formatted string of past content examples, or "" if none found.
        Never raises.
    """
    if not embedding:
        return ""

    try:
        resp = supabase.rpc(
            "match_brand_memory",
            {
                "query_embedding": embedding,
                "match_count": match_count,
                "filter_platform": platform,
            },
        ).execute()

        if not resp.data:
            return ""

        lines = [f"- {item['content']}" for item in resp.data]
        return "Past brand content examples:\n" + "\n".join(lines)

    except Exception as exc:
        logger.warning(f"get_brand_context: RPC failed | platform={platform} | err={exc}")
        return ""
