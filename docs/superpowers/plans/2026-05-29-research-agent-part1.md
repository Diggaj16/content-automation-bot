# Research Agent Part 1 — Scraping Infrastructure

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install Crawl4AI + Playwright on Windows and build the two core scraping modules — homepage link extractor and full-article content fetcher — with URL normalisation included.

**Architecture:** `scraper.py` takes a `CuratedSite` section URL and returns a list of article links by parsing `result.links["internal"]` from a Crawl4AI run. `extractor.py` takes a single article URL, fetches its full text via Crawl4AI, normalises the URL (strip UTM/fragments), detects paywalls by word count, and extracts publication date from page metadata. Both modules never raise — they return empty/safe defaults and log warnings so the caller can handle failures gracefully.

**Tech Stack:** `crawl4ai>=0.4.0`, `playwright` (bundled with crawl4ai), `pydantic>=2.5`, `pytest-asyncio`, `pytest-mock`

---

## File Structure

```
backend/
  pyproject.toml                           MODIFY — add crawl4ai dependency
  app/
    agents/
      __init__.py                          CREATE — empty package marker
      research/
        __init__.py                        CREATE — empty package marker
        scraper.py                         CREATE — homepage → article links
        extractor.py                       CREATE — article URL → text + metadata
tests/
  agents/
    __init__.py                            CREATE — empty package marker
    research/
      __init__.py                          CREATE — empty package marker
      test_scraper.py                      CREATE — unit tests for scraper
      test_extractor.py                    CREATE — unit tests for extractor
```

---

### Task 1: Install Crawl4AI and Playwright on Windows

**Files:**
- Modify: `backend/pyproject.toml` (dependencies list)

#### Background

Crawl4AI is an async Python web crawler that drives a headless Chromium browser via Playwright. On Windows you must install the Playwright browser binaries separately — `crawl4ai-setup` uses `--with-deps` which is Linux-only. Use `playwright install chromium` instead.

- [ ] **Step 1: Add crawl4ai to pyproject.toml**

Open `backend/pyproject.toml`. In `[project] dependencies`, add `crawl4ai>=0.4.0` after the existing `httpx` line:

```toml
[project]
dependencies = [
    "supabase>=2.3.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "arq>=0.26.1",
    "redis>=5.0.0,<6",
    "anthropic>=0.90.0",
    "voyageai>=0.3.2",
    "python-dotenv>=1.0.0",
    "httpx>=0.26.0,<0.29",
    "crawl4ai>=0.4.0",
]
```

- [ ] **Step 2: Install the new dependency**

From `backend/` with the venv active:

```bash
pip install -e ".[dev]"
```

Expected: crawl4ai and its dependencies (playwright, etc.) install without errors. If you see a conflict message about `httpx`, check the conflicting package and tighten the cap in pyproject.toml (e.g. `httpx>=0.26.0,<0.28`).

- [ ] **Step 3: Install Playwright browser binaries on Windows**

```bash
playwright install chromium
```

Expected output ends with:
```
Chromium ... downloaded to ...
```

Do NOT run `crawl4ai-setup` — it passes `--with-deps` which fails on Windows.

- [ ] **Step 4: Write the import smoke test**

Create `tests/agents/__init__.py`, `tests/agents/research/__init__.py` (both empty).

Create `tests/agents/research/test_install.py`:

```python
"""Smoke test: crawl4ai and playwright are importable and Chromium is present."""
import pytest


def test_crawl4ai_importable():
    """crawl4ai package and key classes import without error."""
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
    assert AsyncWebCrawler is not None
    assert CrawlerRunConfig is not None
    assert CacheMode is not None


def test_browser_config_importable():
    """BrowserConfig is available (crawl4ai >= 0.4.0)."""
    from crawl4ai import BrowserConfig
    assert BrowserConfig is not None
```

- [ ] **Step 5: Run the smoke test**

```bash
pytest tests/agents/research/test_install.py -v
```

Expected:
```
tests/agents/research/test_install.py::test_crawl4ai_importable PASSED
tests/agents/research/test_install.py::test_browser_config_importable PASSED
2 passed
```

