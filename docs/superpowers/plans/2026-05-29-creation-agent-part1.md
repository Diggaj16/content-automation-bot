# Content Creation Agent Implementation Plan — Part 1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Content Creation Agent modules: brand context retrieval (RAG via `match_brand_memory`), Claude Sonnet content generation, and finance flag detection + DB write.

**Architecture:** Three independent modules under `app/agents/creation/`. Each follows the never-raise contract: all exceptions are caught and a safe default returned. `content_generator.py` uses Anthropic sync client. `finance_flags.py` uses regex only (no AI cost). `db_writer.py` wraps a single INSERT with per-flag serialisation.

**Tech Stack:** Anthropic (existing), Supabase (existing), Python regex, Pydantic (existing)

---

### Task 29: Brand context module

**Files:**
- Create: `backend/app/agents/creation/__init__.py`
- Create: `backend/app/agents/creation/brand_context.py`
- Create: `backend/tests/agents/creation/__init__.py`
- Create: `backend/tests/agents/creation/test_brand_context.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/agents/creation/test_brand_context.py
"""Tests for brand_context.get_brand_context."""
from unittest.mock import MagicMock
from app.agents.creation.brand_context import get_brand_context


def _mock_sb_rpc(data):
    sb = MagicMock()
    sb.rpc.return_value.execute.return_value.data = data
    return sb


# ─── happy path ───────────────────────────────────────────────────────────────

def test_returns_formatted_string_when_results():
    sb = _mock_sb_rpc([
        {"id": "1", "content": "LinkedIn post about SEBI crackdown"},
        {"id": "2", "content": "Thread on mutual funds"},
    ])
    result = get_brand_context([0.1, 0.2, 0.3], "linkedin", sb)
    assert "LinkedIn post about SEBI crackdown" in result
    assert "Thread on mutual funds" in result
    assert result.startswith("Past brand content examples:")


def test_returns_empty_string_when_no_results():
    sb = _mock_sb_rpc([])
    result = get_brand_context([0.1, 0.2], "linkedin", sb)
    assert result == ""


def test_returns_empty_string_when_data_is_none():
    sb = _mock_sb_rpc(None)
    result = get_brand_context([0.1, 0.2], "linkedin", sb)
    assert result == ""


# ─── empty embedding guard ────────────────────────────────────────────────────

def test_empty_embedding_returns_empty_string_no_rpc():
    sb = MagicMock()
    result = get_brand_context([], "linkedin", sb)
    assert result == ""
    sb.rpc.assert_not_called()


def test_none_embedding_returns_empty_string_no_rpc():
    sb = MagicMock()
    result = get_brand_context(None, "linkedin", sb)
    assert result == ""
    sb.rpc.assert_not_called()


# ─── error handling ───────────────────────────────────────────────────────────

def test_rpc_exception_returns_empty_string():
    sb = MagicMock()
    sb.rpc.return_value.execute.side_effect = RuntimeError("RPC failed")
    result = get_brand_context([0.1, 0.2], "linkedin", sb)
    assert result == ""


def test_respects_match_count_parameter():
    sb = _mock_sb_rpc([{"id": "1", "content": "post1"}])
    get_brand_context([0.1], "twitter", sb, match_count=3)
    call_kwargs = sb.rpc.call_args[0][1]
    assert call_kwargs["match_count"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/agents/creation/test_brand_context.py -v
```
Expected: ERROR (ImportError — module doesn't exist yet)

- [ ] **Step 3: Create `backend/app/agents/creation/__init__.py`**

Empty file.

- [ ] **Step 4: Create `backend/tests/agents/creation/__init__.py`**

Empty file.

- [ ] **Step 5: Create `backend/app/agents/creation/brand_context.py`**

```python
"""
Brand context retrieval for content generation.

Calls the match_brand_memory Postgres RPC to find semantically similar
past published content, then formats it as a prompt context string.
"""
from typing import Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)


def get_brand_context(
    embedding: Optional[list[float]],
    platform: str,
    supabase,
    match_count: int = 5,
) -> str:
    """
    Retrieve relevant past brand content using vector similarity.

    Args:
        embedding:   Voyage AI embedding of the idea text (1024-dim).
                     Empty list or None → return "" immediately, no RPC called.
        platform:    Platform string used to filter brand_memory results.
        supabase:    Supabase client.
        match_count: Number of similar examples to retrieve (default 5).

    Returns:
        Formatted string of past content examples, or "" if none found.
        Never raises.
    """
    if not embedding:
        return ""

    try:
        resp = supabase.rpc(
            "match_brand_memory",
            {
                "query_embedding": embedding,
                "match_count": match_count,
                "filter_platform": platform,
            },
        ).execute()

        if not resp.data:
            return ""

        lines = [f"- {item['content']}" for item in resp.data]
        return "Past brand content examples:\n" + "\n".join(lines)

    except Exception as exc:
        logger.warning(f"get_brand_context: RPC failed | platform={platform} | err={exc}")
        return ""
```

- [ ] **Step 6: Run test to verify it passes**

```
pytest tests/agents/creation/test_brand_context.py -v
```
Expected: 7 PASSED

- [ ] **Step 7: Run full suite**

```
pytest tests/ --ignore=tests/agents/research/test_install.py -q
```
Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add app/agents/creation/__init__.py app/agents/creation/brand_context.py tests/agents/creation/__init__.py tests/agents/creation/test_brand_context.py
git commit -m "feat: add creation agent brand_context module"
```

---

### Task 30: Content generator module

**Files:**
- Create: `backend/app/agents/creation/content_generator.py`
- Create: `backend/tests/agents/creation/test_content_generator.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/agents/creation/test_content_generator.py
"""Tests for content_generator.generate_content."""
import json
from dataclasses import dataclass
from unittest.mock import MagicMock, patch
from uuid import UUID

from app.agents.creation.content_generator import generate_content, ContentGenerationResult
from app.db.models import Idea, Platform, ApprovalStatus


def _make_idea(platform: str = "linkedin", angle: str = "SEBI new circular impacts AMCs") -> Idea:
    return Idea(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        platform=Platform(platform),
        angle=angle,
        edited_angle=None,
        source_article_id=None,
        agent_reasoning="Strong relevance to Indian investors",
        source_article_date=None,
        approval_status=ApprovalStatus.APPROVED,
        score=8.2,
        recent_coverage_flag=False,
        created_at=__import__("datetime").datetime(2026, 5, 29, tzinfo=__import__("datetime").timezone.utc),
        updated_at=__import__("datetime").datetime(2026, 5, 29, tzinfo=__import__("datetime").timezone.utc),
    )


def _mock_anthropic(content_text: str = "Generated LinkedIn post here.", reasoning: str = "Good angle."):
    client = MagicMock()
    response_json = json.dumps({"content_text": content_text, "reasoning": reasoning})
    msg = MagicMock()
    msg.content = [MagicMock(text=response_json)]
    msg.usage.input_tokens = 100
    msg.usage.output_tokens = 200
    client.messages.create.return_value = msg
    return client


# ─── happy path ───────────────────────────────────────────────────────────────

def test_returns_draft_create_on_success():
    idea = _make_idea("linkedin")
    client = _mock_anthropic("A great LinkedIn post about SEBI.", "Strong angle for professionals.")
    result = generate_content(idea, "Article context here.", "Brand context here.", client, "claude-sonnet-4-5")
    assert result.draft_create is not None
    assert result.draft_create.content_text == "A great LinkedIn post about SEBI."
    assert result.draft_create.agent_reasoning == "Strong angle for professionals."
    assert result.draft_create.platform == Platform.LINKEDIN
    assert result.draft_create.source_idea_id == idea.id
    assert result.input_tokens == 100
    assert result.output_tokens == 200


def test_uses_edited_angle_when_available():
    idea = _make_idea("twitter", "original angle")
    idea = idea.model_copy(update={"edited_angle": "EDITED: better angle"})
    client = _mock_anthropic("Twitter thread here.")
    generate_content(idea, "", "", client, "model")
    call_args = client.messages.create.call_args
    # The edited_angle should appear in the prompt
    prompt_text = str(call_args)
    assert "EDITED: better angle" in prompt_text


def test_token_counts_tracked():
    idea = _make_idea()
    client = _mock_anthropic()
    result = generate_content(idea, "", "", client, "model")
    assert result.input_tokens == 100
    assert result.output_tokens == 200


def test_finance_flags_list_is_empty_by_default():
    """generate_content does not populate finance_flags — that's done by finance_flags module."""
    idea = _make_idea()
    client = _mock_anthropic()
    result = generate_content(idea, "", "", client, "model")
    assert result.draft_create is not None
    assert result.draft_create.finance_flags == []


# ─── JSON parsing robustness ──────────────────────────────────────────────────

def test_handles_json_wrapped_in_markdown_fences():
    client = MagicMock()
    response_json = '```json\n{"content_text": "Post content.", "reasoning": "Good."}\n```'
    msg = MagicMock()
    msg.content = [MagicMock(text=response_json)]
    msg.usage.input_tokens = 50
    msg.usage.output_tokens = 80
    client.messages.create.return_value = msg
    result = generate_content(_make_idea(), "", "", client, "model")
    assert result.draft_create is not None
    assert result.draft_create.content_text == "Post content."


def test_returns_none_draft_on_invalid_json():
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text="not json at all")]
    msg.usage.input_tokens = 30
    msg.usage.output_tokens = 10
    client.messages.create.return_value = msg
    result = generate_content(_make_idea(), "", "", client, "model")
    assert result.draft_create is None


