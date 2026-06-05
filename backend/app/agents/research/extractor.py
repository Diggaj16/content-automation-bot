"""
Article extractor: fetches a single article URL, extracts full text and metadata.

Strategy (fastest-first):
  1. Plain HTTP (httpx) — works for Livemint, ET, MoneyControl etc. ~1-2s per article.
  2. Browser fallback (Playwright/Edge) — for JS-rendered sites like Business Standard.
     Accepts an optional shared Browser to avoid per-call launch overhead.

Also provides normalize_url() used by the dedup checker.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser
from pydantic import BaseModel

from app.utils.logging import get_logger

logger = get_logger(__name__)

import os

# On Windows set PLAYWRIGHT_BROWSER_CHANNEL=msedge in .env to use installed Edge.
# In Docker leave unset — Playwright's bundled Chromium is used automatically.
BROWSER_CHANNEL: str | None = os.environ.get("PLAYWRIGHT_BROWSER_CHANNEL") or None

BROWSER_ARGS = ["--no-proxy-server", "--disable-ipv6", "--disable-blink-features=AutomationControlled"]
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
)
_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
}

# CSS selectors tried in order — first one with ≥100 words wins.
_CONTENT_SELECTORS = [
    "article",
    "[class*='article-body']",
    "[class*='articleBody']",
    "[class*='story-body']",
    "[class*='storyBody']",
    "[class*='article-content']",
    "[class*='articleContent']",
    "[class*='story-content']",
    "[class*='post-content']",
    "[class*='entry-content']",
    "[itemprop='articleBody']",
    "main",
    "[role='main']",
    "#content",
    "#main",
    ".content",
]

_EXPAND_JS = """
(async () => {
    // Dismiss overlays/popups before extracting content
    const dismissSels = [
        '#onetrust-accept-btn-handler', '.onetrust-close-btn-handler',
        'button[id*="accept"]', 'button[class*="cookie"]',
        '.login_close_btn', '#mc_login .icon-close', '.modal .close',
        '.popup-close', '[data-dismiss="modal"]', '#close_button',
    ];
    for (const sel of dismissSels) {
        try { document.querySelectorAll(sel).forEach(el => { if (el.offsetParent) el.click(); }); }
        catch (_) {}
    }
    // Force-remove large overlays covering the viewport
    const overlaySels = ['.modal-backdrop','.overlay','[class*="popup"]','[class*="modal"]','.subscription-wall'];
    for (const sel of overlaySels) {
        try {
            document.querySelectorAll(sel).forEach(el => {
                const r = el.getBoundingClientRect();
                if (r.width > window.innerWidth * 0.5 && r.height > window.innerHeight * 0.3) el.remove();
            });
        } catch (_) {}
    }
    try { document.body.style.overflow = 'auto'; } catch (_) {}

    // Expand truncated content
    const expandSels = [
        'button[class*="read-more"]','button[class*="readmore"]',
        'button[class*="show-more"]','a[class*="read-more"]',
        '[data-testid*="read-more"]','[aria-label*="Read more"]',
    ];
    for (const sel of expandSels) {
        try { document.querySelectorAll(sel).forEach(el => { if (el.offsetParent) el.click(); }); }
        catch (_) {}
    }
    window.scrollTo(0, document.body.scrollHeight / 2);
    await new Promise(r => setTimeout(r, 300));
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise(r => setTimeout(r, 300));
})();
"""

_TRACKING_PARAMS: frozenset[str] = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "referrer", "source", "fbclid", "gclid", "_ga", "mc_cid", "mc_eid",
})

# Threshold for "good" content — below this we try the browser fallback.
_HTTP_WORD_THRESHOLD = 200
# Final paywall threshold — below this even after browser we give up.
_PAYWALL_WORD_THRESHOLD = 80


class ArticleContent(BaseModel):
    url: str
    normalized_url: str
    title: str
    full_text: str
    word_count: int
    paywall_detected: bool
    publication_date: Optional[datetime] = None


def normalize_url(url: str) -> str:
    """Canonical URL: lowercase host, no fragment, no tracking params."""
    parsed = urlparse(url)
    clean_params = {
        k: v for k, v in parse_qs(parsed.query, keep_blank_values=False).items()
        if k.lower() not in _TRACKING_PARAMS
    }
    clean_query = urlencode(sorted(clean_params.items()), doseq=True)
    clean_path = parsed.path.rstrip("/") or "/"
    return urlunparse((
        parsed.scheme.lower(), parsed.netloc.lower(),
        clean_path, parsed.params, clean_query, "",
    ))


def _extract_from_html(html: str) -> tuple[str, str, str]:
    """
    Parse raw HTML with BeautifulSoup.
    Returns (full_text, title, raw_date_str).
    """
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title = ""
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = og["content"].strip()
    if not title and soup.title:
        title = soup.title.get_text(strip=True)

    # Publication date
    raw_date = ""
    for attr, key in [
        ({"property": "article:published_time"}, "content"),
        ({"name": "datePublished"}, "content"),
        ({"itemprop": "datePublished"}, "content"),
    ]:
        tag = soup.find("meta", attr)
        if tag and tag.get(key):
            raw_date = tag[key]
            break
    if not raw_date:
        time_tag = soup.find("time", attrs={"datetime": True})
        if time_tag:
            raw_date = time_tag["datetime"]

    # Content — try specific selectors first
    full_text = ""
    for sel in _CONTENT_SELECTORS:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(separator=" ", strip=True)
            if len(text.split()) > 80:
                full_text = text
                break

    # Fallback: strip chrome from body
    if not full_text and soup.body:
        for tag in soup.body.find_all(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        full_text = soup.body.get_text(separator=" ", strip=True)

    full_text = re.sub(r"\s{3,}", "  ", full_text).strip()
    return full_text, title, raw_date


async def _fetch_via_http(url: str, timeout_s: float = 12.0) -> tuple[str, str, str]:
    """
    Fetch page HTML with httpx. Returns (full_text, title, raw_date).
    Raises on failure so the caller can fall back to browser.
    """
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout_s,
        headers=_HEADERS,
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return _extract_from_html(resp.text)


async def _fetch_via_browser(
    url: str, timeout_ms: int, browser: Optional[Browser]
) -> tuple[str, str, str]:
    """
    Fetch page via Playwright. Creates its own browser if none is provided.
    Returns (full_text, title, raw_date).
    """
    _own_pw = browser is None

    async def _run(b: Browser) -> tuple[str, str, str]:
        context = await b.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                await page.evaluate(_EXPAND_JS)
            except Exception:
                pass
            html = await page.content()
            return _extract_from_html(html)
        finally:
            await context.close()

    if not _own_pw:
        return await _run(browser)

    async with async_playwright() as p:
        b = await p.chromium.launch(channel=BROWSER_CHANNEL, headless=True, args=BROWSER_ARGS)
        try:
            return await _run(b)
        finally:
            await b.close()


async def fetch_article(
    url: str,
    *,
    timeout_ms: int = 30_000,
    browser: Optional[Browser] = None,
) -> ArticleContent:
    """
    Fetch and extract a single article. Never raises.

    Tries plain HTTP first (fast, ~1-2s). Falls back to Playwright browser
    if HTTP returns thin content (<200 words, e.g. JS-rendered sites).

    Pass `browser` to reuse an existing Playwright Browser for the fallback
    path (avoids launching a new Edge process).
    """
    normalized = normalize_url(url)
    _fail = ArticleContent(
        url=url, normalized_url=normalized,
        title="", full_text="", word_count=0, paywall_detected=True,
    )

    full_text, title, raw_date = "", "", ""
    used_browser = False

    # --- Step 1: plain HTTP ---
    try:
        full_text, title, raw_date = await _fetch_via_http(url, timeout_s=12.0)
    except Exception as exc:
        logger.info("fetch_article: HTTP failed, trying browser",
                    extra={"url": url, "error": str(exc)})

    # --- Step 2: browser fallback if HTTP content is thin ---
    if len(full_text.split()) < _HTTP_WORD_THRESHOLD:
        used_browser = True
        try:
            full_text, title, raw_date = await _fetch_via_browser(url, timeout_ms, browser)
        except Exception as exc:
            logger.warning("fetch_article: browser fallback failed",
                           extra={"url": url, "error": str(exc)})
            if not full_text:
                return _fail

    word_count = len(full_text.split())
    paywall_detected = word_count < _PAYWALL_WORD_THRESHOLD

    pub_date: Optional[datetime] = None
    if raw_date:
        try:
            pub_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    logger.info("fetch_article complete",
                extra={"url": url, "words": word_count,
                       "paywall": paywall_detected, "browser_used": used_browser})
    return ArticleContent(
        url=url, normalized_url=normalized,
        title=title, full_text=full_text,
        word_count=word_count, paywall_detected=paywall_detected,
        publication_date=pub_date,
    )
