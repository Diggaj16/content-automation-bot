# Research Agent Part 2 — Filters and Pre-scorer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the two cheap-filter layers that sit between the homepage scraper and the expensive full-article fetch — a dedup/age/word-count filter and a Claude Haiku headline pre-scorer.

**Architecture:** `filters.py` contains three pure/simple functions: `is_url_seen` (sync Supabase SELECT), `is_article_fresh` (datetime arithmetic), `is_article_long_enough` (integer comparison). `prescorer.py` batches all headlines from one site into a single Claude Haiku call and returns `PreScoreResult` (scores + token usage). Keeping costs in the result lets Part 3 accumulate them into `run_logs`. Both modules never raise — failures return safe defaults so the pipeline keeps running.

**Tech Stack:** `anthropic>=0.90.0` (sync `Anthropic` client), `supabase>=2.3.0` (sync `.table().select()` chain), `pydantic>=2.5.0`, `pytest-mock`

---

## File Structure

```
backend/
  app/
    agents/
      research/
        filters.py      CREATE — is_url_seen, is_article_fresh, is_article_long_enough
        prescorer.py    CREATE — PreScoreResult dataclass + pre_score_headlines()
tests/
  agents/
    research/
      test_filters.py   CREATE — unit tests for all three filter functions
      test_prescorer.py CREATE — unit tests for pre_score_headlines
```

No existing files are modified.

---

### Task 15: Article filters — dedup, age, word count

**Files:**
- Create: `backend/app/agents/research/filters.py`
- Test: `backend/tests/agents/research/test_filters.py`

#### Background

These filters run in order from cheapest to most expensive:

1. **Dedup** (`is_url_seen`) — one Supabase SELECT on `raw_content.normalized_url`. If the article is already in the DB, skip it entirely. The normalised URL from Part 1's `normalize_url()` is what's stored in the DB, so the check is an exact equality query.

2. **Age filter** (`is_article_fresh`) — compares `publication_date` to `datetime.now(UTC)`. Articles without a pub date are treated as fresh (we cannot reject without fetching; age will be confirmed after the full article is retrieved in Part 3). Uses an injectable `now` parameter so tests can pin the clock.

3. **Word count filter** (`is_article_long_enough`) — purely numeric: `word_count >= min_words`.

The Supabase client (`supabase-py`) is **synchronous**. We call it directly from async contexts — one fast HTTP call per article link, acceptable latency. No `asyncio.to_thread` wrapping needed at this stage.

#### Supabase call pattern (for reference)

```python
# The fluent chain used in is_url_seen:
response = (
    supabase
    .table("raw_content")
    .select("id")
    .eq("normalized_url", normalized_url)
    .limit(1)
    .execute()
)
found = len(response.data) > 0
```

#### How to mock the Supabase chain in tests

```python
# Fluent chain mock — must match exactly:
mock_sb = MagicMock()
mock_sb.table.return_value \
       .select.return_value \
       .eq.return_value \
       .limit.return_value \
       .execute.return_value \
       .data = []           # empty → not seen
```

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/agents/research/test_filters.py`:

```python
"""Unit tests for app.agents.research.filters."""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

from app.agents.research.filters import (
    is_url_seen,
    is_article_fresh,
    is_article_long_enough,
)


# ── is_url_seen ───────────────────────────────────────────────────────────────

def _make_supabase_mock(rows: list[dict]) -> MagicMock:
    """Supabase mock whose .execute().data returns `rows`."""
    mock = MagicMock()
    (
        mock.table.return_value
        .select.return_value
        .eq.return_value
        .limit.return_value
        .execute.return_value
        .data
    ) = rows
    return mock


class TestIsUrlSeen:
    def test_returns_false_when_not_in_db(self):
        sb = _make_supabase_mock(rows=[])
        assert is_url_seen("https://example.com/article", sb) is False

    def test_returns_true_when_found(self):
        sb = _make_supabase_mock(rows=[{"id": "abc123"}])
        assert is_url_seen("https://example.com/article", sb) is True

    def test_calls_correct_table(self):
        sb = _make_supabase_mock(rows=[])
        is_url_seen("https://example.com/article", sb)
        sb.table.assert_called_once_with("raw_content")

    def test_queries_normalized_url_field(self):
        sb = _make_supabase_mock(rows=[])
        is_url_seen("https://example.com/article", sb)
        sb.table.return_value.select.return_value.eq.assert_called_once_with(
            "normalized_url", "https://example.com/article"
        )

    def test_limits_to_one_row(self):
        sb = _make_supabase_mock(rows=[])
        is_url_seen("https://example.com/article", sb)
        sb.table.return_value.select.return_value.eq.return_value.limit.assert_called_once_with(1)


