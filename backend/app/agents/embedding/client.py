"""
Unified embedding client: Gemini primary, local fastembed fallback.

Usage:
    from app.agents.embedding.client import make_embed_client
    client = make_embed_client(settings)
    vectors = client.embed(["text1", "text2", ...])    # batch → list[list[float]]
    vector  = client.embed_one("single text")          # single → list[float]

Both Gemini text-embedding-004 and fastembed BAAI/bge-base-en-v1.5 produce
768-dimensional vectors, so they are DB-compatible with each other and
interchangeable without any schema change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Shared output dimension for all embedders — must match vector(N) in the DB
EMBEDDING_DIMENSIONS = 768

# Module-level singleton for the local model: arq reuses the same process
# across multiple tasks, so we load the model once and keep it in memory.
_local_model_cache: dict[str, object] = {}


class EmbedClient(ABC):
    """Protocol for all embedding backends."""

    @abstractmethod
    def embed(self, texts: list[str], *, for_query: bool = False) -> list[list[float]]:
        """
        Embed a batch of texts. Returns list[list[float]] of length == len(texts).
        for_query=True uses query-optimised embedding (better recall for search).
        Never raises — returns empty sub-lists on individual failures.
        """
        ...

    def embed_one(self, text: str, *, for_query: bool = False) -> list[float]:
        """Convenience wrapper for single-text embedding."""
        results = self.embed([text], for_query=for_query)
        return results[0] if results else []


class GeminiEmbedder(EmbedClient):
    """
    Google gemini-embedding-001 (768 dims via output_dimensionality) via the
    google-genai SDK. text-embedding-004 (the older model) was retired and is
    no longer served — gemini-embedding-001 is the current replacement.
    Supports batches up to 100 texts per request.
    """

    _CHUNK_SIZE = 100  # Gemini batch limit

    def __init__(self, api_key: str, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        from google import genai  # google-genai package (not deprecated google-generativeai)
        self._client = genai.Client(api_key=api_key)
        self._dimensions = dimensions

    def embed(self, texts: list[str], *, for_query: bool = False) -> list[list[float]]:
        if not texts:
            return []
        task_type = "RETRIEVAL_QUERY" if for_query else "RETRIEVAL_DOCUMENT"
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self._CHUNK_SIZE):
            chunk = texts[i : i + self._CHUNK_SIZE]
            try:
                result = self._client.models.embed_content(
                    model="models/gemini-embedding-001",
                    contents=chunk,
                    config={
                        "task_type": task_type,
                        "output_dimensionality": self._dimensions,
                    },
                )
                # result.embeddings is a list of ContentEmbedding; each has .values
                all_embeddings.extend([e.values for e in result.embeddings])
            except Exception as exc:
                logger.warning(
                    "GeminiEmbedder.embed chunk failed",
                    extra={"chunk_start": i, "error": str(exc)},
                )
                all_embeddings.extend([[] for _ in chunk])
        return all_embeddings


class LocalEmbedder(EmbedClient):
    """
    fastembed with BAAI/bge-base-en-v1.5 (768 dims, ~430 MB download on first use).
    No API key required. Model is cached in ~/.cache/fastembed/ after first download.
    The model instance is a module-level singleton so it loads once per process.
    """

    def __init__(self, model_name: str = "BAAI/bge-base-en-v1.5") -> None:
        self._model_name = model_name
        self._model = self._load(model_name)

    @staticmethod
    def _load(model_name: str):
        if model_name not in _local_model_cache:
            from fastembed import TextEmbedding
            logger.info("Loading local embedding model", extra={"model": model_name})
            _local_model_cache[model_name] = TextEmbedding(model_name=model_name)
        return _local_model_cache[model_name]

    def embed(self, texts: list[str], *, for_query: bool = False) -> list[list[float]]:
        if not texts:
            return []
        # bge-base query mode: prepend the standard query prefix
        if for_query:
            texts = [
                f"Represent this sentence for searching relevant passages: {t}"
                for t in texts
            ]
        try:
            return [emb.tolist() for emb in self._model.embed(texts, batch_size=32)]
        except Exception as exc:
            logger.warning("LocalEmbedder.embed failed", extra={"error": str(exc)})
            return [[] for _ in texts]


class FallbackEmbedder(EmbedClient):
    """
    Tries primary; falls back to secondary on any failure.

    Partial failures (e.g. Gemini succeeds for chunk 1 but fails for chunk 2,
    returning a mix of valid and empty vectors) are treated as full failures —
    the entire batch is retried against the fallback so no empty vectors slip through.
    """

    def __init__(self, primary: EmbedClient, fallback: EmbedClient) -> None:
        self._primary = primary
        self._fallback = fallback

    def embed(self, texts: list[str], *, for_query: bool = False) -> list[list[float]]:
        try:
            results = self._primary.embed(texts, for_query=for_query)
            # Fail over if ANY vector is empty — partial failures are treated as full failures
            # so callers never receive a silently mixed valid/empty result.
            empty_count = sum(1 for v in results if not v)
            if empty_count:
                raise ValueError(f"primary returned {empty_count}/{len(results)} empty vector(s)")
            return results
        except Exception as exc:
            logger.warning(
                "FallbackEmbedder: primary failed, using local",
                extra={"error": str(exc)},
            )
            return self._fallback.embed(texts, for_query=for_query)


class NoOpEmbedder(EmbedClient):
    """Used when no API key and no local model available (graceful no-op)."""

    def embed(self, texts: list[str], *, for_query: bool = False) -> list[list[float]]:
        return [[] for _ in texts]


def make_embed_client(
    google_api_key: Optional[str] = None,
    local_model: str = "BAAI/bge-base-en-v1.5",
) -> EmbedClient:
    """
    Build the best available embedding client.

    Priority:
      1. If GOOGLE_API_KEY set → Gemini primary + local fallback
      2. If local fastembed importable → local only
      3. Else → no-op (embeddings disabled, vector features degrade gracefully)
    """
    local: Optional[EmbedClient] = None
    try:
        import fastembed  # noqa: F401 — just check availability
        local = LocalEmbedder(local_model)
    except ImportError:
        logger.warning(
            "fastembed not installed — local embedding fallback unavailable. "
            "Install with: pip install fastembed"
        )

    if google_api_key:
        gemini = GeminiEmbedder(google_api_key)
        if local:
            return FallbackEmbedder(primary=gemini, fallback=local)
        return gemini

    if local:
        return local

    logger.warning(
        "No embedding provider available (no GOOGLE_API_KEY, fastembed not installed). "
        "Brand context, KB search, and coverage checks will be disabled."
    )
    return NoOpEmbedder()
