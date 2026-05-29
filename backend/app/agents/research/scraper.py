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
    r"/(page|tag|author|category|search|login|subscribe|newsletters?)(/|$)",
    re.IGNORECASE,
)

# URL sub-strings that strongly suggest an article page
_ARTICLE_URL_RE = re.compile(
    r"(/\d{4}/\d{2}/|/article|/story|/news/|[a-z0-9-]{20,}/?$)",
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