# ── is_article_fresh ─────────────────────────────────────────────────────────

_NOW = datetime(2025, 5, 15, 12, 0, 0, tzinfo=timezone.utc)


class TestIsArticleFresh:
    def test_fresh_article_within_limit(self):
        pub = _NOW - timedelta(days=3)
        assert is_article_fresh(pub, max_age_days=7, now=_NOW) is True

    def test_article_exactly_at_limit_is_fresh(self):
        pub = _NOW - timedelta(days=7)
        assert is_article_fresh(pub, max_age_days=7, now=_NOW) is True

    def test_article_one_day_over_limit_is_stale(self):
        pub = _NOW - timedelta(days=8)
        assert is_article_fresh(pub, max_age_days=7, now=_NOW) is False

    def test_none_publication_date_is_treated_as_fresh(self):
        # Cannot reject without fetching — caller handles this after full fetch
        assert is_article_fresh(None, max_age_days=7, now=_NOW) is True

    def test_future_dated_article_is_fresh(self):
        pub = _NOW + timedelta(days=1)  # minor clock drift / timezone edge
        assert is_article_fresh(pub, max_age_days=7, now=_NOW) is True

    def test_naive_datetime_treated_as_utc(self):
        # Some metadata gives tz-naive datetimes — treat as UTC
        naive_pub = datetime(2025, 5, 14, 12, 0, 0)  # no tzinfo, 1 day before _NOW
        assert is_article_fresh(naive_pub, max_age_days=7, now=_NOW) is True

    def test_stale_naive_datetime(self):
        naive_pub = datetime(2025, 5, 7, 12, 0, 0)  # 8 days before _NOW
        assert is_article_fresh(naive_pub, max_age_days=7, now=_NOW) is False


# ── is_article_long_enough ───────────────────────────────────────────────────

class TestIsArticleLongEnough:
    def test_word_count_above_minimum(self):
        assert is_article_long_enough(500, min_words=400) is True

    def test_word_count_exactly_at_minimum(self):
        assert is_article_long_enough(400, min_words=400) is True

    def test_word_count_one_below_minimum(self):
        assert is_article_long_enough(399, min_words=400) is False

    def test_zero_words(self):
        assert is_article_long_enough(0, min_words=400) is False

    def test_min_words_zero_always_passes(self):
        assert is_article_long_enough(0, min_words=0) is True
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
D:/Intern/content-automation-bot/backend/.venv/Scripts/pytest.exe tests/agents/research/test_filters.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.agents.research.filters'`

- [ ] **Step 3: Create `filters.py`**

Create `backend/app/agents/research/filters.py`:

```python
"""
Article filters: cheap checks that run before the expensive full-article fetch.

Execution order in the research pipeline (cheapest first):
  1. is_url_seen      — Supabase SELECT on normalized_url (skip if already stored)
  2. is_article_fresh — datetime comparison against publication_date
  3. is_article_long_enough — word count check (after full article is fetched)

All functions are synchronous. is_url_seen uses the synchronous supabase-py client
directly; the single HTTP call per article is fast enough to call from async code.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from supabase import Client

from app.utils.logging import get_logger

logger = get_logger(__name__)


def is_url_seen(normalized_url: str, supabase: Client) -> bool:
    """
    Return True if this normalized_url already exists in raw_content.

    Performs an exact-match SELECT on the normalized_url column (unique index).
    Uses LIMIT 1 so the DB returns as soon as any row is found.
    """
    response = (
        supabase
        .table("raw_content")
        .select("id")
        .eq("normalized_url", normalized_url)
        .limit(1)
        .execute()
    )
    seen = len(response.data) > 0
    if seen:
        logger.info(
            "is_url_seen: duplicate skipped",
            extra={"normalized_url": normalized_url},
        )
    return seen


def is_article_fresh(
    publication_date: Optional[datetime],
    max_age_days: int,
    *,
    now: Optional[datetime] = None,
) -> bool:
    """
    Return True if the article is within max_age_days of `now`.

    Articles with no publication_date are treated as fresh — we cannot reject
    them without fetching the full article first. Age is re-verified in Part 3
    after the fetch if the date is still missing.

    Naive datetimes are assumed to be UTC.
    """
    if publication_date is None:
        return True

    reference = now or datetime.now(timezone.utc)

    # Normalise to UTC-aware for safe subtraction
    if publication_date.tzinfo is None:
        publication_date = publication_date.replace(tzinfo=timezone.utc)

    age_days = (reference - publication_date).days
    fresh = age_days <= max_age_days

    if not fresh:
        logger.info(
            "is_article_fresh: stale article skipped",
            extra={"age_days": age_days, "max_age_days": max_age_days},
        )
    return fresh


def is_article_long_enough(word_count: int, min_words: int) -> bool:
    """Return True if word_count >= min_words."""
    long_enough = word_count >= min_words
    if not long_enough:
        logger.info(
            "is_article_long_enough: short article skipped",
            extra={"word_count": word_count, "min_words": min_words},
        )
    return long_enough
```

