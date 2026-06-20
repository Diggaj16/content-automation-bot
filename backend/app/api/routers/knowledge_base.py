"""
Knowledge base ingestion endpoints.

POST /knowledge-base/upload  — upload PDF or TXT; returns {source_file, chunks_ingested}
GET  /knowledge-base          — list ingested files grouped by source_file
DELETE /knowledge-base/{source_file} — delete all chunks for a file
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings
from app.config import Settings
from app.agents.orchestrator.kb_ingester import extract_text, ingest_file
from app.db.orm import KnowledgeBase
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/knowledge-base", tags=["Knowledge Base"])

_ALLOWED_EXTENSIONS = {".pdf", ".txt"}


@router.post("/upload")
async def upload_kb_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    filename = file.filename or "upload"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f"Only PDF and TXT files are accepted. Got: {ext!r}")

    MAX_KB_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
    content_bytes = await file.read()
    if len(content_bytes) > MAX_KB_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

    try:
        text = extract_text(filename, content_bytes)
    except ValueError as exc:
        logger.warning("kb: unsupported or malformed file", extra={"source_file": filename, "error": str(exc)})
        raise HTTPException(status_code=422, detail="Unsupported or malformed file.")
    except Exception as exc:
        logger.warning("kb: text extraction failed", extra={"source_file": filename, "error": str(exc)})
        raise HTTPException(status_code=500, detail="Failed to extract text from file.")

    from app.agents.embedding.client import make_embed_client
    embed_client = make_embed_client(
        google_api_key=settings.google_api_key,
        local_model=settings.local_embedding_model,
    )

    try:
        chunks_written = ingest_file(filename, text, embed_client, db)
    except Exception as exc:
        logger.warning("kb: ingestion failed", extra={"source_file": filename, "error": str(exc)})
        raise HTTPException(status_code=500, detail="Failed to ingest file.")

    return {"source_file": filename, "chunks_ingested": chunks_written}


@router.get("")
def list_kb_files(
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return distinct source files with chunk count and earliest created_at."""
    try:
        rows = db.execute(
            select(KnowledgeBase.source_file, KnowledgeBase.chunk_index, KnowledgeBase.created_at)
            .order_by(KnowledgeBase.source_file, KnowledgeBase.chunk_index)
        ).all()

        # Group by source_file
        files: dict[str, dict] = {}
        for row in rows:
            sf = row.source_file
            if sf not in files:
                files[sf] = {"source_file": sf, "chunk_count": 0, "created_at": row.created_at}
            files[sf]["chunk_count"] += 1

        return list(files.values())
    except Exception as exc:
        logger.warning("kb: list failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Failed to list knowledge base files.")


@router.delete("/{source_file:path}")
def delete_kb_file(
    source_file: str,
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = db.execute(delete(KnowledgeBase).where(KnowledgeBase.source_file == source_file))
        db.commit()
        if not result.rowcount:
            raise HTTPException(status_code=404, detail=f"No knowledge base file found: {source_file!r}")
        return {"deleted": True, "source_file": source_file}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.warning("kb: delete failed", extra={"source_file": source_file, "error": str(exc)})
        raise HTTPException(status_code=500, detail="Failed to delete knowledge base file.")
