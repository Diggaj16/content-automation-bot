"""
Platform posting stubs for the publishing agent.

These are no-ops that simulate successful posting and return a generated identifier.
Replace each function with a real API call when platform credentials are available.
"""
import uuid
from typing import Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)


def post_linkedin(content_text: str, settings) -> str:
    logger.info(f"poster: [STUB] LinkedIn | chars={len(content_text)}")
    return f"linkedin-stub-{uuid.uuid4().hex[:8]}"


def post_twitter(content_text: str, settings) -> str:
    logger.info(f"poster: [STUB] Twitter | chars={len(content_text)}")
    return f"twitter-stub-{uuid.uuid4().hex[:8]}"


def post_blog(content_text: str, settings) -> str:
    logger.info(f"poster: [STUB] Blog | chars={len(content_text)}")
    return f"blog-stub-{uuid.uuid4().hex[:8]}"


def post_email(content_text: str, settings) -> str:
    logger.info(f"poster: [STUB] Email | chars={len(content_text)}")
    return f"email-stub-{uuid.uuid4().hex[:8]}"


_PLATFORM_POSTERS = {
    "linkedin": post_linkedin,
    "twitter":  post_twitter,
    "blog":     post_blog,
    "email":    post_email,
}


def post_to_platform(platform: str, content_text: str, settings) -> Optional[str]:
    """
    Dispatch to the correct platform poster.
    Returns a post_identifier string on success, None if unknown platform or error. Never raises.
    """
    poster = _PLATFORM_POSTERS.get(platform)
    if poster is None:
        logger.error(f"post_to_platform: unknown platform | platform={platform}")
        return None
    try:
        return poster(content_text, settings)
    except Exception as exc:
        logger.error(f"post_to_platform: failed | platform={platform} | err={exc}")
        return None
