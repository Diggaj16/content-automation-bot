"""
Headline pre-scorer: rates a batch of article titles using Claude Haiku.

One API call per site scrape — all headlines from one section page are batched
into a single message. This is the cheapest possible LLM gate before the
expensive full-article fetch step.

Usage:
    from anthropic import Anthropic
    client = Anthropic(api_key=settings.anthropic_api_key)
    result = pre_score_headlines(titles, client, model=settings.claude_model_light)
    # result.scores[i] is the relevance score for titles[i]
    # result.input_tokens / result.output_tokens go into cost tracking
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from anthropic import Anthropic

from app.utils.logging import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You score news headlines for an Indian personal finance content creator. "
    "Their audience is retail Indian investors interested in stock markets, mutual funds, "
    "bonds, RBI/SEBI policy, IPOs, and macroeconomics affecting Indian markets.\n\n"
    "Score each headline from 0 to 10:\n"
    "10    — Breaking: RBI rate decision, SEBI major regulation, Nifty/Sensex milestone, major IPO\n"
    "8-9   — High relevance: sector earnings, budget implications, bond yield moves, FII flows\n"
    "5-7   — Moderate: company news, global macro with India angle, mutual fund flows\n"
    "2-4   — Low: generic business news, minor company updates, tangential India relevance\n"
    "0-1   — Not relevant: politics without market impact, international news, celebrity finance\n\n"
    "Respond with ONLY a JSON array of numbers in the same order as the input headlines.\n"
    "Example for 3 headlines: [8.5, 3.0, 6.5]"
)


@dataclass
class PreScoreResult:
    """Result from pre_score_headlines."""
    scores: list[float] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


def pre_score_headlines(
    titles: list[str],
    client: Anthropic,
    model: str,
) -> PreScoreResult:
    """
    Score a batch of article headlines using a Claude model.

    Returns a PreScoreResult with one float per title (same order).
    On any failure (API error, malformed JSON, wrong count) returns 5.0 for
    every title and zero token counts — neutral scores so no articles are lost
    due to a transient LLM issue.

    Empty input returns an empty PreScoreResult without making an API call.
    """
    if not titles:
        return PreScoreResult()

    headlines_text = "\n".join(f"{i + 1}. {title}" for i, title in enumerate(titles))

    try:
        # max_tokens: ~6 chars per score entry; 512 covers up to ~300 headlines safely
        message = client.messages.create(
            model=model,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": headlines_text}],
        )
        raw = message.content[0].text.strip()
        scores_raw = json.loads(raw)

        if not isinstance(scores_raw, list) or len(scores_raw) != len(titles):
            raise ValueError(
                f"Expected JSON list of {len(titles)} scores, got: {raw!r}"
            )

        scores = [float(s) for s in scores_raw]
        return PreScoreResult(
            scores=scores,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )

    except Exception as exc:
        logger.warning(
            "pre_score_headlines failed — defaulting all to 5.0",
            extra={"error": str(exc), "title_count": len(titles), "model": model},
        )
        return PreScoreResult(scores=[5.0] * len(titles))
