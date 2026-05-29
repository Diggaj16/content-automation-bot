"""Unit tests for app.agents.scoring.embedder."""
from unittest.mock import MagicMock

import pytest

from app.agents.scoring.embedder import embed_text, _EMBEDDING_MODEL


def _make_voyage_client(embeddings: list[list[float]]) -> MagicMock:
    """Return a mock voyageai.Client whose embed() returns the given embeddings."""
    mock_result = MagicMock()
    mock_result.embeddings = embeddings
    mock_client = MagicMock()
    mock_client.embed.return_value = mock_result
    return mock_client


class TestEmbedText:
    def test_returns_embedding_on_success(self):
        expected = [0.1, 0.2, 0.3]
        client = _make_voyage_client([expected])
        result = embed_text("some finance article text", client)
        assert result == expected
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    def test_returns_empty_list_on_exception(self):
        mock_client = MagicMock()
        mock_client.embed.side_effect = Exception("Voyage API error")
        result = embed_text("some text", mock_client)
        assert result == []

    def test_passes_correct_model(self):
        client = _make_voyage_client([[0.1, 0.2]])
        embed_text("text", client)
        call_kwargs = client.embed.call_args.kwargs
        assert call_kwargs["model"] == _EMBEDDING_MODEL

    def test_passes_text_as_list(self):
        client = _make_voyage_client([[0.1, 0.2]])
        embed_text("my article text", client)
        call_args = client.embed.call_args.args
        # First positional arg must be a list containing the text, not the bare string
        assert call_args[0] == ["my article text"]