def test_returns_none_draft_on_api_error():
    client = MagicMock()
    client.messages.create.side_effect = RuntimeError("API timeout")
    result = generate_content(_make_idea(), "", "", client, "model")
    assert result.draft_create is None
    assert result.input_tokens == 0
    assert result.output_tokens == 0


def test_returns_none_on_empty_content_list():
    client = MagicMock()
    msg = MagicMock()
    msg.content = []
    msg.usage.input_tokens = 10
    msg.usage.output_tokens = 5
    client.messages.create.return_value = msg
    result = generate_content(_make_idea(), "", "", client, "model")
    assert result.draft_create is None
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/agents/creation/test_content_generator.py -v
```
Expected: ERROR (ImportError)

- [ ] **Step 3: Create `backend/app/agents/creation/content_generator.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/agents/creation/test_content_generator.py -v
```
Expected: 9 PASSED

- [ ] **Step 5: Run full suite**

```
pytest tests/ --ignore=tests/agents/research/test_install.py -q
```
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add app/agents/creation/content_generator.py tests/agents/creation/test_content_generator.py
git commit -m "feat: add creation agent content_generator module"
```

---

### Task 31: Finance flags detection + DB writer

**Files:**
- Create: `backend/app/agents/creation/finance_flags.py`
- Create: `backend/app/agents/creation/db_writer.py`
- Create: `backend/tests/agents/creation/test_finance_flags.py`
- Create: `backend/tests/agents/creation/test_db_writer.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/agents/creation/test_finance_flags.py
"""Tests for finance_flags.detect_finance_flags."""
from app.agents.creation.finance_flags import detect_finance_flags


def test_detects_investment_advice():
    text = "You should buy HDFC Bank stocks right now."
    flags = detect_finance_flags(text)
    assert any(f.flag_type == "investment_advice" for f in flags)


def test_detects_financial_figure_rupee():
    text = "The company raised ₹500 crore in Series A funding."
    flags = detect_finance_flags(text)
    assert any(f.flag_type == "financial_figure" for f in flags)


def test_detects_financial_figure_percentage():
    text = "The stock dropped 12.5% after the quarterly results."
    flags = detect_finance_flags(text)
    assert any(f.flag_type == "financial_figure" for f in flags)


def test_detects_regulatory_claim():
    text = "This fund is SEBI approved and regulated."
    flags = detect_finance_flags(text)
    assert any(f.flag_type == "regulatory_claim" for f in flags)


def test_no_flags_for_clean_text():
    text = "The Indian economy grew in the last quarter according to government data."
    flags = detect_finance_flags(text)
    # May detect some patterns, but investment_advice should not be flagged
    assert not any(f.flag_type == "investment_advice" for f in flags)


def test_returns_empty_list_for_empty_text():
    flags = detect_finance_flags("")
    assert flags == []


def test_flag_has_context_field():
    text = "SEBI announced new regulations for mutual funds yesterday."
    flags = detect_finance_flags(text)
    for flag in flags:
        assert flag.context != ""
        assert flag.content != ""
        assert flag.flag_type in ("investment_advice", "financial_figure", "regulatory_claim", "company_name")


def test_does_not_raise_on_exception():
    """detect_finance_flags must never raise."""
    # Even on unusual input, no exception
    flags = detect_finance_flags("normal text without issues")
    assert isinstance(flags, list)
```