If `BrowserConfig` is missing (older crawl4ai), upgrade: `pip install "crawl4ai>=0.4.0"`.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml tests/agents/__init__.py tests/agents/research/__init__.py tests/agents/research/test_install.py
git commit -m "feat: add crawl4ai dependency and install Playwright Chromium"
```

---

### Task 2: Homepage scraper — section page → article links

**Files:**
- Create: `backend/app/agents/__init__.py`
- Create: `backend/app/agents/research/__init__.py`
- Create: `backend/app/agents/research/scraper.py`
- Test: `backend/tests/agents/research/test_scraper.py`

#### Background

Each `curated_sites` row has a `section_url` like `https://www.livemint.com/market/stock-market-news`. The scraper fetches that page with Crawl4AI and extracts internal links that look like article URLs. It returns `ArticleLink` objects. It never raises — callers treat an empty list as a site failure.

Key Crawl4AI API (v0.4.x+):

```python
# CrawlResult attributes used here:
# result.success: bool
# result.links: dict — {"internal": [{"href": "...", "text": "...", "title": "..."}], "external": [...]}
```

Article vs navigation heuristics:
- Skip URLs matching `/page/`, `/tag/`, `/author/`, `/category/`, `/search/`, `/login/`, `/subscribe/`, `/newsletter/`
- Skip link text shorter than 20 characters
- Accept URLs matching any of: date pattern `/YYYY/MM/`, `/article`, `/story`, `/news/`, long slug ≥ 20 chars at end

- [ ] **Step 1: Write the failing tests**

Create `tests/agents/research/test_scraper.py`:

