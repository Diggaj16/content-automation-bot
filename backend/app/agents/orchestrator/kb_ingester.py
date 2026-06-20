"""
Knowledge base file ingestion: extract → chunk → embed → upsert.

Supports PDF (pdfplumber) and TXT (UTF-8) files.
Embedding is optional; pass embed_client=None to skip (chunks stored without vectors).
"""
from __future__ import annotations

import io

import pdfplumber
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.orm import KnowledgeBase
from app.utils.logging import get_logger

logger = get_logger(__name__)


def extract_text(filename: str, content_bytes: bytes) -> str:
    """
    Extract plain text from a PDF or TXT file.

    Raises ValueError for unsupported file types.
    """
    name_lower = filename.lower()
    if name_lower.endswith(".txt"):
        return content_bytes.decode("utf-8", errors="replace").strip()
    elif name_lower.endswith(".pdf"):
        try:
            pages = []
            with pdfplumber.open(io.BytesIO(content_bytes)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text.strip())
            return "\n\n".join(pages)
        except Exception as exc:
            raise ValueError(
                f"Cannot read PDF '{filename}': {exc}. "
                "The file may be encrypted, password-protected, or corrupted."
            ) from exc
    else:
        ext = filename.rsplit(".", 1)[-1] if "." in filename else filename
        raise ValueError(f"Unsupported file type: {ext}. Upload PDF or TXT.")


def chunk_text(
    text: str,
    max_words: int = 500,
    overlap_words: int = 50,
) -> list[str]:
    """
    Split text into overlapping word-based chunks.
    """
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    all_words: list[str] = []
    for para in paragraphs:
        all_words.extend(para.split())

    if not all_words:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(all_words):
        end = min(start + max_words, len(all_words))
        chunk_words = all_words[start:end]
        chunks.append(" ".join(chunk_words))
        if end == len(all_words):
            break
        start = end - overlap_words

    return chunks


def ingest_file(
    filename: str,
    text: str,
    embed_client,
    db: Session,
) -> int:
    """
    Chunk text, batch-embed all chunks in a single API call, then upsert.

    Returns the number of chunks written.
    Embedding is skipped if embed_client is None — chunks are stored without vectors.
    """
    from app.agents.embedding.client import NoOpEmbedder

    chunks = chunk_text(text)
    if not chunks:
        return 0

    # Batch-embed all chunks in one API call (much faster than one-by-one)
    embeddings: list[list[float]] = []
    if embed_client is not None and not isinstance(embed_client, NoOpEmbedder):
        try:
            embeddings = embed_client.embed(chunks)
        except Exception as exc:
            logger.warning("kb_ingester: batch embed failed, storing without vectors",
                           extra={"source_file": filename, "error": str(exc)})
            embeddings = []

    written = 0
    for idx, chunk in enumerate(chunks):
        row: dict = {
            "source_file": filename,
            "chunk_index": idx,
            "content": chunk,
        }
        if embeddings and idx < len(embeddings) and embeddings[idx]:
            row["embedding"] = embeddings[idx]

        try:
            stmt = (
                pg_insert(KnowledgeBase)
                .values(**row)
                .on_conflict_do_update(index_elements=["source_file", "chunk_index"], set_=row)
            )
            db.execute(stmt)
            db.commit()
            written += 1
        except Exception as exc:
            db.rollback()
            logger.warning("kb_ingester: upsert failed for chunk",
                           extra={"chunk_idx": idx, "error": str(exc)})

    logger.info("kb_ingester: ingestion complete",
                extra={"source_file": filename, "written": written, "total": len(chunks),
                       "embedded": len([e for e in embeddings if e])})
    return written
