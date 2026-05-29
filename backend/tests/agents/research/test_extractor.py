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
        # path should not end with / (root path "/" is OK)
        path = result.split("?")[0]
        assert not path.endswith("/") or path == "https://www.livemint.com/"

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
        # With query params — normalizing twice should give the same result
        url = "https://www.livemint.com/markets/article?page=2&id=123"
        assert normalize_url(normalize_url(url)) == normalize_url(url)

    def test_stable_param_ordering(self):
        # Same params in different order must normalize to the same URL
        url_a = "https://example.com/article?id=1&page=2"
        url_b = "https://example.com/article?page=2&id=1"
        assert normalize_url(url_a) == normalize_url(url_b)


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
async def test_fetch_article_returns_safe_default_on_failed_crawl():
    """result.success=False should return same safe default as an exception."""
    mock_crawler = _make_mock_crawler(
        markdown="Some text that would pass paywall threshold " * 10,
        metadata={"title": "Some article"},
        success=False,
    )

    with patch("app.agents.research.extractor.AsyncWebCrawler", return_value=mock_crawler):
        content = await fetch_article("https://example.com/article")

    assert content.word_count == 0
    assert content.paywall_detected is True
    assert content.full_text == ""


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