- [ ] **Step 4: Run tests — all should pass**

```bash
D:/Intern/content-automation-bot/backend/.venv/Scripts/pytest.exe tests/agents/research/test_filters.py -v
```

Expected:
```
tests/agents/research/test_filters.py::TestIsUrlSeen::test_returns_false_when_not_in_db PASSED
tests/agents/research/test_filters.py::TestIsUrlSeen::test_returns_true_when_found PASSED
tests/agents/research/test_filters.py::TestIsUrlSeen::test_calls_correct_table PASSED
tests/agents/research/test_filters.py::TestIsUrlSeen::test_queries_normalized_url_field PASSED
tests/agents/research/test_filters.py::TestIsUrlSeen::test_limits_to_one_row PASSED
tests/agents/research/test_filters.py::TestIsArticleFresh::test_fresh_article_within_limit PASSED
tests/agents/research/test_filters.py::TestIsArticleFresh::test_article_exactly_at_limit_is_fresh PASSED
tests/agents/research/test_filters.py::TestIsArticleFresh::test_article_one_day_over_limit_is_stale PASSED
tests/agents/research/test_filters.py::TestIsArticleFresh::test_none_publication_date_is_treated_as_fresh PASSED
tests/agents/research/test_filters.py::TestIsArticleFresh::test_future_dated_article_is_fresh PASSED
tests/agents/research/test_filters.py::TestIsArticleFresh::test_naive_datetime_treated_as_utc PASSED
tests/agents/research/test_filters.py::TestIsArticleFresh::test_stale_naive_datetime PASSED
tests/agents/research/test_filters.py::TestIsArticleLongEnough::test_word_count_above_minimum PASSED
tests/agents/research/test_filters.py::TestIsArticleLongEnough::test_word_count_exactly_at_minimum PASSED
tests/agents/research/test_filters.py::TestIsArticleLongEnough::test_word_count_one_below_minimum PASSED
tests/agents/research/test_filters.py::TestIsArticleLongEnough::test_zero_words PASSED
tests/agents/research/test_filters.py::TestIsArticleLongEnough::test_min_words_zero_always_passes PASSED
17 passed
```

- [ ] **Step 5: Run full suite**

```bash
D:/Intern/content-automation-bot/backend/.venv/Scripts/pytest.exe -m "not integration" -v
```

Expected: all prior tests still pass.

- [ ] **Step 6: Commit**

```bash
git -C D:/Intern/content-automation-bot add backend/app/agents/research/filters.py backend/tests/agents/research/test_filters.py
git -C D:/Intern/content-automation-bot commit -m "feat: add research agent filters module (dedup, age, word-count)"
```

---

### Task 16: Headline pre-scorer — Claude Haiku batch scoring

**Files:**
- Create: `backend/app/agents/research/prescorer.py`
- Test: `backend/tests/agents/research/test_prescorer.py`

#### Background

Before fetching full article text (the expensive step), we score each headline with Claude Haiku to decide if it's worth fetching. One API call per site scrape — all headlines from a single section page are batched into one message. The response is a JSON array of floats.

The `PreScoreResult` dataclass carries:
- `scores: list[float]` — one per input title, same order
- `input_tokens: int` and `output_tokens: int` — for cost tracking in Part 3

