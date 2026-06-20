"""
Homepage scraper: fetches a section page and returns article links.

Uses raw Playwright (no crawl4ai). Accepts an optional shared Browser instance.

Usage:
    links = await scrape_homepage(
        section_url="https://www.livemint.com/market/stock-market-news",
        site_name="LiveMint Stock Market",
        browser=shared_browser,   # optional — omit for standalone use
    )
"""
import re
from typing import Optional
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Browser
from pydantic import BaseModel

from app.agents.research.extractor import BROWSER_ARGS, BROWSER_CHANNEL, USER_AGENT
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Dismisses cookie banners, login modals, and subscription overlays common on
# Indian news sites (MoneyControl, ET, Financial Express, etc.).
_DISMISS_POPUPS_JS = """
(async () => {
    // Click common accept/close buttons
    const dismissSelectors = [
        // Cookie consent
        '#onetrust-accept-btn-handler',
        '.onetrust-close-btn-handler',
        'button[id*="accept"]',
        'button[class*="accept"]',
        'button[class*="cookie"]',
        '[aria-label*="Accept"]',
        '[aria-label*="Close"]',
        // Generic modal close
        'button[class*="close"]',
        'button[class*="dismiss"]',
        '.modal-close',
        '.popup-close',
        '[data-dismiss="modal"]',
        // MoneyControl specific
        '.login_close_btn',
        '#mc_login .icon-close',
        '.loginbar .close',
        '.modal .close',
        '.popup .close',
        // Financial Express
        '.gdpr-btn',
        '.consent-btn',
        // ET specific
        '#close_button',
        '.prime-close',
    ];
    for (const sel of dismissSelectors) {
        try {
            document.querySelectorAll(sel).forEach(el => {
                if (el.offsetParent !== null || el.getBoundingClientRect().height > 0) {
                    el.click();
                }
            });
        } catch (_) {}
    }
    // Force-remove common overlay elements that block the page
    const overlaySelectors = [
        '.modal-backdrop', '.overlay', '#overlay',
        '.popup-overlay', '.modal-overlay',
        '[class*="modal"]', '[class*="popup"]',
        '#loginOverlay', '.login-overlay',
        '.subscription-wall', '.paywall-overlay',
    ];
    for (const sel of overlaySelectors) {
        try {
            document.querySelectorAll(sel).forEach(el => {
                // Only remove if it's covering the viewport
                const rect = el.getBoundingClientRect();
                if (rect.width > window.innerWidth * 0.5 && rect.height > window.innerHeight * 0.3) {
                    el.remove();
                }
            });
        } catch (_) {}
    }
    // Re-enable scrolling (some popups lock body scroll)
    try {
        document.body.style.overflow = 'auto';
        document.documentElement.style.overflow = 'auto';
    } catch (_) {}
    await new Promise(r => setTimeout(r, 500));
})();
"""

# URL sub-strings that signal navigation / non-article pages.
# share-price-\d+ catches BS ticker pages like /markets/suzlon-energy-ltd-share-price-13872.html
_SKIP_URL_RE = re.compile(
    r"/(page|tag|author|category|search|login|subscribe|newsletters?|topic|calculator|"
    r"tools?|widget|video|podcast|gallery|photo|slideshow)(/|$)"
    r"|share-price-\d+"
    r"|/calculator",
    re.IGNORECASE,
)

# URL sub-strings that strongly suggest an article page.
# /\d{5,} catches Financial Express & MoneyControl numeric article IDs like /3401234/
_ARTICLE_URL_RE = re.compile(
    r"(/\d{4}/\d{2}/|/article|/story|/news/|\.html?$|/\d{5,}/?$)",
    re.IGNORECASE,
)

_MIN_TITLE_LEN = 20


class ArticleLink(BaseModel):
    url: str
    title: str
    source_name: str


def _looks_like_article(href: str, text: str) -> bool:
    if _SKIP_URL_RE.search(href):
        return False
    if len(text.strip()) < _MIN_TITLE_LEN:
        return False
    if not _ARTICLE_URL_RE.search(href):
        return False
    return True


async def _scrape_with_browser(
    section_url: str, site_name: str, browser: Browser, timeout_ms: int
) -> list[ArticleLink]:
    parsed_base = urlparse(section_url)
    base_netloc = parsed_base.netloc.lower()

    context = await browser.new_context(user_agent=USER_AGENT)
    page = await context.new_page()
    try:
        await page.goto(section_url, wait_until="domcontentloaded", timeout=timeout_ms)
        # Dismiss cookie banners, login modals, subscription overlays
        try:
            await page.evaluate(_DISMISS_POPUPS_JS)
        except Exception:
            pass
        raw_links: list[dict] = await page.evaluate("""
            () => Array.from(document.querySelectorAll('a[href]')).map(a => ({
                href: a.href,
                text: (a.innerText || a.textContent || a.title || '').trim()
            }))
        """)
    except Exception as exc:
        logger.warning("scrape_homepage failed",
                       extra={"site": site_name, "url": section_url, "error": str(exc)})
        await context.close()
        return []
    finally:
        await context.close()

    seen: set[str] = set()
    links: list[ArticleLink] = []

    for item in raw_links:
        href: str = item.get("href", "") or ""
        text: str = item.get("text", "") or ""

        if not href.startswith("http"):
            continue

        link_netloc = urlparse(href).netloc.lower()
        # Keep same domain and subdomains, drop unrelated external links
        if not (link_netloc == base_netloc or link_netloc.endswith("." + base_netloc)):
            continue

        # Skip brandstories / special-initiatives — not editorial
        if any(s in link_netloc for s in ("brandstories.", "special-initiatives.")):
            continue

        if href in seen:
            continue
        seen.add(href)

        if _looks_like_article(href, text):
            links.append(ArticleLink(url=href, title=text, source_name=site_name))

    logger.info("scrape_homepage complete",
                extra={"site": site_name, "found": len(links)})
    return links


async def scrape_homepage(
    section_url: str,
    site_name: str,
    *,
    timeout_ms: int = 30_000,
    browser: Optional[Browser] = None,
) -> list[ArticleLink]:
    """
    Fetch a section page and extract article links.
    Pass `browser` to reuse an existing Playwright browser process.
    Returns an empty list (never raises) on any failure.
    """
    if browser is not None:
        return await _scrape_with_browser(section_url, site_name, browser, timeout_ms)

    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(
                channel=BROWSER_CHANNEL, headless=True, args=BROWSER_ARGS
            )
            try:
                return await _scrape_with_browser(section_url, site_name, b, timeout_ms)
            finally:
                await b.close()
    except Exception as exc:
        logger.warning("scrape_homepage: browser launch failed",
                       extra={"site": site_name, "url": section_url, "error": str(exc)})
        return []
