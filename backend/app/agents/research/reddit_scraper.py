"""
Reddit subreddit scraper — handles both link posts and text posts.

Link posts:  returns the external URL → research task fetches the article normally
Text posts:  returns the post body as content directly → skips fetch_article

No authentication required. Uses Reddit's public JSON API.

Relevant subreddits for Indian finance:
    r/IndiaInvestments     — most active, high quality discussion
    r/IndianStockMarket    — stocks, IPOs, earnings
    r/personalfinanceindia — SIPs, tax, insurance, retirement
    r/IndiaFinance         — general finance news

Usage:
    results = await scrape_reddit("IndiaInvestments", "Reddit r/IndiaInvestments")
    for item in results:
        if item.selftext:
            # Text post — content already available, skip fetch_article
            full_text = item.selftext
        else:
            # Link post — fetch the external article
            content = await fetch_article(item.url)
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Reddit identifies bots by User-Agent. Use a descriptive string.
_USER_AGENT = "ContentAutomation/1.0 IndianFinanceResearch (educational use)"
_HEADERS = {"User-Agent": _USER_AGENT}

# Domains worth following for link posts
_NEWS_DOMAINS = {
    "economictimes.indiatimes.com",
    "livemint.com",
    "business-standard.com",
    "financialexpress.com",
    "moneycontrol.com",
    "cnbctv18.com",
    "ndtvprofit.com",
    "thehindubusinessline.com",
    "thehindu.com",
    "bqprime.com",
    "reuters.com",
    "bloomberg.com",
    "ft.com",
    "zeebiz.com",
}

# Minimum upvotes — filters out low-engagement / spam posts
_MIN_SCORE = 5

# Minimum characters for a text post body to be worth processing
_MIN_SELFTEXT_CHARS = 200

# Keywords that indicate spam, abuse, or off-topic content — skip posts with these in the title
_SPAM_TITLE_KEYWORDS = {
    "porn", "nsfw", "sex", "nude", "onlyfans", "escort",
    "casino", "bet ", "betting", "gamble", "gambling", "lottery",
    "mlm", "pyramid", "referral code", "join my",
    "dm me", "telegram group", "whatsapp group",
    "100x", "1000x", "moonshot", "guaranteed returns", "guaranteed profit",
    "get rich", "make money fast", "passive income scheme",
    "crypto pump", "altcoin", "shitcoin", "presale",
    "astrology", "numerology", "vastu",
}

# Reddit post flair tags that indicate off-topic posts
_SKIP_FLAIR = {
    "meme", "memes", "humor", "humour", "off-topic",
    "rant", "venting", "satire",
}


class RedditPost(BaseModel):
    """
    Represents one Reddit post.

    For link posts:  url = external article URL, selftext = None
    For text posts:  url = Reddit post permalink, selftext = full post body
    """
    url: str
    title: str
    source_name: str
    score: int
    selftext: str | None = None          # None → link post; str → text post
    num_comments: int = 0
    subreddit: str = ""
    reddit_url: str = ""                  # always the reddit.com/r/... URL


def _is_news_domain(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
        return any(host == d or host.endswith("." + d) for d in _NEWS_DOMAINS)
    except Exception:
        return False


def _clean_selftext(text: str) -> str:
    """Strip Reddit formatting artifacts from post body."""
    # Remove markdown links [text](url) → keep just the text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove standalone URLs
    text = re.sub(r"https?://\S+", "", text)
    # Collapse excess whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def scrape_reddit(
    subreddit: str,
    site_name: str,
    *,
    sort: str = "hot",
    limit: int = 25,
    time_filter: str = "day",
    min_score: int = _MIN_SCORE,
    include_text_posts: bool = True,
    include_link_posts: bool = True,
    any_domain: bool = False,
) -> list[RedditPost]:
    """
    Fetch posts from a subreddit and return both link and text posts.

    Args:
        subreddit:           Subreddit name without r/ prefix
        site_name:           Label used for logging and source_name field
        sort:                hot | new | top | rising
        limit:               Max posts to fetch (Reddit hard max = 100)
        time_filter:         For sort=top: hour | day | week | month | year | all
        min_score:           Skip posts with fewer upvotes
        include_text_posts:  Include self/text posts (post body as content)
        include_link_posts:  Include link posts (external article URLs)
        any_domain:          Accept link posts from any domain, not just news sites

    Returns empty list on any failure — never raises.
    """
    params: dict = {"limit": min(limit, 100), "raw_json": 1}
    if sort == "top":
        params["t"] = time_filter

    api_url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"

    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, follow_redirects=True, timeout=15
        ) as client:
            resp = await client.get(api_url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning(
            "scrape_reddit: fetch failed",
            extra={"subreddit": subreddit, "error": str(exc)},
        )
        return []

    posts = data.get("data", {}).get("children", [])
    results: list[RedditPost] = []
    seen_urls: set[str] = set()

    for post in posts:
        pd = post.get("data", {})

        if pd.get("stickied", False):
            continue

        # Skip NSFW posts
        if pd.get("over_18", False):
            continue

        score = pd.get("score", 0)
        if score < min_score:
            continue

        title: str = (pd.get("title") or "").strip()
        if not title or len(title) < 15:
            continue

        # Skip posts whose title contains spam/abuse keywords
        title_lower = title.lower()
        if any(kw in title_lower for kw in _SPAM_TITLE_KEYWORDS):
            continue

        # Skip off-topic flair
        flair: str = (pd.get("link_flair_text") or "").lower()
        if any(f in flair for f in _SKIP_FLAIR):
            continue

        is_self: bool = pd.get("is_self", False)
        permalink: str = "https://www.reddit.com" + pd.get("permalink", "")

        if is_self and include_text_posts:
            # ── Text post ──────────────────────────────────────────────────
            raw_body: str = (pd.get("selftext") or "").strip()

            # Reddit marks deleted/removed posts with these placeholder strings
            if raw_body in ("[deleted]", "[removed]", ""):
                continue

            body = _clean_selftext(raw_body)
            if len(body) < _MIN_SELFTEXT_CHARS:
                continue

            if permalink in seen_urls:
                continue
            seen_urls.add(permalink)

            results.append(RedditPost(
                url=permalink,
                title=title,
                source_name=site_name,
                score=score,
                selftext=body,
                num_comments=pd.get("num_comments", 0),
                subreddit=subreddit,
                reddit_url=permalink,
            ))

        elif not is_self and include_link_posts:
            # ── Link post ──────────────────────────────────────────────────
            ext_url: str = pd.get("url", "")
            if not ext_url:
                continue

            if not any_domain and not _is_news_domain(ext_url):
                continue

            if ext_url in seen_urls:
                continue
            seen_urls.add(ext_url)

            results.append(RedditPost(
                url=ext_url,
                title=title,
                source_name=site_name,
                score=score,
                selftext=None,
                num_comments=pd.get("num_comments", 0),
                subreddit=subreddit,
                reddit_url=permalink,
            ))

    logger.info(
        "scrape_reddit complete",
        extra={
            "subreddit": subreddit,
            "posts_checked": len(posts),
            "returned": len(results),
            "text_posts": sum(1 for r in results if r.selftext),
            "link_posts": sum(1 for r in results if not r.selftext),
        },
    )
    return results