```python
"""Unit tests for app.agents.research.scraper."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.research.scraper import scrape_homepage, ArticleLink, _looks_like_article


# ── _looks_like_article ───────────────────────────────────────────────────────

class TestLooksLikeArticle:
    def test_accepts_dated_path(self):
        assert _looks_like_article(
            href="/markets/2025/05/sebi-new-rules-for-traders",
            text="SEBI announces sweeping new rules for F&O traders starting June",
        )

    def test_accepts_article_in_path(self):
        assert _looks_like_article(
            href="/article/rbi-policy-2025",
            text="RBI holds rates steady for the fifth consecutive meeting in a row",
        )

    def test_accepts_story_in_path(self):
        assert _looks_like_article(
            href="/story/nifty-hits-all-time-high-on-foreign-inflows",
            text="Nifty hits all-time high as foreign institutional investors flood back",
        )

    def test_rejects_short_text(self):
        assert not _looks_like_article(
            href="/markets/2025/05/sebi-new-rules",
            text="Markets",
        )

    def test_rejects_exactly_19_chars(self):
        # Title must be >= 20 chars
        assert not _looks_like_article(
            href="/markets/2025/05/article",
            text="A" * 19,
        )

    def test_accepts_exactly_20_chars(self):
        assert _looks_like_article(
            href="/markets/2025/05/article",
            text="A" * 20,
        )

    def test_rejects_pagination(self):
        assert not _looks_like_article(
            href="/page/2",
            text="SEBI announces sweeping new rules for F&O traders starting June",
        )

    def test_rejects_author_page(self):
        assert not _looks_like_article(
            href="/author/rahul-sharma",
            text="Rahul Sharma writes extensively about finance and capital markets",
        )

    def test_rejects_tag_page(self):
        assert not _looks_like_article(
            href="/tag/sensex",
            text="All articles tagged with Sensex covering Indian equity markets",
        )

    def test_rejects_subscribe_page(self):
        assert not _looks_like_article(
            href="/subscribe/premium",
            text="Subscribe to our premium plan for unlimited access to all articles",
        )

    def test_rejects_no_article_pattern(self):
        # Short path, no date, no article/story keyword
        assert not _looks_like_article(
            href="/markets",
            text="Markets section covering all Indian equity and commodity markets",
        )


# ── scrape_homepage ───────────────────────────────────────────────────────────

def _make_mock_crawler(links: list[dict], success: bool = True) -> AsyncMock:
    """Build a mock AsyncWebCrawler async context manager."""
    mock_result = MagicMock()
    mock_result.success = success
    mock_result.links = {"internal": links, "external": []}

    mock_instance = AsyncMock()
    mock_instance.arun.return_value = mock_result
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    return mock_instance


@pytest.mark.asyncio
async def test_scrape_homepage_returns_article_links():
    mock_crawler = _make_mock_crawler([
        {
            "href": "/markets/2025/05/sebi-tightens-fno-eligibility-rules-for-stock-derivatives",
            "text": "SEBI tightens F&O eligibility: 45 stocks may be dropped from derivatives next month",
            "title": "",
        },
        {
            "href": "/story/rbi-holds-rates-steady-amid-inflation-concerns",
            "text": "RBI holds rates steady — what it means for your EMI and home loan",
            "title": "",
        },
    ])

    with patch("app.agents.research.scraper.AsyncWebCrawler", return_value=mock_crawler):
        links = await scrape_homepage(
            section_url="https://www.livemint.com/market/stock-market-news",
            site_name="LiveMint Stock Market",
        )

    assert len(links) == 2
    assert all(isinstance(lnk, ArticleLink) for lnk in links)
    assert links[0].source_name == "LiveMint Stock Market"
    assert "SEBI" in links[0].title


@pytest.mark.asyncio
async def test_scrape_homepage_filters_nav_links():
    mock_crawler = _make_mock_crawler([
        {
            "href": "/page/2",
            "text": "Next page of stock market results for today's trading session",
            "title": "",
        },
        {
            "href": "/author/priya-sharma",
            "text": "Priya Sharma is a senior finance journalist covering equity markets",
            "title": "",
        },
        {
            "href": "/markets/2025/05/sensex-gains-500-points-on-strong-global-cues",
            "text": "Sensex gains 500 points as global markets rally on Fed pivot hopes",
            "title": "",
        },
    ])

    with patch("app.agents.research.scraper.AsyncWebCrawler", return_value=mock_crawler):
        links = await scrape_homepage(
            section_url="https://www.livemint.com/market/stock-market-news",
            site_name="LiveMint Stock Market",
        )

    assert len(links) == 1
    assert "Sensex" in links[0].title


@pytest.mark.asyncio
async def test_scrape_homepage_deduplicates_links():
    mock_crawler = _make_mock_crawler([
        {
            "href": "/markets/2025/05/sensex-500-points",
            "text": "Sensex gains 500 points as global markets rally on Fed pivot hopes",
            "title": "",
        },
        {
            # Same href — duplicate
            "href": "/markets/2025/05/sensex-500-points",
            "text": "Sensex gains 500 points as global markets rally on Fed pivot hopes",
            "title": "",
        },
    ])

    with patch("app.agents.research.scraper.AsyncWebCrawler", return_value=mock_crawler):
        links = await scrape_homepage(
            section_url="https://www.livemint.com/market/stock-market-news",
            site_name="LiveMint Stock Market",
        )

    assert len(links) == 1


@pytest.mark.asyncio
async def test_scrape_homepage_returns_empty_on_failed_crawl():
    mock_crawler = _make_mock_crawler([], success=False)

    with patch("app.agents.research.scraper.AsyncWebCrawler", return_value=mock_crawler):
        links = await scrape_homepage(
            section_url="https://www.livemint.com/market/stock-market-news",
            site_name="LiveMint Stock Market",
        )

    assert links == []


@pytest.mark.asyncio
async def test_scrape_homepage_returns_empty_on_exception():
    mock_instance = AsyncMock()
    mock_instance.arun.side_effect = Exception("Playwright crashed")
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)

    with patch("app.agents.research.scraper.AsyncWebCrawler", return_value=mock_instance):
        links = await scrape_homepage(
            section_url="https://www.livemint.com/market/stock-market-news",
            site_name="LiveMint Stock Market",
        )

    assert links == []


@pytest.mark.asyncio
async def test_scrape_homepage_makes_relative_urls_absolute():
    """Relative /path links must be prefixed with the site origin."""
    mock_crawler = _make_mock_crawler([
        {
            "href": "/markets/2025/05/rbi-policy-rate-unchanged-sixth-meeting",
            "text": "RBI keeps policy rate unchanged for the sixth consecutive monetary meeting",
            "title": "",
        },
    ])

    with patch("app.agents.research.scraper.AsyncWebCrawler", return_value=mock_crawler):
        links = await scrape_homepage(
            section_url="https://www.livemint.com/market/stock-market-news",
            site_name="LiveMint Stock Market",
        )

    assert links[0].url.startswith("https://www.livemint.com")
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/agents/research/test_scraper.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `app.agents.research.scraper` does not exist yet.

- [ ] **Step 3: Create package markers**

Create `backend/app/agents/__init__.py` (empty file):
```python
```

Create `backend/app/agents/research/__init__.py` (empty file):
```python
```

- [ ] **Step 4: Create `scraper.py`**

Create `backend/app/agents/research/scraper.py`:

```python
"""
Homepage scraper: fetches a section page and returns article links.

Usage:
    links = await scrape_homepage(
        section_url="https://www.livemint.com/market/stock-market-news",
        site_name="LiveMint Stock Market",
    )
"""
import re
from urllib.parse import urlparse

