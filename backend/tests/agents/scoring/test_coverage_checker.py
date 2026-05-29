"""Unit tests for app.agents.scoring.coverage_checker."""
from unittest.mock import MagicMock

import pytest

from app.agents.scoring.coverage_checker import check_recent_coverage


def _make_supabase(rpc_data: list) -> MagicMock:
    """Return a mock Supabase client whose rpc().execute() returns rpc_data."""
    mock_resp = MagicMock()
    mock_resp.data = rpc_data
    mock_sb = MagicMock()
    mock_sb.rpc.return_value.execute.return_value = mock_resp
    return mock_sb


_DUMMY_EMBEDDING = [0.1] * 1024


class TestCheckRecentCoverage:
    def test_returns_true_when_similar_content_found(self):
        sb = _make_supabase([
            {"id": "uuid-1", "content": "RBI rate decision", "similarity": 0.92},
        ])
        result = check_recent_coverage(_DUMMY_EMBEDDING, "linkedin", sb)
        assert result is True

    def test_returns_false_when_no_similar_content(self):
        sb = _make_supabase([])
        result = check_recent_coverage(_DUMMY_EMBEDDING, "linkedin", sb)
        assert result is False

    def test_returns_false_for_empty_embedding(self):
        """When embed_text returned [] (no Voyage key), skip RPC entirely."""
        sb = MagicMock()  # should not be called at all
        result = check_recent_coverage([], "linkedin", sb)
        assert result is False
        sb.rpc.assert_not_called()

    def test_passes_correct_params_to_rpc(self):
        sb = _make_supabase([])
        check_recent_coverage(
            _DUMMY_EMBEDDING, "twitter", sb, days_back=14, threshold=0.90
        )
        sb.rpc.assert_called_once_with(
            "check_recent_brand_coverage",
            {
                "topic_embedding":   _DUMMY_EMBEDDING,
                "platform_filter":   "twitter",
                "days_back":         14,
                "similarity_threshold": 0.90,
            },
        )

    def test_returns_false_on_exception(self):
        sb = MagicMock()
        sb.rpc.side_effect = Exception("Supabase connection error")
        result = check_recent_coverage(_DUMMY_EMBEDDING, "linkedin", sb)
        assert result is False
