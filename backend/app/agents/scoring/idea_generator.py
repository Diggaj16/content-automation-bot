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
    "You are a content strategist for Growthvine Capital, an Indian wealth-management and "
    "advisory firm. Your readers are financially-aware Indians — HNIs, professionals, founders, "
    "advisors, and serious retail investors. They are smart and curious but not necessarily "
    "finance specialists, so good ideas explain the mechanism behind a story, not just the "
    "headline.\n\n"
    "Given a structured article summary and its identified affected segments, generate content "
    "ideas for the firm's platforms. Each idea MUST target a specific, relatable persona drawn "
    "from the affected_segments (e.g. first-time investors, small business owners, NRIs, working "
    "professionals planning for retirement, founders managing treasury, or seasoned investors — "
    "whichever fits the article). Focus on a real mechanism, a concrete number, or a non-obvious "
    "implication from the source material — not a generic restatement of the headline, and not "
    "vague 'markets are interesting' filler. Depth means a specific, well-explained cause-and-effect, "
    "not jargon density — avoid acronyms and technical terms unless you'd also explain them in one "
    "clause. Respond with ONLY a JSON array — no markdown, no extra keys:\n\n"
    "[\n"
    "  {\n"
    '    "platform": "linkedin" | "twitter" | "blog" | "email" | "whatsapp" | "carousel" | "advisor_talking_points",\n'
    '    "target_persona": "<specific, relatable investor or reader segment this targets>",\n'
    '    "angle": "<a clear, concrete hook — the specific mechanism or number this idea will explain>",\n'
    '    "agent_reasoning": "<why this angle is genuinely useful or surprising to this persona>",\n'
    '    "score": <float 0.0-10.0 representing how novel and well-grounded the angle is>\n'
    "  },\n"
    "  ...\n"
    "]\n\n"
    "Generate exactly 3 ideas across different platforms, tailored to different personas "
    "from the affected_segments. Respond with nothing but the JSON array."
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
    segments_str = "\n".join(f"- {seg}" for seg in s.affected_segments)
    sentiment_str = s.sentiment

    user_content = (
        f"Title: {article.title}\n\n"
        f"Story narrative:\n{s.story_narrative}\n\n"
        f"Sentiment: {sentiment_str}\n\n"
        f"Key data points:\n{key_points_str}\n\n"
        f"Mechanism:\n{s.mechanism}\n\n"
        f"Implications:\n{s.implications}\n\n"
        f"Suggested content angles:\n{angles_str}\n\n"
        f"Affected Segments:\n{segments_str}"
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
                target_persona=item.get("target_persona"),
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
