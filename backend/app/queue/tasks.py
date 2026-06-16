"""
Stub arq task functions — one per agent.
Each agent plan replaces its stub with the real implementation.
"""
import asyncio

from anthropic import Anthropic, AsyncAnthropic
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Max simultaneous article fetches PER SITE — keep low: each fetch launches an
# Edge process; too many at once (7 sites × 3 = 21 browsers) starves the machine
# and pushes 4-second fetches past the 60s hard timeout.
_ARTICLE_CONCURRENCY = 1

# Hard per-article timeout — generous because Edge under load is slow to start.
_ARTICLE_FETCH_TIMEOUT = 90

# NOTE: _GLOBAL_FETCH_SEM is created inside research_agent_task (not here) because
# asyncio.Semaphore created outside a running event loop is broken in Python 3.10+.

# URL path patterns that are genuine non-article pages — skip without fetching.
# Only list actual tool/data pages here — editorial sections are fair game.
_NON_ARTICLE_PATH_PREFIXES = (
    # Livemint data/tool pages (not editorial)
    "/market/market-stats/",
    "/market-stats/",
    "/tools-calculators/",
    "/loans/",
    "/topic/",
    # Business Standard index/data pages
    "/markets/nse-nifty-indices-",
    "/markets/bse-sensex-indices-",
    "/markets/nse-nifty-midcap",
    "/markets/bse-",
    "/markets/nse-",
    "/finance/personal-finance/retirement-calculator",
    "/finance/personal-finance/home-loan-calculator",
    "/finance/personal-finance/education-loan-calculator",
    "/finance/personal-finance/net-worth-calculator",
    "/finance/personal-finance/crorepati-calculator",
    "/finance/personal-finance/marriage-plan-calculator",
    # Generic non-article paths
    "/webinars/",
    "/crossword",
    "/education/calculators",
    "/personal-finance/net-worth-calculator",
    "/personal-finance/retirement-calculator",
    "/personal-finance/home-loan-calculator",
    "/personal-finance/education-loan-calculator",
    "/investor-communication",
)


