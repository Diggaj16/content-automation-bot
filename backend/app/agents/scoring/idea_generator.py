"""
Idea generator for the scoring agent.

Calls Claude Sonnet to produce a list of content ideas (IdeaCreate) from a
scored article. Each idea specifies a platform, angle, reasoning, and score.

Usage:
    result = generate_ideas(article, client, settings.claude_model_heavy)
    # result.ideas:         list[IdeaCreate]
    # result.input_tokens:  int
    # result.output_tokens: int
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from anthropic import Anthropic

from app.db.models import IdeaCreate, Platform, RawContent
from app.utils.logging import get_logger

logger = get_logger(__name__)

_MAX_OUTPUT_TOKENS = 1024
_KNOWN_PLATFORMS = frozenset(p.value for p in Platform)

_SYSTEM_PROMPT = (
    "You are a sophisticated content strategist for Growthvine Capital, an elite wealth "
    "management and portfolio management firm in Gurgaon. Your audience consists entirely "
    "of highly technical professionals who have cleared CFA Level 3, including portfolio "
    "managers, institutional investors, and seasoned wealth advisors.\n\n"
    "Given a structured article summary, generate content ideas for the firm's platforms "
    "that meet the rigorous standards of CFA charterholders. Focus on deep portfolio "
    "implications, risk-adjusted returns, macro/micro economic shifts, asset allocation "
    "strategies, and institutional-grade analysis. DO NOT generate superficial or generic "
    "retail finance 'bullshit'. Respond with ONLY a JSON array — no markdown, no extra keys:\n\n"
    "[\n"
    "  {\n"
    '    "platform": "linkedin" | "twitter" | "blog" | "email",\n'
    '    "angle": "<advanced, descriptive analytical hook or angle for this platform>",\n'
    '    "agent_reasoning": "<why this sophisticated angle engages CFA Level 3 cleared professionals>",\n'
    '    "score": <float 0.0-10.0 representing institutional novelty + technical depth>\n'
    "  },\n"
    "  ...\n"
    "]\n\n"
    "Generate exactly 2 ideas, each on a different platform. Respond with nothing but the JSON array."
)


@dataclass
class IdeaGenerationResult:
    """Result from generate_ideas."""
    ideas:         list[IdeaCreate] = field(default_factory=list)
    input_tokens:  int              = 0
    output_tokens: int              = 0


def _empty_result() -> IdeaGenerationResult:
    return IdeaGenerationResult()


def generate_ideas(
    article: RawContent,
    client: Anthropic,
    model: str,
    rejection_summary: str = "",
) -> IdeaGenerationResult:
    """
    Generate a list of IdeaCreate objects from a scored article.

    Never raises. Returns empty IdeaGenerationResult on any failure.
    If article.structured_summary is None, returns empty immediately.
    """
    if article.structured_summary is None:
        return _empty_result()

    s = article.structured_summary
    key_points_str = "\n".join(f"- {pt}" for pt in s.key_data_points)
    angles_str = "\n".join(f"- {a}" for a in s.content_angles)

    rejection_block = (
        f"\n\nREJECTION PATTERNS TO AVOID:\n{rejection_summary}"
        if rejection_summary else ""
    )
    user_content = (
        f"Title: {article.title}\n\n"
        f"Story narrative:\n{s.story_narrative}\n\n"
        f"Key data points:\n{key_points_str}\n\n"
        f"Mechanism:\n{s.mechanism}\n\n"
        f"Implications:\n{s.implications}\n\n"
        f"Suggested content angles:\n{angles_str}"
        f"{rejection_block}"
    )

    try:
        message = client.messages.create(
            model=model,
            max_tokens=_MAX_OUTPUT_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        if not message.content:
            logger.warning("generate_ideas: empty content list", extra={"title": article.title})
            return _empty_result()

        raw = message.content[0].text.strip()

        json_match = re.search(r'\[.*\]', raw, re.DOTALL)
        if not json_match:
            logger.warning("generate_ideas: no JSON array found", extra={"title": article.title, "raw": raw[:200]})
            return _empty_result()

        items = json.loads(json_match.group(0))

        ideas: list[IdeaCreate] = []
        for item in items:
            platform_str = item.get("platform", "")
            if platform_str not in _KNOWN_PLATFORMS:
                logger.warning("generate_ideas: unknown platform filtered out", extra={"platform": platform_str})
                continue
            ideas.append(IdeaCreate(
                platform=Platform(platform_str),
                angle=item["angle"],
                agent_reasoning=item["agent_reasoning"],
                score=float(item["score"]),
            ))

        return IdeaGenerationResult(
            ideas=ideas,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )

    except Exception as exc:
        logger.warning("generate_ideas failed", extra={"title": article.title, "error": str(exc)})
        return _empty_result()