from pydantic import BaseModel
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

from app.utils.logging import get_logger

logger = get_logger(__name__)

# URL sub-strings that signal navigation / non-article pages — skip them
_SKIP_URL_RE = re.compile(
    r"/(page|tag|author|category|search|login|subscribe|newsletters?)/",
    re.IGNORECASE,
)

# URL sub-strings that strongly suggest an article page
_ARTICLE_URL_RE = re.compile(
    r"(/\d{4}/\d{2}/|/article|/story|/news/|[a-z0-9-]{20,}$)",
    re.IGNORECASE,
)

# Minimum headline length — shorter strings are nav labels, not headlines
_MIN_TITLE_LEN = 20


class ArticleLink(BaseModel):
    url: str
    title: str
    source_name: str


def _looks_like_article(href: str, text: str) -> bool:
    """Return True if this link looks like an article rather than nav/pagination."""
    if _SKIP_URL_RE.search(href):
        return False
    if len(text.strip()) < _MIN_TITLE_LEN:
        return False
    if not _ARTICLE_URL_RE.search(href):
        return False
    return True


async def scrape_homepage(
    section_url: str,
    site_name: str,
    *,
    timeout_ms: int = 30_000,
) -> list[ArticleLink]:
    """
    Fetch a section page and extract article links.

    Returns a de-duplicated list of ArticleLink objects.
    Returns an empty list (never raises) on crawl failure — the caller
    should treat an empty result as a site health failure.
    """
    browser_cfg = BrowserConfig(headless=True, verbose=False)
    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        page_timeout=timeout_ms,
        word_count_threshold=1,  # don't skip low-word pages (section indexes)
    )

    try:
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=section_url, config=run_cfg)
    except Exception as exc:
        logger.warning(
            "scrape_homepage failed",
            extra={"site": site_name, "url": section_url, "error": str(exc)},
        )
        return []

    if not result.success:
        logger.warning(
            "scrape_homepage: crawl unsuccessful",
            extra={"site": site_name, "url": section_url},
        )
        return []

    parsed_base = urlparse(section_url)
    base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"

    seen: set[str] = set()
    links: list[ArticleLink] = []

    for link in result.links.get("internal", []):
        href: str = link.get("href", "")
        text: str = (link.get("text") or link.get("title") or "").strip()

        # Make relative URLs absolute
        if href.startswith("/"):
            href = base_origin + href
        if not href.startswith("http"):
            continue

        if href in seen:
            continue
        seen.add(href)

        if _looks_like_article(href, text):
            links.append(ArticleLink(url=href, title=text, source_name=site_name))

    logger.info(
        "scrape_homepage complete",
        extra={"site": site_name, "found": len(links)},
    )
    return links
