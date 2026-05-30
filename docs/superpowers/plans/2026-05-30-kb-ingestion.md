# Knowledge Base Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Accept PDF and TXT file uploads from the browser, extract text, chunk it with a sliding-window chunker, optionally embed with Voyage AI, write chunks to the `knowledge_base` table, and expose a management page for listing and deleting ingested files.

**Architecture:** A new `kb_ingester.py` module handles extraction, chunking, and DB writes. A new FastAPI router `knowledge_base.py` wires it to multipart upload/list/delete endpoints. A new Next.js page at `/knowledge-base` offers drag-and-drop upload plus a file list. `python-multipart` is required for FastAPI multipart; `PyPDF2` for PDF extraction.

**Tech Stack:** Python 3.11, PyPDF2, anthropic SDK (not used here), supabase-py, voyageai (optional), pytest + pytest-mock; Next.js 16, React 19, Tailwind 4.

---

## File Map

| Action | Path |
|--------|------|
| Create | `backend/app/agents/orchestrator/__init__.py` |
| Create | `backend/app/agents/orchestrator/kb_ingester.py` |
| Create | `backend/app/api/routers/knowledge_base.py` |
| Modify | `backend/app/api/main.py` |
| Modify | `backend/pyproject.toml` |
| Create | `backend/tests/test_kb_ingester.py` |
| Create | `frontend/app/knowledge-base/page.tsx` |
| Modify | `frontend/app/lib/api.ts` |

---

### Task 1 — Dependencies

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add PyPDF2 and python-multipart**

Open `backend/pyproject.toml`. In the `dependencies = [...]` list, add these two lines:

```toml
"PyPDF2>=3.0.0",
"python-multipart>=0.0.9",
```

- [ ] **Step 2: Install dependencies**

```powershell
cd D:\Intern\content-automation-bot\backend
pip install "PyPDF2>=3.0.0" "python-multipart>=0.0.9"
```

Expected: both install successfully.

- [ ] **Step 3: Verify imports**

```powershell
cd D:\Intern\content-automation-bot\backend
python -c "import PyPDF2; from fastapi import UploadFile; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml
git commit -m "chore: add PyPDF2 and python-multipart dependencies"
```

---

### Task 2 — `kb_ingester.py` module

**Files:**
- Create: `backend/app/agents/orchestrator/__init__.py`
- Create: `backend/app/agents/orchestrator/kb_ingester.py`
- Create: `backend/tests/test_kb_ingester.py`

- [ ] **Step 1: Create the orchestrator package init**

```python
# backend/app/agents/orchestrator/__init__.py
```

(Empty file — just creates the package.)

- [ ] **Step 2: Write the failing tests**

```python
# backend/tests/test_kb_ingester.py
"""Unit tests for kb_ingester: extract_text, chunk_text, ingest_file."""
from unittest.mock import MagicMock, patch
import pytest


# ── extract_text ────────────────────────────────────────────────────

def test_extract_txt_utf8():
    from app.agents.orchestrator.kb_ingester import extract_text
    content = "Hello world, this is text."
    result = extract_text("doc.txt", content.encode("utf-8"))
    assert result == "Hello world, this is text."


def test_extract_txt_strips_whitespace():
    from app.agents.orchestrator.kb_ingester import extract_text
    result = extract_text("doc.txt", b"  spaced out  ")
    assert result == "spaced out"


def test_extract_pdf_calls_pdfreader():
    from app.agents.orchestrator.kb_ingester import extract_text
    with patch("app.agents.orchestrator.kb_ingester.PyPDF2") as mock_pdf:
        page1 = MagicMock()
        page1.extract_text.return_value = "Page one content."
        page2 = MagicMock()
        page2.extract_text.return_value = "Page two content."
        mock_pdf.PdfReader.return_value.pages = [page1, page2]

        result = extract_text("doc.pdf", b"fake-pdf-bytes")
        assert "Page one" in result
        assert "Page two" in result


def test_extract_unsupported_raises():
    from app.agents.orchestrator.kb_ingester import extract_text
    with pytest.raises(ValueError, match="Unsupported"):
        extract_text("doc.docx", b"bytes")


# ── chunk_text ──────────────────────────────────────────────────────

def test_chunk_short_text_produces_one_chunk():
    from app.agents.orchestrator.kb_ingester import chunk_text
    text = "Short text with fewer than 500 words."
    chunks = chunk_text(text, max_words=500, overlap_words=50)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_long_text_produces_multiple_chunks():
    from app.agents.orchestrator.kb_ingester import chunk_text
    # 600 words
    text = " ".join(["word"] * 600)
    chunks = chunk_text(text, max_words=200, overlap_words=20)
    assert len(chunks) >= 3


def test_chunk_overlap_shares_words():
    from app.agents.orchestrator.kb_ingester import chunk_text
    # 300 words
    words = [f"w{i}" for i in range(300)]
    text = " ".join(words)
    chunks = chunk_text(text, max_words=100, overlap_words=20)
    assert len(chunks) >= 2
    # Last 20 words of chunk 0 should appear in first 20 words of chunk 1
    c0_last = chunks[0].split()[-20:]
    c1_first = chunks[1].split()[:20]
    assert c0_last == c1_first


def test_chunk_empty_text_returns_empty_list():
    from app.agents.orchestrator.kb_ingester import chunk_text
    assert chunk_text("") == []


def test_chunk_whitespace_only_returns_empty_list():
    from app.agents.orchestrator.kb_ingester import chunk_text
    assert chunk_text("   \n\n  ") == []


# ── ingest_file ─────────────────────────────────────────────────────

def test_ingest_file_writes_chunks_without_voyage():
    from app.agents.orchestrator.kb_ingester import ingest_file
    sb = MagicMock()
    sb.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "x"}]

    # 3-word text → 1 chunk
    count = ingest_file("test.txt", "one two three", voyage_client=None, supabase=sb)
    assert count == 1
    sb.table.assert_called_with("knowledge_base")


def test_ingest_file_embeds_when_voyage_present():
    from app.agents.orchestrator.kb_ingester import ingest_file

    voyage = MagicMock()
    voyage.embed.return_value.embeddings = [[0.1] * 1024]

    sb = MagicMock()
    sb.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "x"}]

    ingest_file("test.txt", "word " * 10, voyage_client=voyage, supabase=sb)
    voyage.embed.assert_called()


def test_ingest_file_returns_zero_for_empty_text():
    from app.agents.orchestrator.kb_ingester import ingest_file
    sb = MagicMock()
    count = ingest_file("empty.txt", "", voyage_client=None, supabase=sb)
    assert count == 0
    sb.table.return_value.upsert.assert_not_called()
```

