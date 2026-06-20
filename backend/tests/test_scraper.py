"""
Pure-logic tests for app.agents.research.scraper's link classification —
no network, no browser launch.
"""
from app.agents.research.scraper import _looks_like_article


class TestLooksLikeArticle:
    def test_accepts_story_path(self):
        href = "https://www.businesstoday.in/markets/ipo-corner/story/jio-platforms-ipo-538065-2026-06-19"
        assert _looks_like_article(href, "Jio Platforms IPO announced in RIL AGM") is True

    def test_accepts_article_path(self):
        href = "https://www.financialexpress.com/business/news/reliance-news/4272025/"
        assert _looks_like_article(href, "Reliance Consumer targets Rs 1 lakh crore topline") is True

    def test_accepts_numeric_id_path(self):
        href = "https://www.cnbctv18.com/market/fiis-data-today-19928852.htm"
        assert _looks_like_article(href, "FIIs post strongest buying since February") is True

    def test_rejects_tag_page(self):
        href = "https://example.com/tag/markets"
        assert _looks_like_article(href, "Markets — all stories on this topic") is False

    def test_rejects_login_page(self):
        href = "https://example.com/login?next=/markets"
        assert _looks_like_article(href, "Login to read more stories now") is False

    def test_rejects_share_price_ticker_page(self):
        href = "https://www.business-standard.com/markets/suzlon-energy-ltd-share-price-13872.html"
        assert _looks_like_article(href, "Suzlon Energy Ltd Share Price Today") is False

    def test_rejects_short_title(self):
        href = "https://example.com/markets/story/short-title-12345"
        assert _looks_like_article(href, "Too short") is False

    def test_rejects_gallery_page(self):
        href = "https://example.com/gallery/best-stocks-2026"
        assert _looks_like_article(href, "Best stocks to watch this year in gallery") is False

    def test_rejects_url_with_no_article_signal(self):
        href = "https://example.com/about-us"
        assert _looks_like_article(href, "About our company and our long history") is False
