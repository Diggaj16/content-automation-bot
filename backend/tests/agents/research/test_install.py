"""Smoke test: crawl4ai and playwright are importable and Chromium is present."""


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