- [ ] **Step 3: Run tests — expect ImportError**

```powershell
cd D:\Intern\content-automation-bot\backend
pytest tests/test_kb_ingester.py -v 2>&1 | Select-Object -First 20
```

Expected: `ModuleNotFoundError: No module named 'app.agents.orchestrator.kb_ingester'`

- [ ] **Step 4: Write `kb_ingester.py`**

```python
# backend/app/agents/orchestrator/kb_ingester.py
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
        reader = PyPDF2.PdfReader(io.BytesIO(content_bytes))
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

    Strategy:
    1. Split on double-newlines (paragraph boundaries) first.
    2. Accumulate paragraphs into chunks of at most max_words words.
    3. Add overlap_words from the previous chunk at each boundary.
    """
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    # Flatten all words, tracking paragraph boundaries
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
        start = end - overlap_words  # slide back by overlap

    return chunks


def ingest_file(
    filename: str,
    text: str,
    voyage_client,
    supabase: Client,
) -> int:
    """
    Chunk text and upsert each chunk into `knowledge_base`.

    Returns the number of chunks written.
    Uses ON CONFLICT (source_file, chunk_index) DO UPDATE so re-uploading
    the same file replaces old chunks cleanly.
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
                result = voyage_client.embed([chunk], model="voyage-3", input_type="document")
                embedding = result.embeddings[0]
                row["embedding"] = embedding
            except Exception as exc:
                logger.warning(f"kb_ingester: embed failed for chunk {idx} | err={exc}")

        try:
            resp = (
                supabase.table("knowledge_base")
                .upsert(row, on_conflict="source_file,chunk_index")
                .execute()
            )
            if resp.data:
                written += 1
        except Exception as exc:
            logger.warning(f"kb_ingester: upsert failed for chunk {idx} | err={exc}")

    logger.info(f"kb_ingester: ingested {written}/{len(chunks)} chunks from {filename}")
    return written
```

- [ ] **Step 5: Run tests — expect all pass**

```powershell
cd D:\Intern\content-automation-bot\backend
pytest tests/test_kb_ingester.py -v
```

Expected: `12 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/orchestrator/__init__.py backend/app/agents/orchestrator/kb_ingester.py backend/tests/test_kb_ingester.py
git commit -m "feat: add kb_ingester module for PDF/TXT chunking and Supabase upsert"
```

---

### Task 3 — `knowledge_base.py` router

**Files:**
- Create: `backend/app/api/routers/knowledge_base.py`

- [ ] **Step 1: Write the router**

```python
# backend/app/api/routers/knowledge_base.py
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
```

- [ ] **Step 2: Register router in `main.py`**

In `backend/app/api/main.py`, inside `create_app()`, after the subscribers router block, add:

```python
    from app.api.routers.knowledge_base import router as kb_router
    _app.include_router(kb_router)
```

- [ ] **Step 3: Smoke test**

```powershell
cd D:\Intern\content-automation-bot\backend
python -c "from app.api.main import app; routes = [r.path for r in app.routes]; print([r for r in routes if 'knowledge' in r])"
```

