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
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from app.utils.logging import get_logger

logger = get_logger(__name__)

# JavaScript injected before content extraction to expand truncated articles.
# Clicks "Read more / Show more / Continue reading" buttons (by selector and text),
# then scrolls the full page to trigger lazy-loaded content.
_EXPAND_ARTICLE_JS = """
(async () => {
    const selectorPatterns = [
        'button[class*="read-more"]', 'button[class*="readmore"]',
        'button[class*="show-more"]', 'button[class*="showmore"]',
        'a[class*="read-more"]',     'a[class*="readmore"]',
        '.read-more-btn', '.show-more-btn', '.expand-btn',
        '[data-testid*="read-more"]', '[data-action*="expand"]',
        '[aria-label*="Read more"]',  '[aria-label*="Show more"]',
    ];
    for (const sel of selectorPatterns) {
        try {
            document.querySelectorAll(sel).forEach(el => {
                if (el.offsetParent !== null) el.click();
            });
        } catch (_) {}
    }
    // Text-based fallback: click visible buttons whose label matches
    const clickable = [...document.querySelectorAll(
        'button, a[role="button"], span[role="button"], [class*="btn"]'
    )];
    clickable
        .filter(el => /read\\s*more|show\\s*more|expand|continue\\s*reading/i.test(
            (el.innerText || el.textContent || '').trim()
        ))
        .filter(el => el.offsetParent !== null)
        .forEach(el => { try { el.click(); } catch (_) {} });
    // Scroll to trigger lazy-loaded content
    window.scrollTo(0, document.body.scrollHeight / 2);
    await new Promise(r => setTimeout(r, 400));
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise(r => setTimeout(r, 400));
})();
"""

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


def _profile_dir_for(url: str, sessions_dir: Optional[str]) -> Optional[str]:
    """Return the persistent browser profile path for this URL's domain if it exists.

    Only returns a path when the user has already logged in (profile dir present).
    A missing profile means no saved session — scrape without authentication.
    """
    if not sessions_dir:
        return None
    from pathlib import Path
    domain = urlparse(url).netloc.lstrip("www.")
    path = Path(sessions_dir).expanduser() / domain
    return str(path) if path.exists() else None


async def fetch_article(
    url: str,
    *,
    timeout_ms: int = 30_000,
    sessions_dir: Optional[str] = None,
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

    profile_dir = _profile_dir_for(url, sessions_dir)
    browser_cfg = BrowserConfig(
        headless=True,
        verbose=False,
        user_data_dir=profile_dir,            # None = fresh context; str = use saved session
        use_persistent_context=bool(profile_dir),
    )
    if profile_dir:
        logger.info("fetch_article: using saved login session", extra={"domain": urlparse(url).netloc})

    # PruningContentFilter removes nav, footer, ads, and other low-density blocks
    # so that full_text contains only the article body, not the entire page.
    # threshold=0.45 is a good balance — lower keeps more content, higher is stricter.
    _content_filter = PruningContentFilter(threshold=0.45, threshold_type="fixed")
    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        page_timeout=timeout_ms,
        word_count_threshold=10,      # skip tiny blocks (nav labels, button text, etc.)
        markdown_generator=DefaultMarkdownGenerator(content_filter=_content_filter),
        js_code=_EXPAND_ARTICLE_JS,   # click "read more" buttons + scroll for lazy content
        delay_before_return_html=500,  # 0.5s is sufficient after scroll+click JS
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

    # fit_markdown is the pruned article body — fall back to full markdown only if empty
    full_text: str = result.fit_markdown or result.markdown or ""
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