```

- [ ] **Step 5: Run tests — all should pass**

```bash
pytest tests/agents/research/test_scraper.py -v
```

Expected:
```
tests/agents/research/test_scraper.py::TestLooksLikeArticle::test_accepts_dated_path PASSED
tests/agents/research/test_scraper.py::TestLooksLikeArticle::test_accepts_article_in_path PASSED
tests/agents/research/test_scraper.py::TestLooksLikeArticle::test_accepts_story_in_path PASSED
tests/agents/research/test_scraper.py::TestLooksLikeArticle::test_rejects_short_text PASSED
tests/agents/research/test_scraper.py::TestLooksLikeArticle::test_rejects_exactly_19_chars PASSED
tests/agents/research/test_scraper.py::TestLooksLikeArticle::test_accepts_exactly_20_chars PASSED
tests/agents/research/test_scraper.py::TestLooksLikeArticle::test_rejects_pagination PASSED
tests/agents/research/test_scraper.py::TestLooksLikeArticle::test_rejects_author_page PASSED
tests/agents/research/test_scraper.py::TestLooksLikeArticle::test_rejects_tag_page PASSED
tests/agents/research/test_scraper.py::TestLooksLikeArticle::test_rejects_subscribe_page PASSED
tests/agents/research/test_scraper.py::TestLooksLikeArticle::test_rejects_no_article_pattern PASSED
tests/agents/research/test_scraper.py::test_scrape_homepage_returns_article_links PASSED
tests/agents/research/test_scraper.py::test_scrape_homepage_filters_nav_links PASSED
tests/agents/research/test_scraper.py::test_scrape_homepage_deduplicates_links PASSED
tests/agents/research/test_scraper.py::test_scrape_homepage_returns_empty_on_failed_crawl PASSED
tests/agents/research/test_scraper.py::test_scrape_homepage_returns_empty_on_exception PASSED
tests/agents/research/test_scraper.py::test_scrape_homepage_makes_relative_urls_absolute PASSED
17 passed
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/__init__.py backend/app/agents/research/__init__.py backend/app/agents/research/scraper.py tests/agents/research/test_scraper.py
git commit -m "feat: add research agent scraper module (homepage -> article links)"
```

---

### Task 3: Article extractor — URL → full text + metadata

**Files:**
- Create: `backend/app/agents/research/extractor.py`
- Test: `backend/tests/agents/research/test_extractor.py`

#### Background

After the scraper returns article links, the extractor fetches each article individually. It:
1. **Normalises the URL** — strips UTM params, fragments, trailing slashes, lowercases scheme/host
2. **Fetches full text** — `result.markdown` is Crawl4AI's clean markdown output
3. **Detects paywalls** — if fewer than 80 words were extracted, the page was probably blocked
4. **Extracts pub date** — reads `article:published_time`, `datePublished`, or `pubdate` from `result.metadata`

On any error the function returns an `ArticleContent` with `full_text=""` and `paywall_detected=True`. The caller (Part 2) will decide whether to attempt a vision fallback.

Key Crawl4AI API:
```python
# result.markdown: str  — clean text (empty string if nothing extracted)
# result.metadata: dict — keys include "title", "og:title", "article:published_time",
#                         "datePublished", "pubdate"
# result.success: bool
```

UTM and tracking params to strip: `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`,
`utm_content`, `ref`, `referrer`, `source`, `fbclid`, `gclid`, `_ga`, `mc_cid`, `mc_eid`.

- [ ] **Step 1: Write the failing tests**

Create `tests/agents/research/test_extractor.py`:

```python
"""Unit tests for app.agents.research.extractor."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.research.extractor import normalize_url, fetch_article, ArticleContent


# ── normalize_url ─────────────────────────────────────────────────────────────

class TestNormalizeUrl:
    def test_strips_utm_source(self):
        url = "https://www.livemint.com/markets/article?utm_source=google"
        assert "utm_source" not in normalize_url(url)

    def test_strips_multiple_utm_params(self):
        url = "https://www.livemint.com/markets/article?utm_source=google&utm_medium=cpc&utm_campaign=daily"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "utm_campaign" not in result

    def test_strips_fbclid(self):
        url = "https://www.livemint.com/markets/article?fbclid=abc123"
        assert "fbclid" not in normalize_url(url)

    def test_strips_fragment(self):
        url = "https://www.livemint.com/markets/article#comments"
        result = normalize_url(url)
        assert "#" not in result
        assert "comments" not in result

    def test_lowercases_scheme(self):
        url = "HTTPS://www.livemint.com/markets/article"
        assert normalize_url(url).startswith("https://")

    def test_lowercases_host(self):
        url = "https://WWW.Livemint.com/markets/article"
        assert normalize_url(url).startswith("https://www.livemint.com")

    def test_strips_trailing_slash_from_path(self):
        url = "https://www.livemint.com/markets/article/"
        result = normalize_url(url)
        assert not result.rstrip("?").endswith("/")

    def test_preserves_real_query_params(self):
        url = "https://example.com/search?q=SEBI&page=2"
        result = normalize_url(url)
        assert "q=SEBI" in result
        assert "page=2" in result

    def test_strips_tracking_but_keeps_real_params(self):
        url = "https://example.com/article?id=123&utm_source=newsletter"
        result = normalize_url(url)
        assert "id=123" in result
        assert "utm_source" not in result

    def test_idempotent(self):
        url = "https://www.livemint.com/markets/article"
        assert normalize_url(normalize_url(url)) == normalize_url(url)


# ── fetch_article ─────────────────────────────────────────────────────────────

def _make_mock_crawler(
    markdown: str = "",
    metadata: dict | None = None,
    success: bool = True,
    side_effect: Exception | None = None,
) -> AsyncMock:
    mock_result = MagicMock()
    mock_result.success = success
    mock_result.markdown = markdown
    mock_result.metadata = metadata or {}

    mock_instance = AsyncMock()
    if side_effect:
        mock_instance.arun.side_effect = side_effect
    else:
        mock_instance.arun.return_value = mock_result
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    return mock_instance


@pytest.mark.asyncio
async def test_fetch_article_success_no_paywall():
    long_text = " ".join(["word"] * 300)  # 300 words — above paywall threshold
    mock_crawler = _make_mock_crawler(
        markdown=long_text,
        metadata={
            "title": "RBI raises rates by 25bps in surprise move",
            "article:published_time": "2025-05-15T10:30:00Z",
        },
    )

    with patch("app.agents.research.extractor.AsyncWebCrawler", return_value=mock_crawler):
        content = await fetch_article("https://www.livemint.com/markets/rbi-raises-rates")

    assert isinstance(content, ArticleContent)
    assert content.word_count == 300
    assert content.paywall_detected is False
    assert content.title == "RBI raises rates by 25bps in surprise move"
    assert content.publication_date is not None
    assert content.publication_date.year == 2025
    assert content.publication_date.month == 5


@pytest.mark.asyncio
async def test_fetch_article_paywall_detected_on_low_word_count():
    mock_crawler = _make_mock_crawler(
        markdown="Subscribe to read this article.",  # 6 words
        metadata={"title": "Premium article behind paywall"},
    )

    with patch("app.agents.research.extractor.AsyncWebCrawler", return_value=mock_crawler):
        content = await fetch_article("https://www.livemint.com/premium/article")

    assert content.paywall_detected is True
    assert content.word_count < 80


@pytest.mark.asyncio
async def test_fetch_article_exactly_at_paywall_threshold():
    # 80 words is exactly the threshold — should NOT be a paywall
    text = " ".join(["word"] * 80)
    mock_crawler = _make_mock_crawler(markdown=text, metadata={"title": "Article"})

    with patch("app.agents.research.extractor.AsyncWebCrawler", return_value=mock_crawler):
        content = await fetch_article("https://example.com/article")

    assert content.paywall_detected is False


@pytest.mark.asyncio
async def test_fetch_article_exception_returns_safe_default():
    mock_crawler = _make_mock_crawler(side_effect=Exception("Connection refused"))

    with patch("app.agents.research.extractor.AsyncWebCrawler", return_value=mock_crawler):
        content = await fetch_article("https://www.livemint.com/markets/article")

    assert content.word_count == 0
    assert content.paywall_detected is True
    assert content.full_text == ""
    assert content.title == ""


@pytest.mark.asyncio
async def test_fetch_article_uses_og_title_fallback():
    long_text = " ".join(["word"] * 200)
    mock_crawler = _make_mock_crawler(
        markdown=long_text,
        metadata={
            "title": "",          # empty title
            "og:title": "OG Title for article about Indian markets",
        },
    )

    with patch("app.agents.research.extractor.AsyncWebCrawler", return_value=mock_crawler):
        content = await fetch_article("https://example.com/article")

    assert content.title == "OG Title for article about Indian markets"


@pytest.mark.asyncio
async def test_fetch_article_handles_missing_pub_date():
    long_text = " ".join(["word"] * 200)
    mock_crawler = _make_mock_crawler(markdown=long_text, metadata={"title": "Some article"})

    with patch("app.agents.research.extractor.AsyncWebCrawler", return_value=mock_crawler):
        content = await fetch_article("https://example.com/article")

    assert content.publication_date is None


@pytest.mark.asyncio
async def test_fetch_article_normalized_url_strips_utm():
    long_text = " ".join(["word"] * 200)
    mock_crawler = _make_mock_crawler(markdown=long_text, metadata={"title": "Article"})
    url_with_utm = "https://www.livemint.com/markets/article?utm_source=google&utm_medium=cpc"

    with patch("app.agents.research.extractor.AsyncWebCrawler", return_value=mock_crawler):
        content = await fetch_article(url_with_utm)

    assert "utm_source" not in content.normalized_url
    assert content.url == url_with_utm   # original URL preserved
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/agents/research/test_extractor.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.agents.research.extractor'`

- [ ] **Step 3: Create `extractor.py`**

Create `backend/app/agents/research/extractor.py`:

```python
"""
Article extractor: fetches a single article URL, extracts full text and metadata.

