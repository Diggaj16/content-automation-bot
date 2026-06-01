"""
Knowledge base ingestion endpoints.

POST /knowledge-base/upload  — upload PDF or TXT; returns {source_file, chunks_ingested}
GET  /knowledge-base          — list ingested files grouped by source_file
DELETE /knowledge-base/{source_file} — delete all chunks for a file
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from supabase import Client

from app.api.deps import get_supabase, get_settings
from app.config import Settings
from app.agents.orchestrator.kb_ingester import extract_text, ingest_file

router = APIRouter(prefix="/knowledge-base", tags=["Knowledge Base"])

_ALLOWED_EXTENSIONS = {".pdf", ".txt"}


@router.post("/upload")
async def upload_kb_file(
    file: UploadFile = File(...),
    supabase: Client = Depends(get_supabase),
    settings: Settings = Depends(get_settings),
) -> dict:
    filename = file.filename or "upload"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f"Only PDF and TXT files are accepted. Got: {ext!r}")

    content_bytes = await file.read()
    try:
        text = extract_text(filename, content_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to extract text: {exc}")

    voyage_client = None
    if settings.voyage_api_key:
        import voyageai
        voyage_client = voyageai.Client(api_key=settings.voyage_api_key)

    try:
        chunks_written = ingest_file(filename, text, voyage_client, supabase)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to ingest file: {exc}")

    return {"source_file": filename, "chunks_ingested": chunks_written}


@router.get("")
def list_kb_files(
    supabase: Client = Depends(get_supabase),
) -> list[dict]:
    """Return distinct source files with chunk count and earliest created_at."""
    try:
        resp = (
            supabase.table("knowledge_base")
            .select("source_file, chunk_index, created_at")
            .order("source_file")
            .order("chunk_index")
            .execute()
        )
        rows = resp.data or []

        # Group by source_file
        files: dict[str, dict] = {}
        for row in rows:
            sf = row["source_file"]
            if sf not in files:
                files[sf] = {"source_file": sf, "chunk_count": 0, "created_at": row["created_at"]}
            files[sf]["chunk_count"] += 1

        return list(files.values())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{source_file:path}")
def delete_kb_file(
    source_file: str,
    supabase: Client = Depends(get_supabase),
) -> dict:
    try:
        supabase.table("knowledge_base").delete().eq("source_file", source_file).execute()
        return {"deleted": True, "source_file": source_file}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
