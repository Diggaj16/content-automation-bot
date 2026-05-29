# tests/agents/creation/test_content_generator.py
"""Tests for content_generator.generate_content."""
import json
import datetime
from unittest.mock import MagicMock
from uuid import UUID

from app.agents.creation.content_generator import generate_content, ContentGenerationResult
from app.db.models import Idea, Platform, ApprovalStatus


def _make_idea(platform: str = "linkedin", angle: str = "SEBI new circular impacts AMCs") -> Idea:
    return Idea(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        platform=Platform(platform),
        angle=angle,
        edited_angle=None,
        source_article_id=None,
        agent_reasoning="Strong relevance to Indian investors",
        source_article_date=None,
        approval_status=ApprovalStatus.APPROVED,
        score=8.2,
        recent_coverage_flag=False,
        created_at=datetime.datetime(2026, 5, 29, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(2026, 5, 29, tzinfo=datetime.timezone.utc),
    )


def _mock_anthropic(content_text: str = "Generated LinkedIn post.", reasoning: str = "Good angle."):
    client = MagicMock()
    response_json = json.dumps({"content_text": content_text, "reasoning": reasoning})
    msg = MagicMock()
    msg.content = [MagicMock(text=response_json)]
    msg.usage.input_tokens = 100
    msg.usage.output_tokens = 200
    client.messages.create.return_value = msg
    return client


# ─── happy path ───────────────────────────────────────────────────────────────

def test_returns_draft_create_on_success():
    idea = _make_idea("linkedin")
    client = _mock_anthropic("A great LinkedIn post about SEBI.", "Strong angle.")
    result = generate_content(idea, "Article context.", "Brand context.", client, "claude-sonnet-4-5")
    assert result.draft_create is not None
    assert result.draft_create.content_text == "A great LinkedIn post about SEBI."
    assert result.draft_create.agent_reasoning == "Strong angle."
    assert result.draft_create.platform == Platform.LINKEDIN
    assert result.draft_create.source_idea_id == idea.id
    assert result.input_tokens == 100
    assert result.output_tokens == 200


def test_uses_edited_angle_when_available():
    idea = _make_idea("twitter", "original angle")
    idea = idea.model_copy(update={"edited_angle": "EDITED: better angle"})
    client = _mock_anthropic("Twitter thread.")
    generate_content(idea, "", "", client, "model")
    prompt_text = str(client.messages.create.call_args)
    assert "EDITED: better angle" in prompt_text


def test_token_counts_tracked():
    result = generate_content(_make_idea(), "", "", _mock_anthropic(), "model")
    assert result.input_tokens == 100
    assert result.output_tokens == 200


def test_finance_flags_list_is_empty_by_default():
    result = generate_content(_make_idea(), "", "", _mock_anthropic(), "model")
    assert result.draft_create is not None
    assert result.draft_create.finance_flags == []


# ─── JSON parsing robustness ──────────────────────────────────────────────────

def test_handles_json_in_markdown_fences():
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text='```json\n{"content_text": "Post content.", "reasoning": "Good."}\n```')]
    msg.usage.input_tokens = 50
    msg.usage.output_tokens = 80
    client.messages.create.return_value = msg
    result = generate_content(_make_idea(), "", "", client, "model")
    assert result.draft_create is not None
    assert result.draft_create.content_text == "Post content."


def test_returns_none_draft_on_invalid_json():
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text="not json at all")]
    msg.usage.input_tokens = 30
    msg.usage.output_tokens = 10
    client.messages.create.return_value = msg
    result = generate_content(_make_idea(), "", "", client, "model")
    assert result.draft_create is None


def test_returns_none_draft_on_api_error():
    client = MagicMock()
    client.messages.create.side_effect = RuntimeError("API timeout")
    result = generate_content(_make_idea(), "", "", client, "model")
    assert result.draft_create is None
    assert result.input_tokens == 0
    assert result.output_tokens == 0


def test_returns_none_on_empty_content_list():
    client = MagicMock()
    msg = MagicMock()
    msg.content = []
    msg.usage.input_tokens = 10
    msg.usage.output_tokens = 5
    client.messages.create.return_value = msg
    result = generate_content(_make_idea(), "", "", client, "model")
    assert result.draft_create is None
