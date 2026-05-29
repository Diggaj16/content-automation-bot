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
    clean_query = urlencode(sorted(clean_params.items()), doseq=True)
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

    if not result.success:
        logger.warning(
            "fetch_article: crawl unsuccessful",
            extra={"url": url},
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