Also provides normalize_url() which is used by both the extractor and the
dedup checker (Part 2) to produce canonical URLs before DB lookups.

Usage:
    content = await fetch_article("https://www.livemint.com/markets/some-article")
    # content.full_text, content.word_count, content.paywall_detected, ...
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from pydantic import BaseModel
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Query parameter keys that are tracking noise — strip them from canonical URLs
_TRACKING_PARAMS: frozenset[str] = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "referrer", "source", "fbclid", "gclid", "_ga", "mc_cid", "mc_eid",
})

# Articles with fewer extracted words than this are likely paywalled or JS-heavy
_PAYWALL_WORD_THRESHOLD = 80


class ArticleContent(BaseModel):
    url: str                              # original URL as passed in
    normalized_url: str                   # canonical form for dedup
    title: str
    full_text: str                        # crawl4ai markdown output
    word_count: int
    paywall_detected: bool
    publication_date: Optional[datetime] = None


def normalize_url(url: str) -> str:
    """
    Return a canonical URL for deduplication:
    - lowercase scheme + host
    - strip fragment
    - strip tracking/UTM query params (see _TRACKING_PARAMS)
    - remove trailing slash from path
    """
    parsed = urlparse(url)

    clean_params = {
        k: v
        for k, v in parse_qs(parsed.query, keep_blank_values=False).items()
        if k.lower() not in _TRACKING_PARAMS
    }
    clean_query = urlencode(clean_params, doseq=True)
    clean_path = parsed.path.rstrip("/") or "/"

    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        clean_path,
        parsed.params,
        clean_query,
        "",   # no fragment
    ))


