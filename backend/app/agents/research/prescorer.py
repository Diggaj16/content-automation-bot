"""
Headline pre-scorer: rates a batch of article titles using Claude Haiku.

Large batches are automatically split into chunks of _CHUNK_SIZE so no single
API call receives more titles than the model can reliably score in one response.
Results are merged back into a single PreScoreResult in original order.

Rate-limit (429) and empty-response errors are retried with exponential backoff
up to _MAX_RETRIES times before giving up and setting failed=True.

Usage:
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    result = await async_pre_score_headlines(titles, client, model=settings.claude_model_light)
    # result.scores[i] is the relevance score for titles[i]
    # result.failed is True when all retries exhausted; callers bypass threshold filter
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field

from anthropic import APIConnectionError, Anthropic, AsyncAnthropic, RateLimitError

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Max headlines per API call — keeps output tokens well under budget.
_CHUNK_SIZE = 40

# Token budget per chunk: 40 scores × ~8 tokens each + brackets + preamble buffer.
_MAX_TOKENS = 1024

# Retry config for transient failures (rate limits, empty responses).
_MAX_RETRIES = 3
_BASE_BACKOFF = 15  # seconds; doubles each retry: 15 → 30 → 60

_SYSTEM_PROMPT = (
    "You score news headlines for Growthvine Capital, a boutique wealth management firm "
    "in Gurgaon. Their clients are professionals, executives, founders, HNIs, and NRIs — "
    "people who are financially aware but not finance professionals. Growthvine creates "
    "content that connects market events to real financial impact, decodes complexity, "
    "and helps this audience make better decisions about their money.\n\n"
    "Score each headline from 0 to 10 based on TWO dimensions combined:\n\n"
    "1. RELEVANCE — how directly the story affects the financial life, portfolio, or "
    "decisions of Growthvine's audience (professionals, founders, HNIs, NRIs)\n\n"
    "2. VIRALITY POTENTIAL — how much noise, conversation, and coverage this story is "
    "generating or is likely to generate. Stories that everyone is talking about create "
    "a virality loop: when Growthvine publishes on a trending topic with a clear, "
    "well-reasoned angle, it benefits from existing search and social momentum. "
    "High virality stories include: market crashes or sharp rallies, major budget or "
    "policy announcements, events dominating business news, global triggers with India "
    "impact (Fed decisions, oil price shocks, geopolitical events), and any story where "
    "the audience is already asking questions and looking for clarity.\n\n"
    "A story can score high if it is strong on EITHER dimension — very high relevance "
    "with moderate virality, or very high virality with moderate relevance. A story that "
    "is strong on BOTH should score 9 or above.\n\n"
    "10    — Maximum on both: a breaking macro event (RBI rate cut, market crash, major "
    "budget announcement) that is dominating headlines AND directly affects the audience's "
    "portfolios, EMIs, or investment decisions\n"
    "8-9   — Strong on one, solid on the other: either a highly relevant story with clear "
    "content potential, or a widely discussed story where Growthvine can add a sharp, "
    "differentiated angle for their audience\n"
    "5-7   — Moderate on both: useful content can be built but the story is either niche "
    "or not generating enough buzz to ride a virality loop\n"
    "2-4   — Low relevance and low virality: niche corporate news, overly technical "
    "regulatory updates, or stories too narrow to build engaging content around\n"
    "0-1   — Not relevant: day-trading tips, celebrity finance, pure politics with no "
    "economic angle, PR-driven announcements with no market significance\n\n"
    "Respond with ONLY a JSON array of numbers in the same order as the input headlines.\n"
    "Example for 3 headlines: [8.5, 3.0, 6.5]"

)


@dataclass
class PreScoreResult:
    """Result from pre_score_headlines."""
    scores: list[float] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    failed: bool = False  # True when all retries exhausted; callers should bypass threshold filter


def _parse_scores(raw: str, expected: int) -> list[float]:
    """
    Parse the model's JSON array response and validate the count.

    Tolerates junk around the JSON array (preamble prose, trailing explanation,
    markdown code fences, newlines inside the array) by falling back to a regex
    extraction when json.loads fails on the full response text.
    """
    if not raw:
        raise ValueError("Empty response from model")
    try:
        scores_raw = json.loads(raw)
    except json.JSONDecodeError:
        # Model wrapped the array in prose or added trailing text — extract it.
        # re.DOTALL so \s matches newlines inside multi-line arrays.
        match = re.search(r"\[[\d\s.,+-]+\]", raw, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON array found in response: {raw!r}")
        scores_raw = json.loads(match.group())

    if not isinstance(scores_raw, list) or len(scores_raw) != expected:
        raise ValueError(
            f"Expected JSON list of {expected} scores, got: {raw!r}"
        )
    return [float(s) for s in scores_raw]


def _retry_after(exc: RateLimitError) -> float:
    """Extract the Retry-After seconds from a RateLimitError response header."""
    try:
        return float(exc.response.headers.get("retry-after", _BASE_BACKOFF))
    except Exception:
        return float(_BASE_BACKOFF)


def pre_score_headlines(
    titles: list[str],
    client: Anthropic,
    model: str,
) -> PreScoreResult:
    """
    Score a batch of article headlines using a Claude model (sync version).

    Large batches are split into chunks of _CHUNK_SIZE and merged.
    Rate-limit and empty-response errors are retried with backoff.
    On permanent failure sets failed=True — callers should bypass the threshold filter.
    Empty input returns an empty PreScoreResult without making an API call.
    """
    if not titles:
        return PreScoreResult()

    all_scores: list[float] = []
    total_in = total_out = 0

    for chunk_start in range(0, len(titles), _CHUNK_SIZE):
        chunk = titles[chunk_start: chunk_start + _CHUNK_SIZE]
        headlines_text = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(chunk))
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                message = client.messages.create(
                    model=model,
                    max_tokens=_MAX_TOKENS,
                    system=_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": headlines_text}],
                )
                raw = message.content[0].text.strip()
                chunk_scores = _parse_scores(raw, len(chunk))
                all_scores.extend(chunk_scores)
                total_in += message.usage.input_tokens
                total_out += message.usage.output_tokens
                last_exc = None
                break  # success

            except RateLimitError as exc:
                last_exc = exc
                wait = _retry_after(exc) * (2 ** attempt)
                logger.warning(
                    f"pre_score_headlines rate-limited (attempt {attempt + 1}/{_MAX_RETRIES}), "
                    f"waiting {wait:.0f}s — chunk {chunk_start}–{chunk_start + len(chunk) - 1}, model={model}",
                )
                time.sleep(wait)

            except (ValueError, json.JSONDecodeError, APIConnectionError) as exc:
                last_exc = exc
                wait = _BASE_BACKOFF * (2 ** attempt)
                logger.warning(
                    f"pre_score_headlines bad response (attempt {attempt + 1}/{_MAX_RETRIES}): {exc} — "
                    f"waiting {wait:.0f}s before retry, chunk {chunk_start}–{chunk_start + len(chunk) - 1}",
                )
                time.sleep(wait)

            except Exception as exc:
                last_exc = exc
                break  # non-transient — don't retry

        if last_exc is not None:
            logger.warning(
                f"pre_score_headlines failed permanently ({type(last_exc).__name__}: {last_exc}) — "
                f"chunk {chunk_start}–{chunk_start + len(chunk) - 1} of {len(titles)} titles, model={model}",
            )
            return PreScoreResult(scores=[0.0] * len(titles), failed=True)

    return PreScoreResult(scores=all_scores, input_tokens=total_in, output_tokens=total_out)


async def async_pre_score_headlines(
    titles: list[str],
    client: AsyncAnthropic,
    model: str,
) -> PreScoreResult:
    """
    Score a batch of article headlines using a Claude model (async version).

    Large batches are split into chunks of _CHUNK_SIZE and merged.
    Rate-limit and empty-response errors are retried with backoff.
    On permanent failure sets failed=True — callers should bypass the threshold filter.
    Empty input returns an empty PreScoreResult without making an API call.
    """
    if not titles:
        return PreScoreResult()

    all_scores: list[float] = []
    total_in = total_out = 0

    for chunk_start in range(0, len(titles), _CHUNK_SIZE):
        chunk = titles[chunk_start: chunk_start + _CHUNK_SIZE]

        # Filter blank titles — Claude returns explanation instead of scores when the
        # message body is empty (e.g. a title that is whitespace-only).
        # Keep index mapping so we can reinsert 0.0 for skipped slots.
        valid_indices = [i for i, t in enumerate(chunk) if t.strip()]
        if not valid_indices:
            all_scores.extend([0.0] * len(chunk))
            continue
        valid_titles = [chunk[i] for i in valid_indices]
        headlines_text = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(valid_titles))
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                message = await client.messages.create(
                    model=model,
                    max_tokens=_MAX_TOKENS,
                    system=_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": headlines_text}],
                )
                raw = message.content[0].text.strip()
                chunk_scores_valid = _parse_scores(raw, len(valid_titles))
                # Reinsert 0.0 for blank-title slots
                chunk_scores = [0.0] * len(chunk)
                for idx, score in zip(valid_indices, chunk_scores_valid):
                    chunk_scores[idx] = score
                all_scores.extend(chunk_scores)
                total_in += message.usage.input_tokens
                total_out += message.usage.output_tokens
                last_exc = None
                break  # success

            except RateLimitError as exc:
                last_exc = exc
                wait = _retry_after(exc) * (2 ** attempt)
                logger.warning(
                    f"async_pre_score_headlines rate-limited (attempt {attempt + 1}/{_MAX_RETRIES}), "
                    f"waiting {wait:.0f}s — chunk {chunk_start}–{chunk_start + len(chunk) - 1}, model={model}",
                )
                await asyncio.sleep(wait)

            except (ValueError, json.JSONDecodeError, APIConnectionError) as exc:
                last_exc = exc
                wait = _BASE_BACKOFF * (2 ** attempt)
                logger.warning(
                    f"async_pre_score_headlines transient error (attempt {attempt + 1}/{_MAX_RETRIES}): {exc} — "
                    f"waiting {wait:.0f}s before retry, chunk {chunk_start}–{chunk_start + len(chunk) - 1}",
                )
                await asyncio.sleep(wait)

            except Exception as exc:
                last_exc = exc
                break  # non-transient — don't retry

        if last_exc is not None:
            logger.warning(
                f"async_pre_score_headlines failed permanently ({type(last_exc).__name__}: {last_exc}) — "
                f"chunk {chunk_start}–{chunk_start + len(chunk) - 1} of {len(titles)} titles, model={model}",
            )
            return PreScoreResult(scores=[0.0] * len(titles), failed=True)

    return PreScoreResult(scores=all_scores, input_tokens=total_in, output_tokens=total_out)
