"""Unit tests for app.agents.scoring.embedder."""
from unittest.mock import MagicMock

from app.agents.scoring.embedder import embed_text
from app.agents.embedding.client import EmbedClient


def _make_embed_client(embedding: list[float]) -> MagicMock:
    """Return a mock EmbedClient whose embed_one() returns the given embedding."""
    client = MagicMock(spec=EmbedClient)
    client.embed_one.return_value = embedding
    return client


class TestEmbedText:
    def test_returns_embedding_on_success(self):
        expected = [0.1, 0.2, 0.3]
        client = _make_embed_client(expected)
        result = embed_text("some finance article text", client)
        assert result == expected
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    def test_returns_empty_list_when_client_is_none(self):
        result = embed_text("some text", None)
        assert result == []

    def test_returns_empty_list_on_exception(self):
        client = MagicMock(spec=EmbedClient)
        client.embed_one.side_effect = Exception("API error")
        result = embed_text("some text", client)
        assert result == []

    def test_passes_text_to_embed_one(self):
        client = _make_embed_client([0.1, 0.2])
        embed_text("my article text", client)
        client.embed_one.assert_called_once_with("my article text")