```python
# backend/tests/agents/creation/test_db_writer.py
"""Tests for creation db_writer."""
from unittest.mock import MagicMock
from uuid import UUID

from app.agents.creation.db_writer import write_draft
from app.db.models import DraftCreate, Platform


def _make_draft_create(platform: str = "linkedin") -> DraftCreate:
    return DraftCreate(
        platform=Platform(platform),
        content_text="Test draft content for LinkedIn.",
        agent_reasoning="Strong angle for the platform.",
        source_idea_id=UUID("00000000-0000-0000-0000-000000000042"),
        finance_flags=[],
    )


def test_write_draft_returns_id_on_success():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "draft-uuid-001"}
    ]
    result = write_draft(sb, _make_draft_create())
    assert result == "draft-uuid-001"


def test_write_draft_returns_none_on_empty_data():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = []
    result = write_draft(sb, _make_draft_create())
    assert result is None


def test_write_draft_returns_none_on_exception():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.side_effect = RuntimeError("DB error")
    result = write_draft(sb, _make_draft_create("twitter"))
    assert result is None


def test_write_draft_serialises_platform_as_string():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "x"}]
    write_draft(sb, _make_draft_create("twitter"))
    payload = sb.table.return_value.insert.call_args[0][0]
    assert payload["platform"] == "twitter"
    assert isinstance(payload["platform"], str)


def test_write_draft_serialises_finance_flags_as_list():
    from app.db.models import FinanceFlag
    draft = DraftCreate(
        platform=Platform.LINKEDIN,
        content_text="Post with flags.",
        agent_reasoning="Test.",
        finance_flags=[FinanceFlag(flag_type="investment_advice", content="buy now", context="you should buy now")],
    )
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "y"}]
    write_draft(sb, draft)
    payload = sb.table.return_value.insert.call_args[0][0]
    assert isinstance(payload["finance_flags"], list)
    assert payload["finance_flags"][0]["flag_type"] == "investment_advice"


def test_write_draft_none_idea_id_serialised_as_none():
    draft = DraftCreate(
        platform=Platform.BLOG,
        content_text="Blog content here.",
        agent_reasoning="Blog angle.",
        source_idea_id=None,
    )
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "z"}]
    write_draft(sb, draft)
    payload = sb.table.return_value.insert.call_args[0][0]
    assert payload["source_idea_id"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/agents/creation/test_finance_flags.py tests/agents/creation/test_db_writer.py -v
```
Expected: ERRORS (ImportError)