async def research_agent_task(
    ctx: dict,
    topic: str | None = None,
    url: str | None = None,
) -> dict:
    """
    Research agent — discovers and extracts articles from curated sites.
    Triggered: daily cron at 6 AM IST, or on-demand by orchestrator.
    Args:
        topic: Optional topic hint for targeted research (e.g. "SEBI announcement")
        url:   Optional specific URL to fast-track (e.g. breaking news)
    """
    import time
    from playwright.async_api import async_playwright
    from app.agents.research.extractor import BROWSER_ARGS, BROWSER_CHANNEL, fetch_article, normalize_url
    from app.agents.research.scraper import scrape_homepage
    from app.agents.research.reddit_scraper import scrape_reddit
    from app.agents.research.filters import is_url_seen, is_article_fresh, is_article_long_enough
    from app.agents.research.prescorer import async_pre_score_headlines
    from app.agents.research.summariser import async_summarise_article
    from app.agents.research.db_writer import (
        upsert_raw_content, record_site_success, record_site_failure, upsert_cost_log,
    )
    from app.utils.slack import send_slack_alert
    from app.utils.logging import format_token_cost, log_agent_decision
    from app.db.models import CuratedSite, RunLogCreate, TriggerType

    settings = ctx["settings"]
    supabase = ctx["supabase"]
    start_time = time.time()

    anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    # One shared browser for the whole run — pages are cheap, browser launches are not.
    # Each fetch creates a new context (isolated cookies/storage) then closes it.
    _pw = await async_playwright().start()   # .start() is the correct non-context-manager API
    _browser = await _pw.chromium.launch(
        channel=BROWSER_CHANNEL, headless=True, args=BROWSER_ARGS
    )

    # Semaphore limits concurrent page opens to avoid memory pressure.
    _global_fetch_sem = asyncio.Semaphore(3)
    # Serialise Supabase batch-dedup calls so 7 parallel sites don't exhaust the connection pool.
    _dedup_sem = asyncio.Semaphore(2)
    # No semaphore for pre-score: the prescorer's own retry+backoff handles rate
    # limits. A semaphore here would hold while sleeping, blocking all other sites.

    processed_count = 0
    success_count = 0
    failure_count = 0
    skipped_count = 0   # articles skipped for legitimate reasons (duplicate, stale, short, low-score)
    errors: list[dict] = []
    trace_entries: list[str] = []

    # Separate token tracking per model for accurate cost calculation
    haiku_in = haiku_out = 0
    sonnet_in = sonnet_out = 0

    _lock = asyncio.Lock()

    # Fetch all active sites
    try:
        sites_resp = supabase.table("curated_sites").select("*").eq("active", True).execute()
        sites = [CuratedSite(**s) for s in sites_resp.data]
    except Exception as exc:
        logger.error(f"research_agent_task: failed to fetch curated_sites | err={exc}")
        return {
            "status": "error",
            "processed": 0,
            "success": 0,
            "failures": 0,
            "duration_seconds": round(time.time() - start_time, 2),
            "cost_usd": 0.0,
            "error": str(exc),
        }
    logger.info(f"research_agent_task: {len(sites)} active sites to process")

    async def _process_site(site) -> None:
        nonlocal processed_count, success_count, failure_count, skipped_count
        nonlocal haiku_in, haiku_out, sonnet_in, sonnet_out
        try:
            # Step 1 — Scrape section page.
            # Reddit subreddits use the JSON API (no browser needed).
            # Everything else uses the Playwright browser scraper.
            if "reddit.com/r/" in site.section_url:
                import re as _re
                _sub = _re.search(r"reddit\.com/r/([^/?#]+)", site.section_url)
                sub_name = _sub.group(1) if _sub else "IndiaInvestments"
                links = await scrape_reddit(sub_name, site.site_name)
            else:
                links = await scrape_homepage(site.section_url, site.site_name, browser=_browser)
            if not links:
                await asyncio.to_thread(
                    record_site_failure, supabase, site.id,
                    "No links extracted", settings.site_failure_pause_threshold
                )
                async with _lock:
                    failure_count += 1
                return

            # Step 2 — Batch pre-score.
            # Retry + backoff is handled inside async_pre_score_headlines.
            titles = [lnk.title for lnk in links]
            pre_result = await async_pre_score_headlines(
                titles, anthropic_client, settings.claude_model_light
            )
            async with _lock:
                haiku_in += pre_result.input_tokens
                haiku_out += pre_result.output_tokens

            if len(pre_result.scores) != len(links):
                logger.warning(
                    f"pre_score count mismatch: {len(links)} links vs {len(pre_result.scores)} scores"
                )

            # Step 3 — Filter: pre-score threshold + skip known non-article URL patterns.
            # If pre-scoring failed entirely, skip the threshold gate so downstream
            # filters (freshness, length, dedup) still have a chance to run.
            from urllib.parse import urlparse as _up
            if pre_result.failed:
                score_filtered = [
                    (link, 0.0)
                    for link in links
                    if not any(
                        _up(link.url).path.startswith(p)
                        for p in _NON_ARTICLE_PATH_PREFIXES
                    )
                ]
                low_score_count = 0
            else:
                score_filtered = [
                    (link, score)
                    for link, score in zip(links, pre_result.scores)
                    if score >= site.pre_score_threshold
                    and not any(
                        _up(link.url).path.startswith(p)
                        for p in _NON_ARTICLE_PATH_PREFIXES
                    )
                ]
                low_score_count = len(links) - len(score_filtered)

            logger.info(
                f"research: site={site.site_name} scraped={len(links)} "
                f"pre_score_pass={len(score_filtered)} dropped_low_score={low_score_count} "
                f"threshold={site.pre_score_threshold} prescore_failed={pre_result.failed}"
            )
            async with _lock:
                skipped_count += low_score_count

            if score_filtered:
                # Batch dedup — serialised to 2 concurrent calls to avoid exhausting Supabase pool
                norm_map = {normalize_url(l.url): (l, s) for l, s in score_filtered}
                try:
                    async with _dedup_sem:
                        seen_resp = await asyncio.to_thread(
                            lambda: supabase.table("raw_content")
                            .select("normalized_url")
                            .in_("normalized_url", list(norm_map.keys()))
                            .execute()
                        )
                        seen_set = {r["normalized_url"] for r in (seen_resp.data or [])}
                except Exception as dedup_exc:
                    logger.warning("research: batch dedup failed, assuming all unseen",
                                   extra={"error": str(dedup_exc)})
                    seen_set = set()

                to_fetch = [
                    (l, s, norm)
                    for norm, (l, s) in norm_map.items()
                    if norm not in seen_set
                ]
                async with _lock:
                    skipped_count += len(norm_map) - len(to_fetch)

                # cap per-site to avoid timeout
                cap = settings.articles_per_site
                if len(to_fetch) > cap:
                    pre_cap_count = len(to_fetch)
                    to_fetch = sorted(to_fetch, key=lambda x: x[1], reverse=True)[:cap]
                    async with _lock:
                        skipped_count += pre_cap_count - cap
            else:
                to_fetch = []

            # Step 3b — Fetch articles in parallel.
            # Reddit text posts already contain their content — no browser fetch needed.
            # Link posts (Reddit or regular) go through fetch_article as normal.
            from app.agents.research.extractor import ArticleContent as _AC
            _site_sem = asyncio.Semaphore(_ARTICLE_CONCURRENCY)

            async def _fetch(link):
                # Reddit text post — content is already in the post body
                if hasattr(link, "selftext") and link.selftext:
                    return _AC(
                        url=link.url,
                        normalized_url=normalize_url(link.url),
                        title=link.title,
                        full_text=link.selftext,
                        word_count=len(link.selftext.split()),
                        paywall_detected=False,
                        publication_date=None,
                    )
                # Regular article or Reddit link post — fetch from the URL
                async with _global_fetch_sem:
                    async with _site_sem:
                        try:
                            return await asyncio.wait_for(
                                fetch_article(link.url),
                                timeout=_ARTICLE_FETCH_TIMEOUT,
                            )
                        except asyncio.TimeoutError:
                            logger.warning(
                                f"research: article fetch hard-timeout ({_ARTICLE_FETCH_TIMEOUT}s) | url={link.url}"
                            )
                            raise

            fetch_results = await asyncio.gather(
                *[_fetch(link) for link, _, _ in to_fetch],
                return_exceptions=True,
            )

            for (link, score, _norm), content_or_exc in zip(to_fetch, fetch_results):
                async with _lock:
                    processed_count += 1
                try:
                    if isinstance(content_or_exc, Exception):
                        logger.warning("research_agent_task: article fetch error",
                                       extra={"url": link.url, "error": str(content_or_exc)})
                        async with _lock:
                            failure_count += 1
                            errors.append({"url": link.url, "error": str(content_or_exc)})
                        continue

                    content = content_or_exc

                    if content.paywall_detected:
                        trace_entries.append(log_agent_decision(
                            logger, "skip_paywall", "Paywall or thin content",
                            {"url": link.url, "word_count": content.word_count},
                        ))
                        async with _lock:
                            skipped_count += 1
                        continue

                    if not is_article_fresh(content.publication_date, settings.article_max_age_days):
                        async with _lock:
                            skipped_count += 1
                        continue

                    if not is_article_long_enough(content.word_count, settings.article_min_words):
                        async with _lock:
                            skipped_count += 1
                        continue

                    # Step 4 — Async summarisation (non-blocking)
                    sum_result = await async_summarise_article(
                        content.full_text, content.title, anthropic_client, settings.claude_model_heavy,
                    )
                    async with _lock:
                        sonnet_in += sum_result.input_tokens
                        sonnet_out += sum_result.output_tokens

                    # Step 5 — Write to DB (wrap sync call in thread)
                    article_id = await asyncio.to_thread(
                        upsert_raw_content, supabase, content, sum_result.summary, score,
                        source_name=site.site_name,
                    )
                    if article_id:
                        async with _lock:
                            success_count += 1
                        trace_entries.append(log_agent_decision(
                            logger, "store_article", "Stored successfully",
                            {"id": article_id, "url": link.url, "score": score},
                        ))
                    else:
                        async with _lock:
                            failure_count += 1
                        trace_entries.append(log_agent_decision(
                            logger, "store_failed", "upsert_raw_content returned None",
                            {"url": link.url, "score": score},
                        ))

                except Exception as article_exc:
                    logger.warning(
                        f"research_agent_task: article error | url={link.url} | err={article_exc}"
                    )
                    async with _lock:
                        failure_count += 1

            await asyncio.to_thread(record_site_success, supabase, site.id)

        except Exception as exc:
            logger.error(f"research_agent_task: site error | site={site.site_name} | err={exc}")
            async with _lock:
                errors.append({"site": site.site_name, "error": str(exc)})
                failure_count += 1
            await asyncio.to_thread(
                record_site_failure, supabase, site.id, str(exc), settings.site_failure_pause_threshold
            )

    try:
        await asyncio.gather(*[_process_site(site) for site in sites])
    finally:
        try:
            await _browser.close()
        except Exception:
            pass
        try:
            await _pw.stop()
        except Exception:
            pass

    duration = time.time() - start_time

    # Build cost breakdown
    haiku_cost = format_token_cost(haiku_in, haiku_out, settings.claude_model_light)
    sonnet_cost = format_token_cost(sonnet_in, sonnet_out, settings.claude_model_heavy)
    total_usd = haiku_cost["estimated_usd"] + sonnet_cost["estimated_usd"]
    total_tokens = haiku_in + haiku_out + sonnet_in + sonnet_out
    token_cost_dict = {
        "haiku": haiku_cost,
        "sonnet": sonnet_cost,
        "total_usd": round(total_usd, 6),
    }

    # Accumulate daily cost
    await asyncio.to_thread(upsert_cost_log, supabase, "research_agent", total_usd=total_usd, token_count=total_tokens)

    # Write run_log
    trigger = TriggerType.CRON if (topic is None and url is None) else TriggerType.MANUAL
    run_log = RunLogCreate(
        agent_name="research_agent",
        trigger_type=trigger,
        processed_count=processed_count,
        success_count=success_count,
        failure_count=failure_count,
        duration_seconds=round(duration, 2),
        reasoning_trace="\n".join(trace_entries) if trace_entries else None,
        errors=errors,
        token_cost=token_cost_dict,
    )
    try:
        await asyncio.to_thread(lambda: supabase.table("run_logs").insert(run_log.model_dump()).execute())
    except Exception as exc:
        logger.error(f"research_agent_task: failed to write run_log | err={exc}")

    # Cost alert
    if settings.slack_webhook_url and total_usd >= settings.daily_cost_alert_usd:
        send_slack_alert(
            settings.slack_webhook_url,
            f"Research agent cost alert: ${total_usd:.4f} in this run "
            f"(threshold: ${settings.daily_cost_alert_usd})",
        )

    logger.info(
        f"research_agent_task done | processed={processed_count} "
        f"success={success_count} skipped={skipped_count} failures={failure_count} "
        f"duration={duration:.1f}s cost=${total_usd:.4f}"
    )

    # Auto-chain to scoring agent (target the scoring queue)
    arq_pool = ctx.get("redis")
    if arq_pool is not None:
        try:
            await arq_pool.enqueue_job("scoring_agent_task", _queue_name="arq:scoring")
            logger.info("research_agent_task: chained to scoring_agent_task")
        except Exception as exc:
            logger.warning(f"research_agent_task: failed to chain scoring | err={exc}")

    return {
        "status": "done",
        "processed": processed_count,
        "success": success_count,
        "skipped": skipped_count,    # duplicates + paywalls + stale + too-short + low-score
        "failures": failure_count,   # only real errors (DB write failed, exception, etc.)
        "duration_seconds": round(duration, 2),
        "cost_usd": round(total_usd, 6),
    }