async def fetch_article(
    url: str,
    *,
    timeout_ms: int = 30_000,
) -> ArticleContent:
    """
    Fetch and extract the full text of a single article URL.

    Never raises. On failure returns ArticleContent with:
      - full_text = ""
      - word_count = 0
      - paywall_detected = True
    so the caller (Part 2) can decide whether to attempt a vision fallback.
    """
    normalized = normalize_url(url)

    browser_cfg = BrowserConfig(headless=True, verbose=False)
    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        page_timeout=timeout_ms,
        word_count_threshold=1,
    )

    try:
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=run_cfg)
    except Exception as exc:
        logger.warning(
            "fetch_article failed",
            extra={"url": url, "error": str(exc)},
        )
        return ArticleContent(
            url=url,
            normalized_url=normalized,
            title="",
            full_text="",
            word_count=0,
            paywall_detected=True,
        )

    full_text: str = result.markdown or ""
    word_count = len(full_text.split())
    paywall_detected = word_count < _PAYWALL_WORD_THRESHOLD

    # Title: prefer explicit title, fall back to og:title
    meta: dict = result.metadata or {}
    title = (
        meta.get("title")
        or meta.get("og:title")
        or ""
    ).strip()

    # Publication date from structured metadata
    pub_date: Optional[datetime] = None
    raw_date = (
        meta.get("article:published_time")
        or meta.get("datePublished")
        or meta.get("pubdate")
    )
    if raw_date:
        try:
            pub_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    logger.info(
        "fetch_article complete",
        extra={"url": url, "words": word_count, "paywall": paywall_detected},
    )
    return ArticleContent(
        url=url,
        normalized_url=normalized,
        title=title,
        full_text=full_text,
        word_count=word_count,
        paywall_detected=paywall_detected,
        publication_date=pub_date,
    )
