# tests/agents/publishing/test_poster.py
"""Tests for publishing poster module."""
from unittest.mock import MagicMock
from app.agents.publishing.poster import post_to_platform


def test_post_to_platform_linkedin_returns_identifier():
    result = post_to_platform("linkedin", "LinkedIn post content.", MagicMock())
    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0


def test_post_to_platform_twitter_returns_identifier():
    result = post_to_platform("twitter", "Twitter thread content.", MagicMock())
    assert result is not None
    assert isinstance(result, str)


def test_post_to_platform_blog_returns_identifier():
    result = post_to_platform("blog", "Blog post outline.", MagicMock())
    assert result is not None


def test_post_to_platform_email_returns_identifier():
    result = post_to_platform("email", "Email newsletter.", MagicMock())
    assert result is not None


def test_post_to_platform_unknown_returns_none():
    result = post_to_platform("unknown_platform", "content", MagicMock())
    assert result is None


def test_post_to_platform_never_raises():
    result = post_to_platform("linkedin", "", MagicMock())
    assert isinstance(result, (str, type(None)))
