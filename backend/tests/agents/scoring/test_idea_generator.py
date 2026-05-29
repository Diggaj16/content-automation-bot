"""Unit tests for app.agents.scoring.idea_generator."""
import json
from unittest.mock import MagicMock
from uuid import uuid4
from datetime import datetime, timezone

import pytest

from app.agents.scoring.idea_generator import (
    generate_ideas,
    IdeaGenerationResult,
)
from app.db.models import IdeaCreate, Platform, RawContent, StructuredSummary


_VALID_IDEAS = [
    {
        "platform":        "linkedin",
        "angle":           "How RBI rate hike affects your home loan EMI",
        "agent_reasoning": "High engagement topic; directly impacts retail borrowers.",
        "score":           8.5,
    },
    {
        "platform":        "twitter",
        "angle":           "RBI surprise: 3 things every investor must know",
        "agent_reasoning": "Twitter audience responds to numbered lists on macro news.",
        "score":           7.0,
    },
]

_VALID_SUMMARY = StructuredSummary(
    story_narrative="RBI raised repo rate by 25bps in a surprise off-cycle move.",
    key_data_points=["25bps", "6.75% repo rate", "May 2025"],
    mechanism="Inflation breached the 6% upper tolerance band for three consecutive months.",
    implications="Home loan EMIs will increase for floating-rate borrowers; FD rates may follow.",
    content_angles=["Impact on EMIs", "What it means for fixed deposits", "FII reaction"],
)


def _make_article(summary=_VALID_SUMMARY) -> RawContent:
    return RawContent(
        id=uuid4(),
        url="https://www.livemint.com/markets/rbi-rate-hike",
        normalized_url="https://www.livemint.com/markets/rbi-rate-hike",
        title="RBI raises repo rate by 25bps",
        source_name="LiveMint",
        publication_date=datetime(2025, 5, 15, tzinfo=timezone.utc),
        fetch_date=datetime(2025, 5, 15, tzinfo=timezone.utc),
        full_text="Long article text " * 100,
        structured_summary=summary,
        word_count=800,
        pre_score=7.5,
        vision_fallback_used=False,
        paywall_detected=False,
        processed=False,
        created_at=datetime(2025, 5, 15, tzinfo=timezone.utc),
    )


def _make_mock_client(json_text: str, input_tokens: int = 300, output_tokens: int = 120) -> MagicMock:
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json_text)]
    mock_msg.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


class TestGenerateIdeas:
    def test_returns_ideas_on_success(self):
        client = _make_mock_client(json.dumps(_VALID_IDEAS), input_tokens=300, output_tokens=120)
        result = generate_ideas(_make_article(), client, "claude-sonnet-4-5")
        assert isinstance(result, IdeaGenerationResult)
        assert len(result.ideas) == 2
        assert all(isinstance(idea, IdeaCreate) for idea in result.ideas)
        assert result.ideas[0].platform == Platform.LINKEDIN
        assert result.ideas[1].platform == Platform.TWITTER
        assert result.input_tokens == 300
        assert result.output_tokens == 120

    def test_unknown_platform_filtered_out(self):
        ideas_with_unknown = [
            *_VALID_IDEAS,
            {"platform": "tiktok", "angle": "RBI explained in 60 seconds",
             "agent_reasoning": "Short video format.", "score": 6.0},
        ]
        client = _make_mock_client(json.dumps(ideas_with_unknown))
        result = generate_ideas(_make_article(), client, "claude-sonnet-4-5")
        assert len(result.ideas) == 2
        platforms = {idea.platform for idea in result.ideas}
        assert Platform.LINKEDIN in platforms
        assert Platform.TWITTER in platforms

    def test_none_summary_returns_empty(self):
        article = _make_article(summary=None)
        client = MagicMock()
        result = generate_ideas(article, client, "claude-sonnet-4-5")
        assert isinstance(result, IdeaGenerationResult)
        assert result.ideas == []
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        client.messages.create.assert_not_called()

    def test_malformed_json_returns_empty(self):
        client = _make_mock_client("Sorry, I cannot generate ideas for this article.")
        result = generate_ideas(_make_article(), client, "claude-sonnet-4-5")
        assert result.ideas == []
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_api_exception_returns_empty(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Anthropic API error")
        result = generate_ideas(_make_article(), mock_client, "claude-sonnet-4-5")
        assert result.ideas == []
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_markdown_fenced_array_parsed(self):
        fenced = f"```json\n{json.dumps(_VALID_IDEAS)}\n```"
        client = _make_mock_client(fenced)
        result = generate_ideas(_make_article(), client, "claude-sonnet-4-5")
        assert len(result.ideas) == 2
        assert result.ideas[0].platform == Platform.LINKEDIN