async def scoring_agent_task(ctx: dict) -> dict:
    """
    Scoring agent — generates content ideas from unprocessed raw_content articles.
    Triggered: by event after research_agent_task completes.
    """
    import time
    from anthropic import Anthropic
    from app.agents.scoring.embedder import embed_text
    from app.agents.scoring.coverage_checker import check_recent_coverage
    from app.agents.scoring.idea_generator import generate_ideas
    from app.agents.scoring.db_writer import write_ideas, mark_article_processed, upsert_cost_log
    from app.utils.slack import send_slack_alert
    from app.utils.logging import format_token_cost, log_agent_decision
    from app.db.models import RawContent, IdeaCreate, RunLogCreate, TriggerType

    settings = ctx["settings"]
    supabase = ctx["supabase"]
    start_time = time.time()

    anthropic_client = Anthropic(api_key=settings.anthropic_api_key)

    from app.agents.embedding.client import make_embed_client
    embed_client = make_embed_client(
        google_api_key=settings.google_api_key,
        local_model=settings.local_embedding_model,
    )

    processed_count = 0
    ideas_created_count = 0
    failure_count = 0
    errors: list[dict] = []
    trace_entries: list[str] = []
    sonnet_in = sonnet_out = 0

    try:
        resp = supabase.table("raw_content").select("*").eq("processed", False).limit(50).execute()
        articles = [RawContent(**r) for r in resp.data]
    except Exception as exc:
        logger.error(f"scoring_agent_task: failed to fetch raw_content | err={exc}")
        return {
            "status": "error",
            "processed": 0,
            "ideas_created": 0,
            "failures": 0,
            "duration_seconds": round(time.time() - start_time, 2),
            "cost_usd": 0.0,
            "error": str(exc),
        }

    logger.info(f"scoring_agent_task: {len(articles)} unprocessed articles")

    # Fetch the latest rejection-pattern summary so the idea generator avoids
    # angles the user has already rejected.
    rejection_summary = ""
    try:
        _ds = (
            supabase.table("user_decision_summaries")
            .select("summary_text")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if _ds.data:
            rejection_summary = _ds.data[0]["summary_text"]
    except Exception:
        pass  # non-fatal — scoring proceeds without the summary

    max_ideas_per_site = settings.max_ideas_per_site
    site_idea_counts: dict[str, int] = {}

    for article in articles:
        processed_count += 1

        site_key = article.source_name
        if site_idea_counts.get(site_key, 0) >= max_ideas_per_site:
            trace_entries.append(log_agent_decision(
                logger, "skip_site_cap", f"Site '{site_key}' already has {max_ideas_per_site} ideas this run",
                {"article_id": str(article.id), "title": article.title},
            ))
            mark_article_processed(supabase, article.id)
            continue

        try:
            embed_input = (
                f"{article.title}. "
                f"{article.structured_summary.story_narrative if article.structured_summary else ''}"
            )
            embedding: list[float] = embed_text(embed_input, embed_client)

            idea_result = generate_ideas(article, anthropic_client, settings.claude_model_heavy, rejection_summary=rejection_summary)
            sonnet_in += idea_result.input_tokens
            sonnet_out += idea_result.output_tokens

            if not idea_result.ideas:
                trace_entries.append(log_agent_decision(
                    logger, "no_ideas", "generate_ideas returned empty list",
                    {"article_id": str(article.id), "title": article.title},
                ))
                mark_article_processed(supabase, article.id)
                continue

            remaining = max_ideas_per_site - site_idea_counts.get(site_key, 0)
            capped_ideas = idea_result.ideas[:remaining]

            final_ideas: list[IdeaCreate] = []
            for idea in capped_ideas:
                is_covered = check_recent_coverage(embedding, idea.platform.value, supabase)
                final_ideas.append(IdeaCreate(**{
                    **idea.model_dump(),
                    "recent_coverage_flag": is_covered,
                    "source_article_id":    article.id,
                    "source_article_date":  article.publication_date,
                }))

            created_ids = write_ideas(supabase, final_ideas, article.id, article.publication_date)
            ideas_created_count += len(created_ids)
            site_idea_counts[site_key] = site_idea_counts.get(site_key, 0) + len(created_ids)

            if len(created_ids) < len(final_ideas):
                failure_count += len(final_ideas) - len(created_ids)

            trace_entries.append(log_agent_decision(
                logger, "ideas_written", f"{len(created_ids)} ideas stored",
                {"article_id": str(article.id), "title": article.title, "ideas": len(created_ids)},
            ))

            mark_article_processed(supabase, article.id)

        except Exception as exc:
            logger.error(f"scoring_agent_task: article error | id={article.id} | err={exc}")
            errors.append({"article_id": str(article.id), "error": str(exc)})
            failure_count += 1

    duration = time.time() - start_time

    sonnet_cost = format_token_cost(sonnet_in, sonnet_out, settings.claude_model_heavy)
    total_usd = sonnet_cost["estimated_usd"]
    total_tokens = sonnet_in + sonnet_out
    token_cost_dict = {"sonnet": sonnet_cost, "total_usd": round(total_usd, 6)}

    await asyncio.to_thread(upsert_cost_log, supabase, "scoring_agent", total_usd=total_usd, token_count=total_tokens)

    run_log = RunLogCreate(
        agent_name="scoring_agent",
        trigger_type=TriggerType.EVENT,
        processed_count=processed_count,
        success_count=ideas_created_count,
        failure_count=failure_count,
        duration_seconds=round(duration, 2),
        reasoning_trace="\n".join(trace_entries) if trace_entries else None,
        errors=errors,
        token_cost=token_cost_dict,
    )
    try:
        supabase.table("run_logs").insert(run_log.model_dump()).execute()
    except Exception as exc:
        logger.error(f"scoring_agent_task: failed to write run_log | err={exc}")

    if settings.slack_webhook_url and total_usd >= settings.daily_cost_alert_usd:
        send_slack_alert(
            settings.slack_webhook_url,
            f"Scoring agent cost alert: ${total_usd:.4f} in this run "
            f"(threshold: ${settings.daily_cost_alert_usd})",
        )

    logger.info(
        f"scoring_agent_task done | processed={processed_count} "
        f"ideas={ideas_created_count} failures={failure_count} "
        f"duration={duration:.1f}s cost=${total_usd:.4f}"
    )
    return {
        "status": "done",
        "processed": processed_count,
        "ideas_created": ideas_created_count,
        "failures": failure_count,
        "duration_seconds": round(duration, 2),
        "cost_usd": round(total_usd, 6),
    }


async def creation_agent_task(
    ctx: dict,
    idea_ids: list[str],
    content_type: str = "news_driven",
) -> dict:
    """
    Content creation agent — generates platform drafts for approved ideas.
    Triggered: by orchestrator after weekly plan is approved.
    Args:
        idea_ids: List of approved idea UUIDs to generate content for.
    """
    import time
    from app.agents.creation.brand_context import get_brand_context
    from app.agents.creation.content_generator import async_generate_content
    from app.agents.creation.editor_agent import async_refine_draft
    from app.agents.creation.compliance_agent import async_check_compliance
    from app.agents.creation.finance_flags import detect_finance_flags
    from app.agents.creation.db_writer import write_draft, upsert_cost_log
    from app.agents.scoring.embedder import embed_text
    from app.utils.slack import send_slack_alert
    from app.utils.logging import format_token_cost, log_agent_decision
    from app.db.models import Idea, DraftCreate, RunLogCreate, TriggerType

    settings = ctx["settings"]
    supabase = ctx["supabase"]
    start_time = time.time()

    anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    from app.agents.embedding.client import make_embed_client
    embed_client = make_embed_client(
        google_api_key=settings.google_api_key,
        local_model=settings.local_embedding_model,
    )

    processed_count = 0
    draft_count = 0
    failure_count = 0
    errors: list[dict] = []
    trace_entries: list[str] = []
    sonnet_in = sonnet_out = 0

    # Step 1 — Batch-fetch all requested ideas in one query
    _CREATION_CONCURRENCY = 3

    if idea_ids:
        try:
            ideas_resp = (
                supabase.table("ideas")
                .select("*")
                .in_("id", idea_ids)
                .execute()
            )
            ideas_by_id = {str(r["id"]): Idea(**r) for r in (ideas_resp.data or [])}
        except Exception as exc:
            logger.error(f"creation_agent_task: failed to batch-fetch ideas | err={exc}")
            return {
                "status": "error",
                "processed": 0,
                "drafts_created": 0,
                "failures": len(idea_ids),
                "duration_seconds": round(time.time() - start_time, 2),
                "cost_usd": 0.0,
                "error": str(exc),
            }
    else:
        ideas_by_id = {}

    # Report missing ideas upfront
    for idea_id in idea_ids:
        if idea_id not in ideas_by_id:
            logger.warning(f"creation_agent_task: idea not found | id={idea_id}")
            failure_count += 1

    ideas_to_process = [ideas_by_id[iid] for iid in idea_ids if iid in ideas_by_id]
    processed_count = len(idea_ids)  # counts all requested, including not-found

    # Semaphore caps concurrent Claude API calls
    sem = asyncio.Semaphore(_CREATION_CONCURRENCY)

    async def _process_idea(idea: Idea):
        idea_id = str(idea.id)
        local_errors: list[dict] = []
        local_traces: list[str] = []
        local_in = local_out = 0
        drafted = 0
        failed = 0

        async with sem:
            try:
                # Step 2 — Fetch source article context (optional)
                article_context = ""
                if idea.source_article_id:
                    art_resp = (
                        supabase.table("raw_content")
                        .select("structured_summary")
                        .eq("id", str(idea.source_article_id))
                        .execute()
                    )
                    if art_resp.data and art_resp.data[0].get("structured_summary"):
                        s = art_resp.data[0]["structured_summary"]
                        article_context = (
                            f"Story: {s.get('story_narrative', '')}\n"
                            f"Key data: {', '.join(s.get('key_data_points', []))}\n"
                            f"Mechanism: {s.get('mechanism', '')}\n"
                            f"Implications: {s.get('implications', '')}"
                        )

                # Step 3 — Embed idea text and get brand context
                embedding: list[float] = []
                brand_ctx = ""
                embed_input = f"{idea.platform.value}: {idea.edited_angle or idea.angle}"
                embedding = embed_text(embed_input, embed_client)
                if embedding:
                    brand_ctx = get_brand_context(embedding, idea.platform.value, supabase)

                # Step 3b — Retrieve KB context if needed
                kb_context = ""
                if content_type in ("kb_driven", "combined"):
                    if not embedding:
                        logger.warning(
                            "creation_agent_task: KB context requested but embedding unavailable",
                            extra={"content_type": content_type, "idea_id": idea_id},
                        )
                        local_traces.append(log_agent_decision(
                            logger, "kb_context_skipped",
                            "Voyage client unavailable — KB context omitted from prompt",
                            {"idea_id": idea_id, "content_type": content_type},
                        ))
                    else:
                        try:
                            kb_resp = supabase.rpc(
                                "match_knowledge_base",
                                {"query_embedding": embedding, "match_count": 8},
                            ).execute()
                            kb_rows = kb_resp.data or []
                            if kb_rows:
                                kb_context = "\n\n---\n\n".join(r["content"] for r in kb_rows)
                        except Exception as kb_exc:
                            logger.warning(
                                "creation_agent_task: KB retrieval failed",
                                extra={"idea_id": idea_id, "error": str(kb_exc)},
                            )
                            local_traces.append(log_agent_decision(
                                logger, "kb_retrieval_failed",
                                "KB RPC failed — draft will be generated without KB context",
                                {"idea_id": idea_id, "error": str(kb_exc)},
                            ))

                # Step 4 — Generate content with Claude Sonnet (async)
                gen_result = await async_generate_content(
                    idea, article_context, brand_ctx, anthropic_client, settings.claude_model_heavy,
                    kb_context=kb_context,
                    content_type=content_type,
                )
                local_in += gen_result.input_tokens
                local_out += gen_result.output_tokens

                def _set_draft_status(status: str, error: str = "") -> None:
                    """Update draft_status on the idea row. Never raises."""
                    try:
                        update = {"draft_status": status}
                        if error:
                            update["agent_reasoning"] = error[:500]
                        supabase.table("ideas").update(update).eq("id", idea_id).execute()
                    except Exception:
                        pass

                if gen_result.draft_create is None:
                    local_traces.append(log_agent_decision(
                        logger, "no_draft", "async_generate_content returned None",
                        {"idea_id": idea_id, "platform": idea.platform.value},
                    ))
                    failed += 1
                    _set_draft_status("failed", "Content generation returned empty")
                    return drafted, failed, local_in, local_out, local_errors, local_traces

                draft_create = gen_result.draft_create

                # Step 5 — Editor Agent
                refined_text = await async_refine_draft(
                    draft_text=draft_create.content_text,
                    platform=draft_create.platform.value,
                    client=anthropic_client,
                    model=settings.claude_model_heavy
                )
                draft_create.content_text = refined_text

                # Step 6 — Compliance Agent
                comp_res = await async_check_compliance(
                    draft_text=draft_create.content_text,
                    client=anthropic_client,
                    model=settings.claude_model_heavy
                )
                draft_create.content_text = comp_res.fixed_text
                draft_create.compliance_status = comp_res.status

                if comp_res.status != "approved":
                    draft_create.agent_reasoning += f" | Compliance Note: {comp_res.reason}"

                # Step 7 — Detect finance flags
                flags = detect_finance_flags(draft_create.content_text)
                draft_with_flags = DraftCreate(**{
                    **draft_create.model_dump(),
                    "finance_flags": flags,
                })

                # Step 8 — Write draft to DB
                draft_id = write_draft(supabase, draft_with_flags)
                if draft_id:
                    drafted += 1
                    _set_draft_status("done")
                    local_traces.append(log_agent_decision(
                        logger, "draft_written", "Draft stored",
                        {"draft_id": draft_id, "idea_id": idea_id, "platform": idea.platform.value},
                    ))
                else:
                    failed += 1
                    _set_draft_status("failed", "write_draft returned None (DB insert failed)")
                    local_traces.append(log_agent_decision(
                        logger, "draft_write_failed", "write_draft returned None",
                        {"idea_id": idea_id},
                    ))

            except Exception as exc:
                logger.error(f"creation_agent_task: idea error | id={idea_id} | err={exc}")
                local_errors.append({"idea_id": idea_id, "error": str(exc)})
                failed += 1
                try:
                    supabase.table("ideas").update(
                        {"draft_status": "failed", "agent_reasoning": str(exc)[:500]}
                    ).eq("id", idea_id).execute()
                except Exception:
                    pass

        return drafted, failed, local_in, local_out, local_errors, local_traces

    # Step 7 — Run all ideas concurrently (capped at _CREATION_CONCURRENCY)
    gather_results = await asyncio.gather(
        *[_process_idea(idea) for idea in ideas_to_process],
        return_exceptions=True,
    )

    for outcome in gather_results:
        if isinstance(outcome, Exception):
            logger.error(f"creation_agent_task: unhandled gather exception | err={outcome}")
            failure_count += 1
            errors.append({"error": str(outcome)})
        else:
            d, f, tin, tout, errs, traces = outcome
            draft_count += d
            failure_count += f
            sonnet_in += tin
            sonnet_out += tout
            errors.extend(errs)
            trace_entries.extend(traces)

    duration = time.time() - start_time

    sonnet_cost = format_token_cost(sonnet_in, sonnet_out, settings.claude_model_heavy)
    total_usd = sonnet_cost["estimated_usd"]
    total_tokens = sonnet_in + sonnet_out
    token_cost_dict = {"sonnet": sonnet_cost, "total_usd": round(total_usd, 6)}

    await asyncio.to_thread(upsert_cost_log, supabase, "creation_agent", total_usd=total_usd, token_count=total_tokens)

    run_log = RunLogCreate(
        agent_name="creation_agent",
        trigger_type=TriggerType.ORCHESTRATOR,
        processed_count=processed_count,
        success_count=draft_count,
        failure_count=failure_count,
        duration_seconds=round(duration, 2),
        reasoning_trace="\n".join(trace_entries) if trace_entries else None,
        errors=errors,
        token_cost=token_cost_dict,
    )
    try:
        supabase.table("run_logs").insert(run_log.model_dump()).execute()
    except Exception as exc:
        logger.error(f"creation_agent_task: failed to write run_log | err={exc}")

    if settings.slack_webhook_url and total_usd >= settings.daily_cost_alert_usd:
        send_slack_alert(
            settings.slack_webhook_url,
            f"Creation agent cost alert: ${total_usd:.4f} in this run "
            f"(threshold: ${settings.daily_cost_alert_usd})",
        )

    logger.info(
        f"creation_agent_task done | processed={processed_count} "
        f"drafts={draft_count} failures={failure_count} "
        f"duration={duration:.1f}s cost=${total_usd:.4f}"
    )
    return {
        "status": "done",
        "processed": processed_count,
        "drafts_created": draft_count,
        "failures": failure_count,
        "duration_seconds": round(duration, 2),
        "cost_usd": round(total_usd, 6),
    }


async def login_site_task(ctx: dict, *, login_url: str) -> dict:
    """
    Open a VISIBLE Edge browser at login_url so the user can log in manually.
    Uses raw Playwright with a persistent user-data-dir so cookies survive.
    Triggered via the orchestrator 'login_to_site' tool.
    """
    from pathlib import Path
    from urllib.parse import urlparse
    from playwright.async_api import async_playwright
    from app.agents.research.extractor import BROWSER_CHANNEL

    settings = ctx["settings"]
    import re as _re
    domain = urlparse(login_url).netloc.lstrip("www.")
    if not _re.fullmatch(r"[a-zA-Z0-9.\-]+", domain):
        logger.error("login_site_task: unsafe domain string rejected", extra={"domain": domain})
        return {"status": "error", "error": f"Unsafe domain: {domain!r}"}
    profile_dir = Path(settings.browser_sessions_dir).expanduser() / domain
    profile_dir.mkdir(parents=True, exist_ok=True)

    logger.info("login_site_task: opening browser", extra={"domain": domain, "url": login_url})

    try:
        async with async_playwright() as p:
            # Persistent context saves cookies/localStorage automatically when closed
            context = await p.chromium.launch_persistent_context(
                str(profile_dir),
                channel=BROWSER_CHANNEL,
                headless=False,           # user must see and interact
                args=["--no-proxy-server", "--disable-ipv6"],
            )
            page = await context.new_page()
            await page.goto(login_url, timeout=30_000)

            # Poll until the URL leaves the login page (successful auth redirect)
            # or 5 minutes pass.
            import asyncio as _asyncio
            for _ in range(150):          # 150 × 2 s = 5 min
                await _asyncio.sleep(2)
                if not any(kw in page.url for kw in ("login", "signin", "sign-in")):
                    break

            await _asyncio.sleep(1.5)    # let any final redirects settle
            await context.close()

        logger.info("login_site_task: session saved", extra={"domain": domain})
        return {"status": "done", "domain": domain, "profile_dir": str(profile_dir)}
    except Exception as exc:
        logger.warning("login_site_task failed", extra={"domain": domain, "error": str(exc)})
        return {"status": "error", "domain": domain, "error": str(exc)}


async def publishing_agent_task(ctx: dict) -> dict:
    """
    Publishing agent — posts approved drafts that are due.
    Triggered: every 15 minutes by cron.
    """
    import time
    from datetime import datetime, timezone, timedelta
    from app.agents.publishing.poster import post_to_platform
    from app.agents.publishing.db_writer import write_published_post, update_draft_published
    from app.utils.logging import log_agent_decision
    from app.db.models import Draft, RunLogCreate, TriggerType

    settings = ctx["settings"]
    supabase = ctx["supabase"]
    arq_pool = ctx.get("redis")   # arq injects "redis" key into task ctx
    start_time = time.time()

    processed_count = 0
    published_count = 0
    failure_count = 0
    errors: list[dict] = []
    trace_entries: list[str] = []

    now = datetime.now(timezone.utc)

    try:
        resp = (
            supabase.table("drafts")
            .select("*")
            .eq("approval_status", "approved")
            .lte("scheduled_at", now.isoformat())
            .execute()
        )
        drafts = [Draft(**d) for d in (resp.data or [])]
    except Exception as exc:
        logger.error(f"publishing_agent_task: failed to fetch drafts | err={exc}")
        return {
            "status": "error",
            "processed": 0,
            "published": 0,
            "failures": 0,
            "duration_seconds": round(time.time() - start_time, 2),
            "error": str(exc),
        }

    for draft in drafts:
        processed_count += 1
        try:
            # Step 1 — Post to platform
            post_identifier = post_to_platform(draft.platform.value, draft.content_text, settings)
            if post_identifier is None:
                failure_count += 1
                errors.append({"draft_id": str(draft.id), "error": "post_to_platform returned None"})
                continue

            # Step 2 — Record in published_posts
            post_id = write_published_post(supabase, draft.platform.value, post_identifier, draft.id)
            if post_id is None:
                failure_count += 1
                errors.append({"draft_id": str(draft.id), "error": "write_published_post failed"})
                continue

            # Step 3 — Update draft status to published
            update_draft_published(supabase, draft.id)

            # Step 4 — Schedule analytics jobs (24h, 72h, 7d)
            if arq_pool is not None:
                for period, hours in [("24h", 24), ("72h", 72), ("7d", 168)]:
                    await arq_pool.enqueue_job(
                        "analytics_agent_task",
                        post_id=post_id,
                        measurement_period=period,
                        _defer_by=timedelta(hours=hours),
                        _queue_name="arq:analytics",
                    )

            published_count += 1
            trace_entries.append(log_agent_decision(
                logger, "draft_published", "Published and analytics scheduled",
                {"draft_id": str(draft.id), "platform": draft.platform.value, "post_id": post_id},
            ))

        except Exception as exc:
            logger.error(f"publishing_agent_task: draft error | id={draft.id} | err={exc}")
            errors.append({"draft_id": str(draft.id), "error": str(exc)})
            failure_count += 1

    duration = time.time() - start_time

    run_log = RunLogCreate(
        agent_name="publishing_agent",
        trigger_type=TriggerType.CRON,
        processed_count=processed_count,
        success_count=published_count,
        failure_count=failure_count,
        duration_seconds=round(duration, 2),
        reasoning_trace="\n".join(trace_entries) if trace_entries else None,
        errors=errors,
        token_cost={"total_usd": 0.0},
    )
    try:
        supabase.table("run_logs").insert(run_log.model_dump()).execute()
    except Exception as exc:
        logger.error(f"publishing_agent_task: failed to write run_log | err={exc}")

    logger.info(
        f"publishing_agent_task done | processed={processed_count} "
        f"published={published_count} failures={failure_count} "
        f"duration={duration:.1f}s"
    )
    return {
        "status": "done",
        "processed": processed_count,
        "published": published_count,
        "failures": failure_count,
        "duration_seconds": round(duration, 2),
    }


async def analytics_agent_task(
    ctx: dict,
    post_id: str,
    measurement_period: str,
) -> dict:
    """
    Analytics agent — pulls metrics for one post at one time window.
    Triggered: by publishing agent at 24h, 72h, and 7d after publish.
    Args:
        post_id:            UUID of the published_post record.
        measurement_period: "24h", "72h", or "7d"
    """
    import time
    from app.agents.analytics.metrics_fetcher import fetch_metrics, calculate_performance_score
    from app.agents.analytics.db_writer import write_analytics, update_style_guide
    from app.utils.logging import log_agent_decision
    from app.db.models import PublishedPost, RunLogCreate, TriggerType

    settings = ctx["settings"]
    supabase = ctx["supabase"]
    start_time = time.time()

    # Fetch the published post record
    try:
        resp = (
            supabase.table("published_posts")
            .select("*")
            .eq("id", post_id)
            .execute()
        )
        if not resp.data:
            logger.warning(f"analytics_agent_task: post not found | id={post_id}")
            return {
                "status": "error",
                "post_id": post_id,
                "measurement_period": measurement_period,
                "duration_seconds": round(time.time() - start_time, 2),
                "error": "Post not found",
            }
        post = PublishedPost.model_construct(**resp.data[0])
    except Exception as exc:
        logger.error(f"analytics_agent_task: failed to fetch post | id={post_id} | err={exc}")
        return {
            "status": "error",
            "post_id": post_id,
            "measurement_period": measurement_period,
            "duration_seconds": round(time.time() - start_time, 2),
            "error": str(exc),
        }

    # Fetch metrics (stub)
    metrics = fetch_metrics(post.platform, post.post_identifier, measurement_period)

    # Calculate performance score
    performance_score = calculate_performance_score(post.platform, metrics)

    # Store analytics
    analytics_id = write_analytics(
        supabase, post_id, post.platform, measurement_period, metrics, performance_score
    )

    # Update style guide only at 7d mark
    if measurement_period == "7d":
        update_style_guide(supabase, post.platform, performance_score)

    duration = time.time() - start_time

    run_log = RunLogCreate(
        agent_name="analytics_agent",
        trigger_type=TriggerType.EVENT,
        processed_count=1,
        success_count=1 if analytics_id else 0,
        failure_count=0 if analytics_id else 1,
        duration_seconds=round(duration, 2),
        reasoning_trace=log_agent_decision(
            logger, "analytics_stored",
            f"Metrics recorded for {post.platform} at {measurement_period}",
            {"post_id": post_id, "period": measurement_period, "score": performance_score},
        ) if analytics_id else None,
        errors=[],
        token_cost={"total_usd": 0.0},
    )
    try:
        supabase.table("run_logs").insert(run_log.model_dump()).execute()
    except Exception as exc:
        logger.error(f"analytics_agent_task: failed to write run_log | err={exc}")

    logger.info(
        f"analytics_agent_task done | post_id={post_id} "
        f"period={measurement_period} platform={post.platform} "
        f"score={performance_score} duration={duration:.1f}s"
    )
    return {
        "status": "done",
        "post_id": post_id,
        "measurement_period": measurement_period,
        "platform": post.platform,
        "performance_score": performance_score,
        "analytics_id": analytics_id,
        "duration_seconds": round(duration, 2),
    }
