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
