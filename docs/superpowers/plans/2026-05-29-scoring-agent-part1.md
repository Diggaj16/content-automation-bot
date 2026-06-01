# Scoring Agent Part 1 — Embedder, Coverage Checker, Idea Generator

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the three foundational modules of the scoring agent — Voyage AI text embedding, Supabase vector-similarity coverage checking, and Claude Sonnet idea generation — each as a single-responsibility module that never raises.

**Architecture:** `embedder.py` wraps the synchronous Voyage AI client and returns a `list[float]` (or `[]` on failure). `coverage_checker.py` takes that embedding and calls a Postgres RPC to detect whether similar content was recently published on a given platform, returning a `bool`. `idea_generator.py` takes a `RawContent` article, calls Claude Sonnet with a structured prompt, and parses the JSON response into a typed `IdeaGenerationResult` containing `list[IdeaCreate]` plus token counts. All three modules follow the same never-raise contract established in the research agent: on any exception they log a warning and return a safe empty/False default.

**Tech Stack:** `voyageai>=0.3.2` (sync client), `anthropic` (already in pyproject.toml), `supabase-py` (already in pyproject.toml), `pytest`, `unittest.mock.MagicMock`

---

## File Structure

```
backend/
  app/
    agents/
      scoring/
        __init__.py          CREATE — empty package marker
        embedder.py          CREATE — Voyage AI text → list[float]
        coverage_checker.py  CREATE — embedding + platform → bool (RPC call)
        idea_generator.py    CREATE — RawContent → IdeaGenerationResult
  tests/
    agents/
      scoring/
        __init__.py              CREATE — empty package marker
        test_embedder.py         CREATE — 4 unit tests for embedder
        test_coverage_checker.py CREATE — 5 unit tests for coverage_checker
        test_idea_generator.py   CREATE — 6 unit tests for idea_generator
```

---

### Task 20: `embedder.py` — Voyage AI article embedding

**Files:**
- Create: `backend/app/agents/scoring/__init__.py`
- Create: `backend/app/agents/scoring/embedder.py`
- Create: `backend/tests/agents/scoring/__init__.py`
- Create: `backend/tests/agents/scoring/test_embedder.py`

---

- [ ] **Step 1: Create the two empty `__init__.py` package markers**

Create `backend/app/agents/scoring/__init__.py` — empty file (one blank line is fine).

Create `backend/tests/agents/scoring/__init__.py` — empty file (one blank line is fine).

These make the directories importable as Python packages. Without them, pytest cannot discover tests and Python cannot import the modules.

---

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/agents/scoring/test_embedder.py` with this exact content:

```python
"""Unit tests for app.agents.scoring.embedder."""
from unittest.mock import MagicMock

import pytest

from app.agents.scoring.embedder import embed_text, _EMBEDDING_MODEL


def _make_voyage_client(embeddings: list[list[float]]) -> MagicMock:
    """Return a mock voyageai.Client whose embed() returns the given embeddings."""
    mock_result = MagicMock()
    mock_result.embeddings = embeddings
    mock_client = MagicMock()
    mock_client.embed.return_value = mock_result
    return mock_client


class TestEmbedText:
    def test_returns_embedding_on_success(self):
        expected = [0.1, 0.2, 0.3]
        client = _make_voyage_client([expected])
        result = embed_text("some finance article text", client)
        assert result == expected
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    def test_returns_empty_list_on_exception(self):
        mock_client = MagicMock()
        mock_client.embed.side_effect = Exception("Voyage API error")
        result = embed_text("some text", mock_client)
        assert result == []

    def test_passes_correct_model(self):
        client = _make_voyage_client([[0.1, 0.2]])
        embed_text("text", client)
        call_kwargs = client.embed.call_args.kwargs
        assert call_kwargs["model"] == _EMBEDDING_MODEL

    def test_passes_text_as_list(self):
        client = _make_voyage_client([[0.1, 0.2]])
        embed_text("my article text", client)
        call_args = client.embed.call_args.args
        # First positional arg must be a list containing the text, not the bare string
        assert call_args[0] == ["my article text"]