- [ ] **Step 3: Create `backend/app/agents/creation/finance_flags.py`**

```python
"""
Finance flag detection for draft content.

Uses regex to identify potentially sensitive financial content that requires
human review before publishing. No AI calls — purely structural detection.
"""
import re
from typing import Optional

from app.db.models import FinanceFlag
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Patterns keyed by FinanceFlag.flag_type
_PATTERNS: dict[str, list[str]] = {
    "investment_advice": [
        r"\b(?:buy|sell|short|invest\s+in)\b",
        r"\bguaranteed\s+(?:return|profit|income|gain)\b",
        r"\b(?:should|must|need\s+to)\s+(?:buy|sell|invest)\b",
    ],
    "regulatory_claim": [
        r"\bSEBI[-\s](?:approved|registered|regulated|compliant|certified)\b",
        r"\bRBI[-\s](?:approved|registered|regulated|licensed)\b",
        r"\b(?:SEBI|RBI|NSE|BSE|IRDAI|PFRDA)\b",
    ],
    "company_name": [
        r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s+(?:Ltd|Limited|Corp|Inc|Pvt\.?|LLP)\b",
    ],
    "financial_figure": [
        r"₹\s*[\d,]+(?:\.\d+)?(?:\s*(?:crore|lakh|thousand|million|billion|cr|L))?",
        r"\b\d+(?:\.\d+)?%\b",
        r"\b\d{1,3}(?:,\d{3})+\b",
    ],
}

_CONTEXT_WINDOW = 100  # chars before/after the match for context


def _extract_context(text: str, match: re.Match) -> str:
    """Extract surrounding text as context for human review."""
    start = max(0, match.start() - _CONTEXT_WINDOW)
    end = min(len(text), match.end() + _CONTEXT_WINDOW)
    return text[start:end].strip()


def detect_finance_flags(content_text: str) -> list[FinanceFlag]:
    """
    Scan content_text for potentially sensitive financial patterns.

    Returns a list of FinanceFlag objects for inclusion in the draft.
    Returns [] on empty input or any internal error. Never raises.
    """
    if not content_text:
        return []

    try:
        seen: set[str] = set()
        flags: list[FinanceFlag] = []

        for flag_type, patterns in _PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, content_text, re.IGNORECASE):
                    matched_text = match.group().strip()
                    # Deduplicate: same flag_type + content pair
                    key = f"{flag_type}:{matched_text.lower()}"
                    if key in seen:
                        continue
                    seen.add(key)
                    flags.append(FinanceFlag(
                        flag_type=flag_type,
                        content=matched_text,
                        context=_extract_context(content_text, match),
                    ))

        return flags

    except Exception as exc:
        logger.error(f"detect_finance_flags: unexpected error | err={exc}")
        return []
```

