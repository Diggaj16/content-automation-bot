"""
Content generation module for the creation agent.

Uses Claude Sonnet to write platform-specific content based on an approved idea,
the source article context, and past brand content examples.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Optional

from anthropic import Anthropic

from app.db.models import DraftCreate, Idea, Platform
from app.utils.logging import get_logger

logger = get_logger(__name__)

_MAX_OUTPUT_TOKENS = 2048

_SYSTEM_PROMPT = (
    "You are a content writer for an Indian finance newsletter. "
    "You create engaging, factual content about Indian markets, economy, and finance. "
    "You NEVER give investment advice, buy/sell recommendations, or guaranteed-return claims. "
    "You always ground content in specific data points and dates from the provided context."
)

_PLATFORM_GUIDES: dict[str, str] = {
    "linkedin": (
        "Write a LinkedIn post (1,000–1,500 characters):\n"
        "- Hook: Open with a surprising fact or counter-intuitive insight\n"
        "- Narrative: 2-3 short paragraphs explaining the story\n"
        "- Key insight: One clear takeaway for Indian investors/professionals\n"
        "- CTA: End with a question or reflection prompt\n"
        "- Tone: Professional but conversational, no jargon\n"
        "- Do NOT include investment advice or stock recommendations"
    ),
    "twitter": (
        "Write a Twitter thread (5-7 tweets, each under 280 characters):\n"
        "- Tweet 1: Hook that makes people want to read more (start with 🧵)\n"
        "- Tweets 2-5: One key insight per tweet with data points\n"
        "- Tweet 6-7: Conclusion and takeaway for Indian investors\n"
        "- Separate tweets with a blank line and number them (1/, 2/, etc.)\n"
        "- Do NOT include investment advice or stock recommendations"
    ),
    "blog": (
        "Write a blog post outline (400–600 words):\n"
        "- SEO-friendly title\n"
        "- Introduction paragraph that hooks readers (2-3 sentences)\n"
        "- 4-6 H2 section headings with one brief paragraph each\n"
        "- Conclusion with actionable takeaway\n"
        "- Target audience: Indian retail investors and finance professionals"
    ),
    "email": (
        "Write an email newsletter section (250–400 words):\n"
        "- Subject line (50 chars max)\n"
        "- Preview text (90 chars max)\n"
        "- Body: Personal, conversational tone\n"
        "- 2-3 short paragraphs covering the key story\n"
        "- Why this matters to Indian investors\n"
        "- Do NOT include investment advice or guaranteed-return claims"
    ),
}


@dataclass
class ContentGenerationResult:
    draft_create: Optional[DraftCreate] = None
    input_tokens: int = 0
    output_tokens: int = 0


def generate_content(
    idea: Idea,
    article_context: str,
    brand_context: str,
    client: Anthropic,
    model: str,
) -> ContentGenerationResult:
    """
    Generate platform-specific content for an approved idea using Claude Sonnet.

    Args:
        idea:            The approved Idea (uses edited_angle if set, else angle).
        article_context: Formatted summary of the source article.
        brand_context:   Formatted past brand content examples from match_brand_memory.
        client:          Anthropic sync client.
        model:           Model name (e.g. "claude-sonnet-4-5").

    Returns:
        ContentGenerationResult with draft_create=None on any failure. Never raises.
    """
    angle = idea.edited_angle or idea.angle
    platform = idea.platform.value
    guide = _PLATFORM_GUIDES.get(platform, _PLATFORM_GUIDES["linkedin"])

    context_section = ""
    if article_context:
        context_section = f"\n\nSource article context:\n{article_context}"
    if brand_context:
        context_section += f"\n\n{brand_context}"

    user_prompt = (
        f"Content angle: {angle}\n"
        f"Platform: {platform}\n"
        f"{context_section}\n\n"
        f"Platform writing guide:\n{guide}\n\n"
        "Return ONLY a JSON object with these exact keys:\n"
        '{"content_text": "the complete content ready to post", '
        '"reasoning": "1-2 sentences explaining why this angle works for this platform"}'
    )

    try:
        message = client.messages.create(
            model=model,
            max_tokens=_MAX_OUTPUT_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens

        if not message.content:
            logger.warning("generate_content: empty content list in response")
            return ContentGenerationResult(input_tokens=input_tokens, output_tokens=output_tokens)

        raw = message.content[0].text

        # Strip markdown fences if present
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            logger.warning(f"generate_content: no JSON object found in response | platform={platform}")
            return ContentGenerationResult(input_tokens=input_tokens, output_tokens=output_tokens)

        data = json.loads(match.group())
        content_text = data.get("content_text", "").strip()
        reasoning = data.get("reasoning", "").strip()

        if not content_text:
            logger.warning(f"generate_content: empty content_text | platform={platform}")
            return ContentGenerationResult(input_tokens=input_tokens, output_tokens=output_tokens)

        draft_create = DraftCreate(
            platform=idea.platform,
            content_text=content_text,
            agent_reasoning=reasoning or f"Generated for {platform}",
            source_idea_id=idea.id,
            finance_flags=[],  # Populated separately by finance_flags module
        )

        return ContentGenerationResult(
            draft_create=draft_create,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    except json.JSONDecodeError as exc:
        logger.warning(f"generate_content: JSON parse error | platform={platform} | err={exc}")
        return ContentGenerationResult()
    except Exception as exc:
        logger.error(f"generate_content: API error | platform={platform} | err={exc}")
        return ContentGenerationResult()