Expected: `['/knowledge-base/upload', '/knowledge-base', '/knowledge-base/{source_file}']`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/routers/knowledge_base.py backend/app/api/main.py
git commit -m "feat: add knowledge base upload/list/delete endpoints"
```

---

### Task 4 — Frontend api.ts additions

**Files:**
- Modify: `frontend/app/lib/api.ts`

- [ ] **Step 1: Add KB file type and functions**

In `frontend/app/lib/api.ts`, append after the subscribers block (before the generic table browser comment):

```typescript
// --- Knowledge Base ---

export interface KbFile {
  source_file: string;
  chunk_count: number;
  created_at: string;
}

export async function uploadKbFile(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/knowledge-base/upload`, {
    method: "POST",
    body: formData,
    // No Content-Type header — browser sets multipart boundary automatically
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload failed ${res.status}: ${text}`);
  }
  return res.json() as Promise<{ source_file: string; chunks_ingested: number }>;
}

export async function listKbFiles() {
  return apiFetch<KbFile[]>("/knowledge-base");
}

export async function deleteKbFile(sourceFile: string) {
  return apiFetch<{ deleted: boolean; source_file: string }>(
    `/knowledge-base/${encodeURIComponent(sourceFile)}`,
    { method: "DELETE" }
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```powershell
cd D:\Intern\content-automation-bot\frontend
npx tsc --noEmit 2>&1 | Select-Object -First 20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/lib/api.ts
git commit -m "feat: add knowledge base API functions to frontend api.ts"
```

---

### Task 5 — Frontend knowledge base page

**Files:**
- Create: `frontend/app/knowledge-base/page.tsx`

- [ ] **Step 1: Write the page**

```tsx
// frontend/app/knowledge-base/page.tsx
"use client";

import { useState, useEffect, useRef } from "react";
import { uploadKbFile, listKbFiles, deleteKbFile, type KbFile } from "../lib/api";

export default function KnowledgeBasePage() {
  const [files, setFiles] = useState<KbFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  const fetchFiles = async () => {
    setLoading(true);
    setError(null);
    try {
      setFiles(await listKbFiles());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  const handleUpload = async (file: File) => {
    if (!file.name.match(/\.(pdf|txt)$/i)) {
      showToast("Only PDF and TXT files are supported.");
      return;
    }
    setUploading(true);
    try {
      const result = await uploadKbFile(file);
      showToast(`Uploaded "${result.source_file}" — ${result.chunks_ingested} chunks ingested.`);
      await fetchFiles();
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
    e.target.value = "";
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  };

  const handleDelete = async (sourceFile: string) => {
    try {
      await deleteKbFile(sourceFile);
      setFiles((prev) => prev.filter((f) => f.source_file !== sourceFile));
      showToast(`Deleted "${sourceFile}".`);
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : "Delete failed");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Knowledge Base</h1>
          <p className="text-sm text-gray-500 mt-1">
            Upload PDF or TXT files to use as context in KB-driven and combined content.
          </p>
        </div>
        <button
          onClick={fetchFiles}
          disabled={loading}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          Refresh
        </button>
      </div>

      {toast && (
        <div className="px-4 py-3 rounded-md text-sm bg-blue-50 text-blue-700 border border-blue-200">
          {toast}
        </div>
      )}

      {/* Upload zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors ${
          dragOver
            ? "border-blue-400 bg-blue-50"
            : "border-gray-300 hover:border-gray-400 bg-white"
        } ${uploading ? "opacity-60 pointer-events-none" : ""}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt"
          className="hidden"
          onChange={handleFileInput}
        />
        <div className="text-3xl mb-2">📄</div>
        <p className="text-sm font-medium text-gray-700">
          {uploading ? "Uploading..." : "Drop a PDF or TXT file here, or click to browse"}
        </p>
        <p className="text-xs text-gray-400 mt-1">Max size determined by server config</p>
      </div>

      {/* File list */}
      {error && (
        <div className="px-4 py-3 rounded-md text-sm bg-red-50 text-red-700 border border-red-200">
          {error}
        </div>
      )}

      {!loading && !error && files.length === 0 && (
        <div className="text-center py-12 text-gray-500 text-sm">
          No files ingested yet. Upload a PDF or TXT to get started.
        </div>
      )}

      {files.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">File</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Chunks</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Uploaded</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {files.map((f) => (
                <tr key={f.source_file} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-900 font-medium">{f.source_file}</td>
                  <td className="px-4 py-3 text-gray-600">{f.chunk_count}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {new Date(f.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleDelete(f.source_file)}
                      className="text-xs text-red-600 hover:underline"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```powershell
cd D:\Intern\content-automation-bot\frontend
npx tsc --noEmit 2>&1 | Select-Object -First 20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/knowledge-base/page.tsx
git commit -m "feat: add knowledge base upload/management page"
```
