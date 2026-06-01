"""
Text embedding helpers used by the scoring and creation agents.

The underlying embedding client (Gemini or local fastembed) is constructed once
by the calling task and passed in — never constructed inside these helpers.

Usage:
    from app.agents.embedding.client import make_embed_client
    client = make_embed_client(google_api_key=settings.google_api_key,
                               local_model=settings.local_embedding_model)
    vector = embed_text("article text", client)
"""
from __future__ import annotations

from app.agents.embedding.client import EmbedClient
from app.utils.logging import get_logger

logger = get_logger(__name__)


def embed_text(text: str, embed_client: EmbedClient | None) -> list[float]:
    """
    Embed a single text string.

    Returns a list of floats (768-dim) on success, or [] if the client is
    None or embedding fails. Never raises — callers treat [] as "unavailable".
    """
    if embed_client is None:
        return []
    try:
        return embed_client.embed_one(text)
    except Exception as exc:
        logger.warning("embed_text failed", extra={"error": str(exc)})
        return []