```

---

- [ ] **Step 3: Run the tests to verify they fail (import error expected)**

Working directory: `D:/Intern/content-automation-bot/backend/`

```
D:/Intern/content-automation-bot/backend/.venv/Scripts/pytest.exe tests/agents/scoring/test_embedder.py -v
```

Expected output: all 4 tests show `ERROR` or `FAILED` with `ModuleNotFoundError: No module named 'app.agents.scoring.embedder'` — this confirms the test infrastructure is wired up correctly and we need to write the implementation.

---

- [ ] **Step 4: Write the implementation**

Create `backend/app/agents/scoring/embedder.py` with this exact content:

```python
"""
Voyage AI text embedder for the scoring agent.

Usage:
    import voyageai
    vo = voyageai.Client(api_key=settings.voyage_api_key)
    embedding = embed_text(article.full_text, vo)
    # embedding: list[float] of length 1024, or [] if Voyage is unavailable
"""
from __future__ import annotations

import voyageai

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Voyage model that produces 1024-dimensional embeddings.
# This constant is exported so tests can reference it without hard-coding the string.
_EMBEDDING_MODEL = "voyage-3"


def embed_text(text: str, voyage_client: voyageai.Client) -> list[float]:
    """
    Embed a single text string using Voyage AI.

    Returns a list of 1024 floats on success, or an empty list on any failure.
    Never raises — callers treat [] as "embedding unavailable".
    """
    try:
        result = voyage_client.embed([text], model=_EMBEDDING_MODEL, input_type="document")
        return result.embeddings[0]
    except Exception as exc:
        logger.warning("embed_text failed", extra={"error": str(exc)})
        return []
```

---

- [ ] **Step 5: Run the tests to verify they pass**

```
D:/Intern/content-automation-bot/backend/.venv/Scripts/pytest.exe tests/agents/scoring/test_embedder.py -v
```

Expected output:
```
tests/agents/scoring/test_embedder.py::TestEmbedText::test_returns_embedding_on_success PASSED
tests/agents/scoring/test_embedder.py::TestEmbedText::test_returns_empty_list_on_exception PASSED
tests/agents/scoring/test_embedder.py::TestEmbedText::test_passes_correct_model PASSED
tests/agents/scoring/test_embedder.py::TestEmbedText::test_passes_text_as_list PASSED

4 passed in 0.XXs
```

---

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/scoring/__init__.py \
        backend/app/agents/scoring/embedder.py \
        backend/tests/agents/scoring/__init__.py \
        backend/tests/agents/scoring/test_embedder.py
git commit -m "feat(scoring): add Voyage AI embedder module with tests (Task 20)"
```

---

### Task 21: `coverage_checker.py` — recent brand coverage check

**Files:**
- Create: `backend/app/agents/scoring/coverage_checker.py`
- Create: `backend/tests/agents/scoring/test_coverage_checker.py`

#### Background

The Postgres function `check_recent_brand_coverage` is called via the Supabase `.rpc()` method. It accepts a 1024-dimensional vector, a platform string, a lookback window in days, and a similarity threshold. It returns rows when brand-published content is semantically close to the candidate embedding. If any rows come back, the topic has been covered recently and we flag the idea.

The function signature in the DB:
```sql
check_recent_brand_coverage(
    topic_embedding      vector(1024),
    platform_filter      TEXT,
    days_back            INT   DEFAULT 30,
    similarity_threshold FLOAT DEFAULT 0.85
)
RETURNS TABLE (id UUID, content TEXT, similarity FLOAT)
```

`supabase.rpc("fn_name", params_dict).execute()` is the supabase-py call pattern. `resp.data` is a list of matching rows (empty list = no match).

