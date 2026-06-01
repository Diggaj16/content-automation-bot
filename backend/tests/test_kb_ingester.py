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
    count = ingest_file("test.txt", "one two three", embed_client=None, supabase=sb)
    assert count == 1
    sb.table.assert_called_with("knowledge_base")


def test_ingest_file_embeds_when_client_present():
    from app.agents.orchestrator.kb_ingester import ingest_file
    from app.agents.embedding.client import EmbedClient
    from unittest.mock import MagicMock

    embed_client = MagicMock(spec=EmbedClient)
    embed_client.embed.return_value = [[0.1] * 768]  # one chunk → one 768-dim vector

    sb = MagicMock()
    sb.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "x"}]

    ingest_file("test.txt", "word " * 10, embed_client=embed_client, supabase=sb)
    embed_client.embed.assert_called()


def test_ingest_file_returns_zero_for_empty_text():
    from app.agents.orchestrator.kb_ingester import ingest_file
    sb = MagicMock()
    count = ingest_file("empty.txt", "", embed_client=None, supabase=sb)
    assert count == 0
    sb.table.return_value.upsert.assert_not_called()
