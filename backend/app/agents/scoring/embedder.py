"""
Voyage AI text embedder for the scoring agent.

Usage:
    import voyageai
    vo = voyageai.Client(api_key=settings.voyage_api_key)
    embedding = embed_text(article.full_text, vo)
    # embedding: list[float] of length 1024, or [] if Voyage is unavailable
"""
from __future__ import annotations

import voyageai

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Voyage model that produces 1024-dimensional embeddings.
# This constant is exported so tests can reference it without hard-coding the string.
_EMBEDDING_MODEL = "voyage-3"


def embed_text(text: str, voyage_client: voyageai.Client) -> list[float]:
    """
    Embed a single text string using Voyage AI.

    Returns a list of 1024 floats on success, or an empty list on any failure.
    Never raises — callers treat [] as "embedding unavailable".
    """
    try:
        result = voyage_client.embed([text], model=_EMBEDDING_MODEL, input_type="document")
        return result.embeddings[0]
    except Exception as exc:
        logger.warning("embed_text failed", extra={"error": str(exc)})
        return []
