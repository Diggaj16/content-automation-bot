"""
Article summariser: calls Claude Sonnet to produce a StructuredSummary.

Usage:
    result = summarise_article(full_text, title, client, model)
    # result.summary: StructuredSummary
    # result.input_tokens / result.output_tokens: for cost tracking
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from anthropic import Anthropic

from app.db.models import StructuredSummary
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Truncate article text to this many characters before sending to Claude.
# Prevents accidental huge prompts; ~12 000 chars ≈ 3 000 words — more than
# enough for a thorough summary of any news article.
_MAX_ARTICLE_CHARS = 12_000

# Maximum tokens Claude may return for a summary response.
_MAX_OUTPUT_TOKENS = 1024

_SYSTEM_PROMPT = (
    "You are a financial journalist writing structured summaries for an Indian "
    "personal finance content creator. Analyse the article and respond with ONLY "
    "a JSON object matching this exact schema — no markdown, no extra keys:\n\n"
    "{\n"
    '  "story_narrative": "<2-3 sentence hook that captures the core story>",\n'
    '  "key_data_points": ["<specific number/date/name>", ...],\n'
    '  "mechanism": "<1-2 sentences explaining the underlying cause>",\n'
    '  "implications": "<1-2 sentences on what this means for Indian investors>",\n'
    '  "content_angles": ["<angle 1>", "<angle 2>"]\n'
    "}\n\n"
    "key_data_points and content_angles must be JSON arrays (even if empty). "
    "Respond with nothing but the JSON object."
)


@dataclass
class SummaryResult:
    summary: StructuredSummary
    input_tokens: int = 0
    output_tokens: int = 0


_KNOWN_FIELDS = frozenset(StructuredSummary.model_fields.keys())


def _fallback_summary(title: str) -> SummaryResult:
    """Minimal StructuredSummary used when Claude fails."""
    return SummaryResult(
        summary=StructuredSummary(
            story_narrative=title,
            key_data_points=[],
            mechanism="",
            implications="",
            content_angles=[],
        ),
        input_tokens=0,
        output_tokens=0,
    )


def summarise_article(
    full_text: str,
    title: str,
    client: Anthropic,
    model: str,
) -> SummaryResult:
    """
    Generate a StructuredSummary for an article.

    Never raises. On any failure returns a minimal StructuredSummary so the
    article is still stored and processed downstream.
    """
    truncated = full_text[:_MAX_ARTICLE_CHARS]
    user_content = f"Title: {title}\n\n{truncated}"

    try:
        message = client.messages.create(
            model=model,
            max_tokens=_MAX_OUTPUT_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        if not message.content:
            logger.warning("summarise_article: empty content list in API response", extra={"title": title})
            return _fallback_summary(title)
        raw = message.content[0].text.strip()
        # Strip markdown code fences if Claude wraps the response
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            raw = json_match.group(0)
        data = json.loads(raw)
        filtered = {k: v for k, v in data.items() if k in _KNOWN_FIELDS}
        summary = StructuredSummary(**filtered)
        return SummaryResult(
            summary=summary,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )
    except Exception as exc:
        logger.warning(
            "summarise_article failed — using fallback",
            extra={"title": title, "error": str(exc)},
        )
        return _fallback_summary(title)
