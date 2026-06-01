"""
Knowledge base file ingestion: extract → chunk → embed → upsert.

Supports PDF (PyPDF2) and TXT (UTF-8) files.
Embedding with Voyage AI is optional; pass voyage_client=None to skip.
"""
from __future__ import annotations

import io
from typing import Optional

import PyPDF2
from supabase import Client

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
            reader = PyPDF2.PdfReader(io.BytesIO(content_bytes))
        except PyPDF2.errors.PdfReadError as exc:
            raise ValueError(
                f"Cannot read PDF '{filename}': {exc}. "
                "The file may be encrypted, password-protected, or corrupted."
            ) from exc
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())
        return "\n\n".join(pages)
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
    voyage_client,
    supabase: Client,
    voyage_model: str = "voyage-3",
) -> int:
    """
    Chunk text and upsert each chunk into `knowledge_base`.

    Returns the number of chunks written.
    """
    chunks = chunk_text(text)
    if not chunks:
        return 0

    written = 0
    for idx, chunk in enumerate(chunks):
        row: dict = {
            "source_file": filename,
            "chunk_index": idx,
            "content": chunk,
        }

        if voyage_client is not None:
            try:
                result = voyage_client.embed([chunk], model=voyage_model, input_type="document")
                embedding = result.embeddings[0]
                row["embedding"] = embedding
            except Exception as exc:
                logger.warning("kb_ingester: embed failed for chunk", extra={"chunk_idx": idx, "error": str(exc)})

        try:
            resp = (
                supabase.table("knowledge_base")
                .upsert(row, on_conflict="source_file,chunk_index")
                .execute()
            )
            if resp.data:
                written += 1
        except Exception as exc:
            logger.warning("kb_ingester: upsert failed for chunk", extra={"chunk_idx": idx, "error": str(exc)})

    logger.info("kb_ingester: ingestion complete", extra={"source_file": filename, "written": written, "total": len(chunks)})
    return written