---

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/agents/scoring/test_coverage_checker.py` with this exact content:

```python
"""Unit tests for app.agents.scoring.coverage_checker."""
from unittest.mock import MagicMock

import pytest

from app.agents.scoring.coverage_checker import check_recent_coverage


def _make_supabase(rpc_data: list) -> MagicMock:
    """Return a mock Supabase client whose rpc().execute() returns rpc_data."""
    mock_resp = MagicMock()
    mock_resp.data = rpc_data
    mock_sb = MagicMock()
    mock_sb.rpc.return_value.execute.return_value = mock_resp
    return mock_sb


_DUMMY_EMBEDDING = [0.1] * 1024


class TestCheckRecentCoverage:
    def test_returns_true_when_similar_content_found(self):
        sb = _make_supabase([
            {"id": "uuid-1", "content": "RBI rate decision", "similarity": 0.92},
        ])
        result = check_recent_coverage(_DUMMY_EMBEDDING, "linkedin", sb)
        assert result is True

    def test_returns_false_when_no_similar_content(self):
        sb = _make_supabase([])
        result = check_recent_coverage(_DUMMY_EMBEDDING, "linkedin", sb)
        assert result is False

    def test_returns_false_for_empty_embedding(self):
        """When embed_text returned [] (no Voyage key), skip RPC entirely."""
        sb = MagicMock()  # should not be called at all
        result = check_recent_coverage([], "linkedin", sb)
        assert result is False
        sb.rpc.assert_not_called()

    def test_passes_correct_params_to_rpc(self):
        sb = _make_supabase([])
        check_recent_coverage(
            _DUMMY_EMBEDDING, "twitter", sb, days_back=14, threshold=0.90
        )
        sb.rpc.assert_called_once_with(
            "check_recent_brand_coverage",
            {
                "topic_embedding":   _DUMMY_EMBEDDING,
                "platform_filter":   "twitter",
                "days_back":         14,
                "similarity_threshold": 0.90,
            },
        )

    def test_returns_false_on_exception(self):
        sb = MagicMock()
        sb.rpc.side_effect = Exception("Supabase connection error")
        result = check_recent_coverage(_DUMMY_EMBEDDING, "linkedin", sb)
        assert result is False
```

---

- [ ] **Step 2: Run the tests to verify they fail**

```
D:/Intern/content-automation-bot/backend/.venv/Scripts/pytest.exe tests/agents/scoring/test_coverage_checker.py -v
```

Expected output: all 5 tests show `ERROR` or `FAILED` with `ModuleNotFoundError: No module named 'app.agents.scoring.coverage_checker'`.

---

- [ ] **Step 3: Write the implementation**

Create `backend/app/agents/scoring/coverage_checker.py` with this exact content:

```python
"""
Recent brand coverage checker for the scoring agent.

Calls the Postgres RPC function `check_recent_brand_coverage` to detect whether
similar content has already been published by the brand on a given platform within
the last N days. Returns True if similar content was found (flag the idea),
False otherwise.

Usage:
    from app.agents.scoring.coverage_checker import check_recent_coverage
    already_covered = check_recent_coverage(embedding, platform.value, supabase)
"""
from __future__ import annotations

from supabase import Client

from app.utils.logging import get_logger

logger = get_logger(__name__)


def check_recent_coverage(
    embedding: list[float],
    platform: str,
    supabase: Client,
    *,
    days_back: int = 30,
    threshold: float = 0.85,
) -> bool:
    """
    Return True if brand-published content similar to `embedding` exists on
    `platform` within the last `days_back` days (similarity >= `threshold`).

    If `embedding` is empty (Voyage AI unavailable), returns False immediately
    without touching the database.

    Never raises — returns False on any error.
    """
    if not embedding:
        return False

    try:
        resp = supabase.rpc(
            "check_recent_brand_coverage",
            {
                "topic_embedding":      embedding,
                "platform_filter":      platform,
                "days_back":            days_back,
                "similarity_threshold": threshold,
            },
        ).execute()
        return bool(resp.data)
    except Exception as exc:
        logger.warning(
            "check_recent_coverage failed",
            extra={"platform": platform, "error": str(exc)},
        )
        return False
