"""Unit tests for app.agents.research.summariser."""
import json
from unittest.mock import MagicMock

import pytest

from app.agents.research.summariser import summarise_article, SummaryResult, _MAX_ARTICLE_CHARS
from app.db.models import StructuredSummary

_VALID_SUMMARY = {
    "story_narrative": "RBI raised rates by 25bps in a surprise move.",
    "key_data_points": ["25bps", "6.75% repo rate", "May 2025"],
    "mechanism": "Inflation exceeded the 6% upper tolerance band.",
    "implications": "Home loan EMIs will increase for floating-rate borrowers.",
    "content_angles": ["Impact on EMIs", "What it means for fixed deposits"],
}


def _make_mock_client(json_text: str, input_tokens: int = 200, output_tokens: int = 80) -> MagicMock:
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json_text)]
    mock_msg.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


class TestSummariseArticle:
    def test_returns_structured_summary_on_success(self):
        client = _make_mock_client(json.dumps(_VALID_SUMMARY), input_tokens=200, output_tokens=80)
        result = summarise_article(
            full_text="Long article text " * 50,
            title="RBI raises repo rate",
            client=client,
            model="claude-sonnet-4-5",
        )
        assert isinstance(result, SummaryResult)
        assert isinstance(result.summary, StructuredSummary)
        assert result.summary.story_narrative == _VALID_SUMMARY["story_narrative"]
        assert result.summary.key_data_points == _VALID_SUMMARY["key_data_points"]
        assert result.input_tokens == 200
        assert result.output_tokens == 80

    def test_malformed_json_returns_fallback_summary(self):
        client = _make_mock_client("Sorry, I cannot summarise this.")
        result = summarise_article(
            full_text="Some article text",
            title="Some article title",
            client=client,
            model="claude-sonnet-4-5",
        )
        assert isinstance(result.summary, StructuredSummary)
        assert result.summary.story_narrative == "Some article title"
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_api_exception_returns_fallback_summary(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Network error")
        result = summarise_article(
            full_text="Some article text",
            title="Some article title",
            client=mock_client,
            model="claude-sonnet-4-5",
        )
        assert result.summary.story_narrative == "Some article title"
        assert result.input_tokens == 0

    def test_text_truncated_to_max_chars(self):
        """Very long articles must be truncated before sending to Claude."""
        long_text = "x" * 20_000   # exceeds 12_000 char cap
        client = _make_mock_client(json.dumps(_VALID_SUMMARY))
        summarise_article(full_text=long_text, title="Title", client=client, model="claude-sonnet-4-5")

        call_kwargs = client.messages.create.call_args.kwargs
        user_content = call_kwargs["messages"][0]["content"]
        # The user message must not contain more than 12_000 + len("Title: Title\n\n") chars
        assert len(user_content) <= _MAX_ARTICLE_CHARS + len("Title: Title\n\n")

    def test_uses_specified_model(self):
        client = _make_mock_client(json.dumps(_VALID_SUMMARY))
        summarise_article(full_text="text", title="title", client=client, model="claude-sonnet-4-5")
        assert client.messages.create.call_args.kwargs["model"] == "claude-sonnet-4-5"

    def test_fallback_summary_has_empty_lists_not_none(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("error")
        result = summarise_article("text", "title", mock_client, "claude-sonnet-4-5")
        assert result.summary.key_data_points == []
        assert result.summary.content_angles == []
        assert result.summary.mechanism == ""
        assert result.summary.implications == ""

    def test_empty_content_list_returns_fallback(self):
        """Empty content list from API should return fallback, not raise IndexError."""
        mock_msg = MagicMock()
        mock_msg.content = []
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        result = summarise_article("article text", "article title", mock_client, "claude-sonnet-4-5")
        assert isinstance(result.summary, StructuredSummary)
        assert result.summary.story_narrative == "article title"
        assert result.input_tokens == 0

    def test_markdown_fenced_json_is_parsed_correctly(self):
        """Claude sometimes wraps JSON in markdown fences; must be handled gracefully."""
        import json
        fenced = f"```json\n{json.dumps(_VALID_SUMMARY)}\n```"
        client = _make_mock_client(fenced)
        result = summarise_article("text", "title", client, "claude-sonnet-4-5")
        assert result.summary.story_narrative == _VALID_SUMMARY["story_narrative"]
        assert isinstance(result.input_tokens, int)

    def test_extra_keys_in_json_are_ignored(self):
        """Claude may return extra fields; only known StructuredSummary fields should be used."""
        import json
        extra_key_summary = {**_VALID_SUMMARY, "confidence": 0.9, "source": "RBI press release"}
        client = _make_mock_client(json.dumps(extra_key_summary))
        result = summarise_article("text", "title", client, "claude-sonnet-4-5")
        assert isinstance(result.summary, StructuredSummary)
        assert result.summary.story_narrative == _VALID_SUMMARY["story_narrative"]
