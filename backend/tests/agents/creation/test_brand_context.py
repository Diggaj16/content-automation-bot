# tests/agents/creation/test_brand_context.py
"""Tests for brand_context.get_brand_context."""
from unittest.mock import MagicMock
from app.agents.creation.brand_context import get_brand_context


def _mock_sb_rpc(data):
    sb = MagicMock()
    sb.rpc.return_value.execute.return_value.data = data
    return sb


def test_returns_formatted_string_when_results():
    sb = _mock_sb_rpc([
        {"id": "1", "content": "LinkedIn post about SEBI crackdown"},
        {"id": "2", "content": "Thread on mutual funds"},
    ])
    result = get_brand_context([0.1, 0.2, 0.3], "linkedin", sb)
    assert "LinkedIn post about SEBI crackdown" in result
    assert "Thread on mutual funds" in result
    assert result.startswith("Past brand content examples:")


def test_returns_empty_string_when_no_results():
    sb = _mock_sb_rpc([])
    result = get_brand_context([0.1, 0.2], "linkedin", sb)
    assert result == ""


def test_returns_empty_string_when_data_is_none():
    sb = _mock_sb_rpc(None)
    result = get_brand_context([0.1, 0.2], "linkedin", sb)
    assert result == ""


def test_empty_embedding_returns_empty_string_no_rpc():
    sb = MagicMock()
    result = get_brand_context([], "linkedin", sb)
    assert result == ""
    sb.rpc.assert_not_called()


def test_none_embedding_returns_empty_string_no_rpc():
    sb = MagicMock()
    result = get_brand_context(None, "linkedin", sb)
    assert result == ""
    sb.rpc.assert_not_called()


def test_rpc_exception_returns_empty_string():
    sb = MagicMock()
    sb.rpc.return_value.execute.side_effect = RuntimeError("RPC failed")
    result = get_brand_context([0.1, 0.2], "linkedin", sb)
    assert result == ""


def test_respects_match_count_parameter():
    sb = _mock_sb_rpc([{"id": "1", "content": "post1"}])
    get_brand_context([0.1], "twitter", sb, match_count=3)
    call_kwargs = sb.rpc.call_args[0][1]
    assert call_kwargs["match_count"] == 3