```

---

- [ ] **Step 4: Run the tests to verify they pass**

```
D:/Intern/content-automation-bot/backend/.venv/Scripts/pytest.exe tests/agents/scoring/test_coverage_checker.py -v
```

Expected output:
```
tests/agents/scoring/test_coverage_checker.py::TestCheckRecentCoverage::test_returns_true_when_similar_content_found PASSED
tests/agents/scoring/test_coverage_checker.py::TestCheckRecentCoverage::test_returns_false_when_no_similar_content PASSED
tests/agents/scoring/test_coverage_checker.py::TestCheckRecentCoverage::test_returns_false_for_empty_embedding PASSED
tests/agents/scoring/test_coverage_checker.py::TestCheckRecentCoverage::test_passes_correct_params_to_rpc PASSED
tests/agents/scoring/test_coverage_checker.py::TestCheckRecentCoverage::test_returns_false_on_exception PASSED

5 passed in 0.XXs
```

---

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/scoring/coverage_checker.py \
        backend/tests/agents/scoring/test_coverage_checker.py
git commit -m "feat(scoring): add coverage checker module with tests (Task 21)"
```

---

### Task 22: `idea_generator.py` — Claude Sonnet → list[IdeaCreate]

**Files:**
- Create: `backend/app/agents/scoring/idea_generator.py`
- Create: `backend/tests/agents/scoring/test_idea_generator.py`

#### Background

This module mirrors the pattern in `summariser.py` (research agent). It calls Claude with a structured JSON prompt, strips optional markdown code fences, parses the JSON array, filters items with unknown platform values, and constructs `IdeaCreate` Pydantic models. The result is a `IdeaGenerationResult` dataclass containing the ideas list and token counts for cost tracking.

The system prompt asks Claude to return a JSON **array** (not object) of idea objects. Each object has:
- `platform`: one of `"linkedin"`, `"twitter"`, `"blog"`, `"email"`
- `angle`: the content angle / hook (string)
- `agent_reasoning`: why this is a good idea for the Indian finance audience (string)
- `score`: novelty + relevance score 0.0–10.0 (float)

The fence-stripping pattern uses `re.search(r'\[.*\]', raw, re.DOTALL)` — matching the outermost `[...]` array. This is the same approach `summariser.py` uses for `{...}` objects.

`_KNOWN_PLATFORMS = frozenset(p.value for p in Platform)` is used to filter before constructing `IdeaCreate` objects, so unknown platform strings from Claude (e.g. `"tiktok"`, `"youtube"`) are silently dropped rather than causing a `ValueError`.

---

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/agents/scoring/test_idea_generator.py` with this exact content:

```python
"""Unit tests for app.agents.scoring.idea_generator."""
import json
from unittest.mock import MagicMock
from uuid import uuid4
from datetime import datetime, timezone

import pytest

from app.agents.scoring.idea_generator import (
    generate_ideas,
    IdeaGenerationResult,
)
from app.db.models import IdeaCreate, Platform, RawContent, StructuredSummary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_IDEAS = [
    {
        "platform":        "linkedin",
        "angle":           "How RBI rate hike affects your home loan EMI",
        "agent_reasoning": "High engagement topic; directly impacts retail borrowers.",
        "score":           8.5,
    },
    {
        "platform":        "twitter",
        "angle":           "RBI surprise: 3 things every investor must know",
        "agent_reasoning": "Twitter audience responds to numbered lists on macro news.",
        "score":           7.0,
    },
]

