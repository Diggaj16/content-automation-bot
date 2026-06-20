"""
Tests for app.agents.embedding.client — primary/fallback failover logic.

All backends are mocked; these tests never call a real embedding API.
"""
from app.agents.embedding.client import EmbedClient, FallbackEmbedder, NoOpEmbedder


class _StubEmbedder(EmbedClient):
    """Returns a fixed list of vectors, or raises if told to."""

    def __init__(self, vectors=None, raises: bool = False):
        self._vectors = vectors
        self._raises = raises
        self.calls: list[tuple[list[str], bool]] = []

    def embed(self, texts, *, for_query=False):
        self.calls.append((texts, for_query))
        if self._raises:
            raise RuntimeError("stub embedder failure")
        return self._vectors


class TestFallbackEmbedder:
    def test_uses_primary_when_it_succeeds(self):
        primary = _StubEmbedder(vectors=[[1.0, 2.0], [3.0, 4.0]])
        fallback = _StubEmbedder(vectors=[[9.0, 9.0], [9.0, 9.0]])
        client = FallbackEmbedder(primary=primary, fallback=fallback)

        result = client.embed(["a", "b"])

        assert result == [[1.0, 2.0], [3.0, 4.0]]
        assert len(fallback.calls) == 0

    def test_falls_back_when_primary_raises(self):
        primary = _StubEmbedder(raises=True)
        fallback = _StubEmbedder(vectors=[[9.0, 9.0]])
        client = FallbackEmbedder(primary=primary, fallback=fallback)

        result = client.embed(["a"])

        assert result == [[9.0, 9.0]]

    def test_partial_failure_treated_as_full_failure(self):
        # Regression test: if the primary returns a MIX of valid and empty
        # vectors (e.g. one chunk of a batch failed), the whole batch must be
        # retried against the fallback rather than returning a silently
        # mixed valid/empty result to the caller.
        primary = _StubEmbedder(vectors=[[1.0, 2.0], [], [3.0, 4.0]])
        fallback = _StubEmbedder(vectors=[[9.0], [9.0], [9.0]])
        client = FallbackEmbedder(primary=primary, fallback=fallback)

        result = client.embed(["a", "b", "c"])

        assert result == [[9.0], [9.0], [9.0]]
        assert len(fallback.calls) == 1

    def test_for_query_flag_passed_through(self):
        primary = _StubEmbedder(vectors=[[1.0]])
        fallback = _StubEmbedder(vectors=[[9.0]])
        client = FallbackEmbedder(primary=primary, fallback=fallback)

        client.embed(["q"], for_query=True)

        assert primary.calls == [(["q"], True)]


class TestEmbedClientEmbedOne:
    def test_embed_one_wraps_single_text(self):
        primary = _StubEmbedder(vectors=[[1.0, 2.0]])
        result = primary.embed_one("hello")
        assert result == [1.0, 2.0]
        assert primary.calls == [(["hello"], False)]

    def test_embed_one_on_empty_result_returns_empty_list(self):
        noop = NoOpEmbedder()
        assert noop.embed_one("hello") == []


class TestNoOpEmbedder:
    def test_returns_empty_vector_per_text(self):
        noop = NoOpEmbedder()
        assert noop.embed(["a", "b", "c"]) == [[], [], []]

    def test_handles_empty_input(self):
        noop = NoOpEmbedder()
        assert noop.embed([]) == []