```

- [ ] **Step 4: Run all tests — should all pass**

```bash
pytest tests/agents/research/test_extractor.py -v
```

Expected:
```
tests/agents/research/test_extractor.py::TestNormalizeUrl::test_strips_utm_source PASSED
tests/agents/research/test_extractor.py::TestNormalizeUrl::test_strips_multiple_utm_params PASSED
tests/agents/research/test_extractor.py::TestNormalizeUrl::test_strips_fbclid PASSED
tests/agents/research/test_extractor.py::TestNormalizeUrl::test_strips_fragment PASSED
tests/agents/research/test_extractor.py::TestNormalizeUrl::test_lowercases_scheme PASSED
tests/agents/research/test_extractor.py::TestNormalizeUrl::test_lowercases_host PASSED
tests/agents/research/test_extractor.py::TestNormalizeUrl::test_strips_trailing_slash_from_path PASSED
tests/agents/research/test_extractor.py::TestNormalizeUrl::test_preserves_real_query_params PASSED
tests/agents/research/test_extractor.py::TestNormalizeUrl::test_strips_tracking_but_keeps_real_params PASSED
tests/agents/research/test_extractor.py::TestNormalizeUrl::test_idempotent PASSED
tests/agents/research/test_extractor.py::test_fetch_article_success_no_paywall PASSED
tests/agents/research/test_extractor.py::test_fetch_article_paywall_detected_on_low_word_count PASSED
tests/agents/research/test_extractor.py::test_fetch_article_exactly_at_paywall_threshold PASSED
tests/agents/research/test_extractor.py::test_fetch_article_exception_returns_safe_default PASSED
tests/agents/research/test_extractor.py::test_fetch_article_uses_og_title_fallback PASSED
tests/agents/research/test_extractor.py::test_fetch_article_handles_missing_pub_date PASSED
tests/agents/research/test_extractor.py::test_fetch_article_normalized_url_strips_utm PASSED
17 passed
```

Run the full test suite to confirm nothing regressed:

```bash
pytest -m "not integration" -v
```

Expected: all existing tests still pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/research/extractor.py tests/agents/research/test_extractor.py
git commit -m "feat: add research agent extractor module (URL normalisation + article text fetch)"
```

---

## Self-Review

**Spec coverage:**
- [x] Crawl4AI + Playwright installed and verified — Task 1
- [x] Homepage scraping to extract article links — Task 2 (`scrape_homepage`)
- [x] Article content fetching — Task 3 (`fetch_article`)
- [x] URL normalisation (prerequisite for dedup in Part 2) — Task 3 (`normalize_url`)
- [x] Paywall detection via word count — Task 3
- [x] Never-raise guarantee on scraping failures — Tasks 2 & 3
- [ ] Age filter, dedup check, pre-scoring — covered in Part 2
- [ ] Structured summarisation — covered in Part 2
- [ ] DB writes + arq wiring — covered in Part 3

**Placeholder scan:** None found.

**Type consistency:**
- `ArticleLink` (Task 2: scraper.py) — used in Task 2 tests only
- `ArticleContent` (Task 3: extractor.py) — used in Task 3 tests only; Part 2 will import both
- `normalize_url(url: str) -> str` — consistent across extractor.py and its tests
- `fetch_article(url: str, *, timeout_ms: int) -> ArticleContent` — consistent
- `scrape_homepage(section_url: str, site_name: str, *, timeout_ms: int) -> list[ArticleLink]` — consistent