**Model:** always `claude-haiku-4-5` (the `claude_model_light` setting). The model name is passed in from outside so tests can substitute any string.

**Failure policy:** if the LLM call fails or returns malformed JSON, default every score to `5.0`. This is a neutral score — articles with a threshold of 4.0 will still proceed, so we never lose articles due to a LLM hiccup. On fallback, `input_tokens` and `output_tokens` are set to `0`.

**Anthropic SDK usage:**
```python
from anthropic import Anthropic

client = Anthropic(api_key="...")   # constructed outside; passed in as argument
message = client.messages.create(
    model=model,
    max_tokens=256,
    system=_SYSTEM_PROMPT,
    messages=[{"role": "user", "content": headlines_text}],
)
text = message.content[0].text          # the JSON array string
usage = message.usage                   # .input_tokens, .output_tokens
```

**How to mock `client.messages.create` in tests:**
```python
from unittest.mock import MagicMock

mock_client = MagicMock()
mock_message = MagicMock()
mock_message.content = [MagicMock(text='[8.0, 3.5, 6.0]')]
mock_message.usage = MagicMock(input_tokens=45, output_tokens=12)
mock_client.messages.create.return_value = mock_message
```

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/agents/research/test_prescorer.py`:

```python
"""Unit tests for app.agents.research.prescorer."""
from unittest.mock import MagicMock

import pytest

from app.agents.research.prescorer import pre_score_headlines, PreScoreResult


