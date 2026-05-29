"""Unit tests for app.agents.research.prescorer."""
from unittest.mock import MagicMock

import pytest

from app.agents.research.prescorer import pre_score_headlines, PreScoreResult


def _make_mock_client(json_text: str, input_tokens: int = 50, output_tokens: int = 10) -> MagicMock:
    """Build a mock Anthropic client whose messages.create returns `json_text`."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json_text)]
    mock_msg.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


class TestPreScoreHeadlines:
    def test_returns_correct_scores_for_three_titles(self):
        client = _make_mock_client("[8.0, 3.5, 6.0]", input_tokens=60, output_tokens=12)
        titles = [
            "RBI raises repo rate by 25bps in surprise off-cycle move",
            "Local company opens new branch in Pune",
            "SEBI tightens F&O eligibility criteria for equity derivatives",
        ]
        result = pre_score_headlines(titles, client, model="claude-haiku-4-5")

        assert isinstance(result, PreScoreResult)
        assert result.scores == [8.0, 3.5, 6.0]
        assert result.input_tokens == 60
        assert result.output_tokens == 12

    def test_single_title(self):
        client = _make_mock_client("[7.5]", input_tokens=30, output_tokens=5)
        result = pre_score_headlines(
            ["Nifty crosses 25000 for first time on foreign inflows"],
            client,
            model="claude-haiku-4-5",
        )
        assert result.scores == [7.5]

    def test_empty_titles_returns_empty_without_api_call(self):
        mock_client = MagicMock()
        result = pre_score_headlines([], mock_client, model="claude-haiku-4-5")

        assert result.scores == []
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        mock_client.messages.create.assert_not_called()

    def test_malformed_json_returns_neutral_scores(self):
        client = _make_mock_client("Sorry, I cannot score these.")
        titles = ["Title A about RBI", "Title B about markets"]
        result = pre_score_headlines(titles, client, model="claude-haiku-4-5")

        assert result.scores == [5.0, 5.0]
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_wrong_count_returns_neutral_scores(self):
        client = _make_mock_client("[8.0, 4.0]")
        titles = ["Title A", "Title B", "Title C"]
        result = pre_score_headlines(titles, client, model="claude-haiku-4-5")

        assert result.scores == [5.0, 5.0, 5.0]
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_api_exception_returns_neutral_scores(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API rate limit")
        titles = ["Title A about RBI rates", "Title B about SEBI"]
        result = pre_score_headlines(titles, mock_client, model="claude-haiku-4-5")

        assert result.scores == [5.0, 5.0]
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_scores_are_floats_not_ints(self):
        client = _make_mock_client("[8, 3, 6]")
        titles = ["Title A", "Title B", "Title C"]
        result = pre_score_headlines(titles, client, model="claude-haiku-4-5")

        assert all(isinstance(s, float) for s in result.scores)

    def test_uses_correct_model_name(self):
        client = _make_mock_client("[7.0]")
        pre_score_headlines(["Some headline about finance"], client, model="claude-haiku-4-5")

        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5"

    def test_headlines_appear_in_user_message(self):
        """Each title must appear in the user message sent to the API."""
        client = _make_mock_client("[7.0, 5.0]")
        titles = [
            "RBI announces emergency rate cut of 50 basis points",
            "Nifty 50 closes at record high on strong FII buying",
        ]
        pre_score_headlines(titles, client, model="claude-haiku-4-5")

        call_kwargs = client.messages.create.call_args.kwargs
        user_content = call_kwargs["messages"][0]["content"]
        assert "RBI announces emergency rate cut" in user_content
        assert "Nifty 50 closes at record high" in user_content
