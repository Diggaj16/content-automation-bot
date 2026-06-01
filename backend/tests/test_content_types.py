"""Tests for ContentType-aware content generation."""
from unittest.mock import MagicMock


def _make_idea():
    from app.db.models import Idea, Platform, ApprovalStatus
    from uuid import uuid4
    from datetime import datetime, timezone
    return Idea(
        id=uuid4(),
        platform=Platform.LINKEDIN,
        angle="Why SEBI just changed debt fund rules",
        edited_angle=None,
        source_article_id=None,
        agent_reasoning="High interest",
        source_article_date=None,
        approval_status=ApprovalStatus.APPROVED,
        score=8.0,
        recent_coverage_flag=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_news_driven_excludes_kb_context():
    """news_driven: prompt must NOT include KB context even if kb_context is provided."""
    from app.agents.creation.content_generator import generate_content

    client = MagicMock()
    msg = MagicMock()
    msg.usage.input_tokens = 100
    msg.usage.output_tokens = 50
    msg.content = [MagicMock(text='{"content_text": "Post text here.", "reasoning": "Good angle"}')]
    client.messages.create.return_value = msg

    generate_content(
        _make_idea(),
        article_context="Article about SEBI",
        brand_context="",
        client=client,
        model="claude-haiku-4-5",
        kb_context="Some KB data",
        content_type="news_driven",
    )

    call_kwargs = client.messages.create.call_args[1]
    prompt = call_kwargs["messages"][0]["content"]
    assert "Some KB data" not in prompt


def test_kb_driven_excludes_article_context():
    """kb_driven: prompt must NOT include article_context even if provided."""
    from app.agents.creation.content_generator import generate_content

    client = MagicMock()
    msg = MagicMock()
    msg.usage.input_tokens = 100
    msg.usage.output_tokens = 50
    msg.content = [MagicMock(text='{"content_text": "Post text here.", "reasoning": "Good angle"}')]
    client.messages.create.return_value = msg

    generate_content(
        _make_idea(),
        article_context="Article about SEBI",
        brand_context="",
        client=client,
        model="claude-haiku-4-5",
        kb_context="Some KB data about debt funds",
        content_type="kb_driven",
    )

    call_kwargs = client.messages.create.call_args[1]
    prompt = call_kwargs["messages"][0]["content"]
    assert "Article about SEBI" not in prompt
    assert "Some KB data" in prompt


def test_combined_includes_both():
    """combined: prompt must include both article_context and kb_context."""
    from app.agents.creation.content_generator import generate_content

    client = MagicMock()
    msg = MagicMock()
    msg.usage.input_tokens = 100
    msg.usage.output_tokens = 50
    msg.content = [MagicMock(text='{"content_text": "Post text here.", "reasoning": "Good angle"}')]
    client.messages.create.return_value = msg

    generate_content(
        _make_idea(),
        article_context="Article about SEBI",
        brand_context="",
        client=client,
        model="claude-haiku-4-5",
        kb_context="Some KB data about debt funds",
        content_type="combined",
    )

    call_kwargs = client.messages.create.call_args[1]
    prompt = call_kwargs["messages"][0]["content"]
    assert "Article about SEBI" in prompt
    assert "Some KB data" in prompt


def test_default_content_type_is_news_driven():
    """When content_type is not specified, behaves as news_driven."""
    from app.agents.creation.content_generator import generate_content

    client = MagicMock()
    msg = MagicMock()
    msg.usage.input_tokens = 100
    msg.usage.output_tokens = 50
    msg.content = [MagicMock(text='{"content_text": "Post text here.", "reasoning": "Good angle"}')]
    client.messages.create.return_value = msg

    generate_content(
        _make_idea(),
        article_context="Article data",
        brand_context="",
        client=client,
        model="claude-haiku-4-5",
        kb_context="KB data that should be excluded",
    )

    call_kwargs = client.messages.create.call_args[1]
    prompt = call_kwargs["messages"][0]["content"]
    assert "KB data that should be excluded" not in prompt