def _make_mock_client(json_text: str, input_tokens: int = 50, output_tokens: int = 10) -> MagicMock:
    """Build a mock Anthropic client whose messages.create returns `json_text`."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json_text)]
    mock_msg.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


class TestPreScoreHeadlines:
    def test_returns_correct_scores_for_three_titles(self):
        client = _make_mock_client("[8.0, 3.5, 6.0]", input_tokens=60, output_tokens=12)
        titles = [
            "RBI raises repo rate by 25bps in surprise off-cycle move",
            "Local company opens new branch in Pune",
            "SEBI tightens F&O eligibility criteria for equity derivatives",
        ]
        result = pre_score_headlines(titles, client, model="claude-haiku-4-5")

        assert isinstance(result, PreScoreResult)
        assert result.scores == [8.0, 3.5, 6.0]
        assert result.input_tokens == 60
        assert result.output_tokens == 12

    def test_single_title(self):
        client = _make_mock_client("[7.5]", input_tokens=30, output_tokens=5)
        result = pre_score_headlines(
            ["Nifty crosses 25000 for first time on foreign inflows"],
            client,
            model="claude-haiku-4-5",
        )
        assert result.scores == [7.5]

    def test_empty_titles_returns_empty_without_api_call(self):
        mock_client = MagicMock()
        result = pre_score_headlines([], mock_client, model="claude-haiku-4-5")

        assert result.scores == []
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        mock_client.messages.create.assert_not_called()

    def test_malformed_json_returns_neutral_scores(self):
        client = _make_mock_client("Sorry, I cannot score these.")
        titles = ["Title A about RBI", "Title B about markets"]
        result = pre_score_headlines(titles, client, model="claude-haiku-4-5")

        assert result.scores == [5.0, 5.0]
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_wrong_count_returns_neutral_scores(self):
        # API returns 2 scores but 3 titles were sent
        client = _make_mock_client("[8.0, 4.0]")
        titles = ["Title A", "Title B", "Title C"]
        result = pre_score_headlines(titles, client, model="claude-haiku-4-5")

        assert result.scores == [5.0, 5.0, 5.0]
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_api_exception_returns_neutral_scores(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API rate limit")
        titles = ["Title A about RBI rates", "Title B about SEBI"]
        result = pre_score_headlines(titles, mock_client, model="claude-haiku-4-5")

        assert result.scores == [5.0, 5.0]
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_scores_are_floats_not_ints(self):
        client = _make_mock_client("[8, 3, 6]")   # integers in JSON
        titles = ["Title A", "Title B", "Title C"]
        result = pre_score_headlines(titles, client, model="claude-haiku-4-5")

        assert all(isinstance(s, float) for s in result.scores)

    def test_uses_correct_model_name(self):
        client = _make_mock_client("[7.0]")
        pre_score_headlines(["Some headline about finance"], client, model="claude-haiku-4-5")

        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5"

    def test_headlines_appear_in_user_message(self):
        """Each title must appear in the user message sent to the API."""
        client = _make_mock_client("[7.0, 5.0]")
        titles = [
            "RBI announces emergency rate cut of 50 basis points",
            "Nifty 50 closes at record high on strong FII buying",
        ]
        pre_score_headlines(titles, client, model="claude-haiku-4-5")

        call_kwargs = client.messages.create.call_args.kwargs
        user_content = call_kwargs["messages"][0]["content"]
        assert "RBI announces emergency rate cut" in user_content
        assert "Nifty 50 closes at record high" in user_content
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
D:/Intern/content-automation-bot/backend/.venv/Scripts/pytest.exe tests/agents/research/test_prescorer.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.agents.research.prescorer'`

- [ ] **Step 3: Create `prescorer.py`**

Create `backend/app/agents/research/prescorer.py`:

```python
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
        message = client.messages.create(
            model=model,
            max_tokens=256,
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
```

- [ ] **Step 4: Run tests — all should pass**

```bash
D:/Intern/content-automation-bot/backend/.venv/Scripts/pytest.exe tests/agents/research/test_prescorer.py -v
```

Expected:
```
tests/agents/research/test_prescorer.py::TestPreScoreHeadlines::test_returns_correct_scores_for_three_titles PASSED
tests/agents/research/test_prescorer.py::TestPreScoreHeadlines::test_single_title PASSED
tests/agents/research/test_prescorer.py::TestPreScoreHeadlines::test_empty_titles_returns_empty_without_api_call PASSED
tests/agents/research/test_prescorer.py::TestPreScoreHeadlines::test_malformed_json_returns_neutral_scores PASSED
tests/agents/research/test_prescorer.py::TestPreScoreHeadlines::test_wrong_count_returns_neutral_scores PASSED
tests/agents/research/test_prescorer.py::TestPreScoreHeadlines::test_api_exception_returns_neutral_scores PASSED
tests/agents/research/test_prescorer.py::TestPreScoreHeadlines::test_scores_are_floats_not_ints PASSED
tests/agents/research/test_prescorer.py::TestPreScoreHeadlines::test_uses_correct_model_name PASSED
tests/agents/research/test_prescorer.py::TestPreScoreHeadlines::test_headlines_appear_in_user_message PASSED
9 passed
```

- [ ] **Step 5: Run full suite**

```bash
D:/Intern/content-automation-bot/backend/.venv/Scripts/pytest.exe -m "not integration" -v
```

Expected: all prior tests still pass.

- [ ] **Step 6: Commit**

```bash
git -C D:/Intern/content-automation-bot add backend/app/agents/research/prescorer.py backend/tests/agents/research/test_prescorer.py
git -C D:/Intern/content-automation-bot commit -m "feat: add research agent prescorer module (Claude Haiku batch headline scoring)"
```

---

## Self-Review

**Spec coverage:**
- [x] Dedup check vs `raw_content.normalized_url` — `is_url_seen` in Task 15
- [x] Age filter — `is_article_fresh` in Task 15
- [x] Word count filter — `is_article_long_enough` in Task 15
- [x] Naive datetime → UTC assumption documented and tested — Task 15
- [x] Claude Haiku batch headline pre-scoring — `pre_score_headlines` in Task 16
- [x] Token usage returned for cost tracking in Part 3 — `PreScoreResult.input_tokens/output_tokens`
- [x] Neutral-score fallback on LLM failure — Task 16
- [x] Empty-titles short-circuit (no API call) — Task 16
- [ ] Structured summarisation (Claude Sonnet) — covered in Part 3
- [ ] DB writes + arq task wiring — covered in Part 3

**Placeholder scan:** None found.

**Type consistency:**
- `is_url_seen(normalized_url: str, supabase: Client) -> bool` — matches tests exactly
- `is_article_fresh(publication_date: Optional[datetime], max_age_days: int, *, now: Optional[datetime] = None) -> bool` — matches tests exactly
- `is_article_long_enough(word_count: int, min_words: int) -> bool` — matches tests exactly
- `pre_score_headlines(titles: list[str], client: Anthropic, model: str) -> PreScoreResult` — matches tests exactly
- `PreScoreResult.scores: list[float]`, `.input_tokens: int`, `.output_tokens: int` — consistent across prescorer.py and tests