_VALID_SUMMARY = StructuredSummary(
    story_narrative="RBI raised repo rate by 25bps in a surprise off-cycle move.",
    key_data_points=["25bps", "6.75% repo rate", "May 2025"],
    mechanism="Inflation breached the 6% upper tolerance band for three consecutive months.",
    implications="Home loan EMIs will increase for floating-rate borrowers; FD rates may follow.",
    content_angles=["Impact on EMIs", "What it means for fixed deposits", "FII reaction"],
)


def _make_article(summary: StructuredSummary | None = _VALID_SUMMARY) -> RawContent:
    return RawContent(
        id=uuid4(),
        url="https://www.livemint.com/markets/rbi-rate-hike",
        normalized_url="https://www.livemint.com/markets/rbi-rate-hike",
        title="RBI raises repo rate by 25bps",
        source_name="LiveMint",
        publication_date=datetime(2025, 5, 15, tzinfo=timezone.utc),
        fetch_date=datetime(2025, 5, 15, tzinfo=timezone.utc),
        full_text="Long article text " * 100,
        structured_summary=summary,
        word_count=800,
        pre_score=7.5,
        vision_fallback_used=False,
        paywall_detected=False,
        processed=False,
        created_at=datetime(2025, 5, 15, tzinfo=timezone.utc),
    )