- [ ] **Step 4: Create `backend/app/agents/creation/db_writer.py`**

```python
"""
DB write operations for the creation agent.
"""
from typing import Optional

from app.db.models import DraftCreate
from app.utils.logging import get_logger

logger = get_logger(__name__)


def write_draft(supabase, draft_create: DraftCreate) -> Optional[str]:
    """
    Insert a new draft into the drafts table.

    Returns the new draft UUID string on success, or None on failure.
    Never raises.
    """
    try:
        payload = {
            "platform":               draft_create.platform.value,
            "content_text":           draft_create.content_text,
            "agent_reasoning":        draft_create.agent_reasoning,
            "source_idea_id":         str(draft_create.source_idea_id)
                                      if draft_create.source_idea_id else None,
            "finance_flags":          [f.model_dump() for f in draft_create.finance_flags],
            "suggested_publish_time": (
                draft_create.suggested_publish_time.isoformat()
                if draft_create.suggested_publish_time else None
            ),
        }
        resp = supabase.table("drafts").insert(payload).execute()
        if not resp.data:
            logger.warning("write_draft: insert returned no data")
            return None
        return resp.data[0]["id"]
    except Exception as exc:
        logger.error(f"write_draft: failed | err={exc}")
        return None


def upsert_cost_log(supabase, agent_name: str, total_usd: float, token_count: int) -> None:
    """
    Accumulate daily cost for cost_log table.
    Read-then-write because supabase-py cannot do incremental upsert arithmetic.
    Never raises.
    """
    from datetime import date
    today = date.today().isoformat()
    try:
        existing = (
            supabase.table("cost_log")
            .select("token_count,estimated_cost_usd")
            .eq("agent_name", agent_name)
            .eq("date", today)
            .execute()
        )
        if existing.data:
            row = existing.data[0]
            new_tokens = row["token_count"] + token_count
            new_usd = row["estimated_cost_usd"] + total_usd
            supabase.table("cost_log").update(
                {"token_count": new_tokens, "estimated_cost_usd": round(new_usd, 6)}
            ).eq("agent_name", agent_name).eq("date", today).execute()
        else:
            supabase.table("cost_log").insert(
                {"agent_name": agent_name, "date": today,
                 "token_count": token_count, "estimated_cost_usd": round(total_usd, 6)}
            ).execute()
    except Exception as exc:
        logger.error(f"upsert_cost_log: failed | agent={agent_name} | err={exc}")
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/agents/creation/test_finance_flags.py tests/agents/creation/test_db_writer.py -v
```
Expected: all PASSED

- [ ] **Step 6: Run full suite**

```
pytest tests/ --ignore=tests/agents/research/test_install.py -q
```
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add app/agents/creation/finance_flags.py app/agents/creation/db_writer.py tests/agents/creation/test_finance_flags.py tests/agents/creation/test_db_writer.py
git commit -m "feat: add creation agent finance_flags and db_writer modules"
```