def _make_mock_client(
    json_text: str,
    input_tokens: int = 300,
    output_tokens: int = 120,
) -> MagicMock:
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json_text)]
    mock_msg.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGenerateIdeas:
    def test_returns_ideas_on_success(self):
        client = _make_mock_client(
            json.dumps(_VALID_IDEAS), input_tokens=300, output_tokens=120
        )
        result = generate_ideas(_make_article(), client, "claude-sonnet-4-5")
        assert isinstance(result, IdeaGenerationResult)
        assert len(result.ideas) == 2
        assert all(isinstance(idea, IdeaCreate) for idea in result.ideas)
        assert result.ideas[0].platform == Platform.LINKEDIN
        assert result.ideas[1].platform == Platform.TWITTER
        assert result.input_tokens == 300
        assert result.output_tokens == 120

    def test_unknown_platform_filtered_out(self):
        ideas_with_unknown = [
            *_VALID_IDEAS,
            {
                "platform":        "tiktok",
                "angle":           "RBI explained in 60 seconds",
                "agent_reasoning": "Short video format.",
                "score":           6.0,
            },
        ]
        client = _make_mock_client(json.dumps(ideas_with_unknown))
        result = generate_ideas(_make_article(), client, "claude-sonnet-4-5")
        # tiktok must be dropped; only the 2 valid ones remain
        assert len(result.ideas) == 2
        platforms = {idea.platform for idea in result.ideas}
        assert Platform.LINKEDIN in platforms
        assert Platform.TWITTER in platforms

    def test_none_summary_returns_empty(self):
        """Articles without a structured_summary must return an empty result immediately."""
        article = _make_article(summary=None)
        client = MagicMock()  # must not be called
        result = generate_ideas(article, client, "claude-sonnet-4-5")
        assert isinstance(result, IdeaGenerationResult)
        assert result.ideas == []
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        client.messages.create.assert_not_called()

    def test_malformed_json_returns_empty(self):
        client = _make_mock_client("Sorry, I cannot generate ideas for this article.")
        result = generate_ideas(_make_article(), client, "claude-sonnet-4-5")
        assert result.ideas == []
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_api_exception_returns_empty(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Anthropic API error")
        result = generate_ideas(_make_article(), mock_client, "claude-sonnet-4-5")
        assert result.ideas == []
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_markdown_fenced_array_parsed(self):
        """Claude sometimes wraps JSON arrays in ```json ... ``` fences."""
        fenced = f"```json\n{json.dumps(_VALID_IDEAS)}\n```"
        client = _make_mock_client(fenced)
        result = generate_ideas(_make_article(), client, "claude-sonnet-4-5")
        assert len(result.ideas) == 2
        assert result.ideas[0].platform == Platform.LINKEDIN
```

---

- [ ] **Step 2: Run the tests to verify they fail**

```
D:/Intern/content-automation-bot/backend/.venv/Scripts/pytest.exe tests/agents/scoring/test_idea_generator.py -v
```

Expected output: all 6 tests show `ERROR` or `FAILED` with `ModuleNotFoundError: No module named 'app.agents.scoring.idea_generator'`.

---

- [ ] **Step 3: Write the implementation**

Create `backend/app/agents/scoring/idea_generator.py` with this exact content:

```python
"""
Idea generator for the scoring agent.

Calls Claude Sonnet to produce a list of content ideas (IdeaCreate) from a
scored article. Each idea specifies a platform, angle, reasoning, and score.

Usage:
    from anthropic import Anthropic
    from app.agents.scoring.idea_generator import generate_ideas

    client = Anthropic(api_key=settings.anthropic_api_key)
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

# Maximum tokens Claude may return for an idea list.
_MAX_OUTPUT_TOKENS = 1024

# Frozenset of valid platform string values — used to filter Claude's output
# before constructing IdeaCreate objects.
_KNOWN_PLATFORMS = frozenset(p.value for p in Platform)

_SYSTEM_PROMPT = (
    "You are a content strategist for an Indian personal finance creator with a highly "
    "engaged audience of retail investors interested in stock markets, mutual funds, "
    "RBI/SEBI policy, IPOs, and macroeconomics.\n\n"
    "Given a structured article summary, generate content ideas for the creator's "
    "platforms. Respond with ONLY a JSON array — no markdown, no extra keys:\n\n"
    "[\n"
    "  {\n"
    '    "platform": "linkedin" | "twitter" | "blog" | "email",\n'
    '    "angle": "<specific hook or angle for this platform>",\n'
    '    "agent_reasoning": "<why this angle works for the Indian finance audience>",\n'
    '    "score": <float 0.0-10.0 representing novelty + relevance>\n'
    "  },\n"
    "  ...\n"
    "]\n\n"
    "Generate 2-4 ideas spread across platforms. Respond with nothing but the JSON array."
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
) -> IdeaGenerationResult:
    """
    Generate a list of IdeaCreate objects from a scored article.

    Returns an IdeaGenerationResult. Never raises — on any failure returns
    an empty IdeaGenerationResult (empty list, zero tokens).

    If article.structured_summary is None, returns empty immediately without
    making an API call.
    """
    if article.structured_summary is None:
        return _empty_result()

    s = article.structured_summary
    key_points_str = "\n".join(f"- {pt}" for pt in s.key_data_points)
    angles_str = "\n".join(f"- {a}" for a in s.content_angles)

    user_content = (
        f"Title: {article.title}\n\n"
        f"Story narrative:\n{s.story_narrative}\n\n"
        f"Key data points:\n{key_points_str}\n\n"
        f"Mechanism:\n{s.mechanism}\n\n"
        f"Implications:\n{s.implications}\n\n"
        f"Suggested content angles:\n{angles_str}"
    )

    try:
        message = client.messages.create(
            model=model,
            max_tokens=_MAX_OUTPUT_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        if not message.content:
            logger.warning(
                "generate_ideas: empty content list in API response",
                extra={"title": article.title},
            )
            return _empty_result()

        raw = message.content[0].text.strip()

        # Strip markdown code fences if Claude wraps the response
        json_match = re.search(r'\[.*\]', raw, re.DOTALL)
        if not json_match:
            logger.warning(
                "generate_ideas: no JSON array found in response",
                extra={"title": article.title, "raw": raw[:200]},
            )
            return _empty_result()

        raw = json_match.group(0)
        items = json.loads(raw)

        ideas: list[IdeaCreate] = []
        for item in items:
            platform_str = item.get("platform", "")
            if platform_str not in _KNOWN_PLATFORMS:
                logger.warning(
                    "generate_ideas: unknown platform filtered out",
                    extra={"platform": platform_str},
                )
                continue
            ideas.append(
                IdeaCreate(
                    platform=Platform(platform_str),
                    angle=item["angle"],
                    agent_reasoning=item["agent_reasoning"],
                    score=float(item["score"]),
                )
            )

        return IdeaGenerationResult(
            ideas=ideas,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )

    except Exception as exc:
        logger.warning(
            "generate_ideas failed — returning empty result",
            extra={"title": article.title, "error": str(exc)},
        )
        return _empty_result()
```

---

- [ ] **Step 4: Run the tests to verify they pass**

```
D:/Intern/content-automation-bot/backend/.venv/Scripts/pytest.exe tests/agents/scoring/test_idea_generator.py -v
```

Expected output:
```
tests/agents/scoring/test_idea_generator.py::TestGenerateIdeas::test_returns_ideas_on_success PASSED
tests/agents/scoring/test_idea_generator.py::TestGenerateIdeas::test_unknown_platform_filtered_out PASSED
tests/agents/scoring/test_idea_generator.py::TestGenerateIdeas::test_none_summary_returns_empty PASSED
tests/agents/scoring/test_idea_generator.py::TestGenerateIdeas::test_malformed_json_returns_empty PASSED
tests/agents/scoring/test_idea_generator.py::TestGenerateIdeas::test_api_exception_returns_empty PASSED
tests/agents/scoring/test_idea_generator.py::TestGenerateIdeas::test_markdown_fenced_array_parsed PASSED

6 passed in 0.XXs
```

---

- [ ] **Step 5: Run all three test files together to confirm no regressions**

```
D:/Intern/content-automation-bot/backend/.venv/Scripts/pytest.exe tests/agents/scoring/ -v
```

Expected output:
```
tests/agents/scoring/test_embedder.py::TestEmbedText::test_returns_embedding_on_success PASSED
tests/agents/scoring/test_embedder.py::TestEmbedText::test_returns_empty_list_on_exception PASSED
tests/agents/scoring/test_embedder.py::TestEmbedText::test_passes_correct_model PASSED
tests/agents/scoring/test_embedder.py::TestEmbedText::test_passes_text_as_list PASSED
tests/agents/scoring/test_coverage_checker.py::TestCheckRecentCoverage::test_returns_true_when_similar_content_found PASSED
tests/agents/scoring/test_coverage_checker.py::TestCheckRecentCoverage::test_returns_false_when_no_similar_content PASSED
tests/agents/scoring/test_coverage_checker.py::TestCheckRecentCoverage::test_returns_false_for_empty_embedding PASSED
tests/agents/scoring/test_coverage_checker.py::TestCheckRecentCoverage::test_passes_correct_params_to_rpc PASSED
tests/agents/scoring/test_coverage_checker.py::TestCheckRecentCoverage::test_returns_false_on_exception PASSED
tests/agents/scoring/test_idea_generator.py::TestGenerateIdeas::test_returns_ideas_on_success PASSED
tests/agents/scoring/test_idea_generator.py::TestGenerateIdeas::test_unknown_platform_filtered_out PASSED
tests/agents/scoring/test_idea_generator.py::TestGenerateIdeas::test_none_summary_returns_empty PASSED
tests/agents/scoring/test_idea_generator.py::TestGenerateIdeas::test_malformed_json_returns_empty PASSED
tests/agents/scoring/test_idea_generator.py::TestGenerateIdeas::test_api_exception_returns_empty PASSED
tests/agents/scoring/test_idea_generator.py::TestGenerateIdeas::test_markdown_fenced_array_parsed PASSED

15 passed in 0.XXs
```

---

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/scoring/idea_generator.py \
        backend/tests/agents/scoring/test_idea_generator.py
git commit -m "feat(scoring): add idea generator module with tests (Task 22)"
```
