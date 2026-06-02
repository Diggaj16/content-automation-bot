"""
Stub arq task functions — one per agent.
Each agent plan replaces its stub with the real implementation.
"""
import asyncio

from anthropic import Anthropic
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Max simultaneous article fetches per site (browser tabs effectively)
_ARTICLE_CONCURRENCY = 3


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
    from app.agents.research.scraper import scrape_homepage
    from app.agents.research.extractor import fetch_article, normalize_url
    from app.agents.research.filters import is_url_seen, is_article_fresh, is_article_long_enough
    from app.agents.research.prescorer import pre_score_headlines
    from app.agents.research.summariser import summarise_article
    from app.agents.research.db_writer import (
        upsert_raw_content, record_site_success, record_site_failure, upsert_cost_log,
    )
    from app.utils.slack import send_slack_alert
    from app.utils.logging import format_token_cost, log_agent_decision
    from app.db.models import CuratedSite, RunLogCreate, TriggerType

    settings = ctx["settings"]
    supabase = ctx["supabase"]
    start_time = time.time()

    anthropic_client = Anthropic(api_key=settings.anthropic_api_key)

    processed_count = 0
    success_count = 0
    failure_count = 0
    skipped_count = 0   # articles skipped for legitimate reasons (duplicate, stale, short, low-score)
    errors: list[dict] = []
    trace_entries: list[str] = []

    # Separate token tracking per model for accurate cost calculation
    haiku_in = haiku_out = 0
    sonnet_in = sonnet_out = 0

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

    for site in sites:
        try:
            # Step 1 — Scrape section page
            links = await scrape_homepage(site.section_url, site.site_name)
            if not links:
                record_site_failure(supabase, site.id, "No links extracted", settings.site_failure_pause_threshold)
                failure_count += 1
                continue

            # Step 2 — Batch pre-score all headlines (one Haiku call per site)
            titles = [lnk.title for lnk in links]
            pre_result = pre_score_headlines(titles, anthropic_client, settings.claude_model_light)
            haiku_in += pre_result.input_tokens
            haiku_out += pre_result.output_tokens

            if len(pre_result.scores) != len(links):
                logger.warning(
                    f"pre_score count mismatch: {len(links)} links vs {len(pre_result.scores)} scores"
                )

            # Step 3 — Filter: pre-score threshold + batch dedup (1 DB call instead of N)
            score_filtered = [
                (link, score)
                for link, score in zip(links, pre_result.scores)
                if score >= site.pre_score_threshold
            ]
            low_score_count = len(links) - len(score_filtered)
            skipped_count += low_score_count

            if score_filtered:
                # Batch dedup: one Supabase IN() query instead of N individual SELECTs
                norm_map = {normalize_url(l.url): (l, s) for l, s in score_filtered}
                try:
                    seen_resp = (
                        supabase.table("raw_content")
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
                skipped_count += len(norm_map) - len(to_fetch)

                # cap per-site to avoid timeout
                cap = settings.articles_per_site
                if len(to_fetch) > cap:
                    pre_cap_count = len(to_fetch)  # capture BEFORE reassignment
                    to_fetch = sorted(to_fetch, key=lambda x: x[1], reverse=True)[:cap]
                    skipped_count += pre_cap_count - cap
            else:
                to_fetch = []

            # Step 3b — Fetch articles in parallel (up to _ARTICLE_CONCURRENCY at once)
            sem = asyncio.Semaphore(_ARTICLE_CONCURRENCY)

            async def _fetch(link_url: str):
                async with sem:
                    return await fetch_article(link_url, sessions_dir=settings.browser_sessions_dir)

            fetch_results = await asyncio.gather(
                *[_fetch(link.url) for link, _, _ in to_fetch],
                return_exceptions=True,
            )

            for (link, score, _norm), content_or_exc in zip(to_fetch, fetch_results):
                processed_count += 1
                try:
                    if isinstance(content_or_exc, Exception):
                        logger.warning("research_agent_task: article fetch error",
                                       extra={"url": link.url, "error": str(content_or_exc)})
                        failure_count += 1
                        errors.append({"url": link.url, "error": str(content_or_exc)})
                        continue

                    content = content_or_exc

                    if content.paywall_detected:
                        trace_entries.append(log_agent_decision(
                            logger, "skip_paywall", "Paywall or thin content",
                            {"url": link.url, "word_count": content.word_count},
                        ))
                        # Alert only when no saved login session exists for this domain
                        from pathlib import Path
                        from urllib.parse import urlparse as _urlparse
                        _domain = _urlparse(link.url).netloc.lstrip("www.")
                        _has_session = (
                            Path(settings.browser_sessions_dir).expanduser() / _domain
                        ).exists()
                        if not _has_session:
                            send_slack_alert(
                                settings.slack_webhook_url,
                                f"🔐 *Paywall hit* on `{_domain}`\n"
                                f"Tell the orchestrator: *login to {link.url}*\n"
                                f"A browser will open — log in once and all future scrapes will use your saved session.",
                            )
                        skipped_count += 1   # paywall = access issue, not a site failure
                        continue

                    if not is_article_fresh(content.publication_date, settings.article_max_age_days):
                        skipped_count += 1
                        continue

                    if not is_article_long_enough(content.word_count, settings.article_min_words):
                        skipped_count += 1
                        continue

                    # Step 4 — Structured summarisation (Sonnet)
                    sum_result = summarise_article(
                        content.full_text, content.title, anthropic_client, settings.claude_model_heavy,
                    )
                    sonnet_in += sum_result.input_tokens
                    sonnet_out += sum_result.output_tokens

                    # Step 5 — Write to DB
                    article_id = upsert_raw_content(
                        supabase, content, sum_result.summary, score, source_name=site.site_name,
                    )
                    if article_id:
                        success_count += 1
                        trace_entries.append(log_agent_decision(
                            logger, "store_article", "Stored successfully",
                            {"id": article_id, "url": link.url, "score": score},
                        ))
                    else:
                        failure_count += 1
                        trace_entries.append(log_agent_decision(
                            logger, "store_failed", "upsert_raw_content returned None",
                            {"url": link.url, "score": score},
                        ))
                except Exception as article_exc:
                    logger.warning(
                        f"research_agent_task: article error | url={link.url} | err={article_exc}"
                    )
                    failure_count += 1

            record_site_success(supabase, site.id)

        except Exception as exc:
            logger.error(f"research_agent_task: site error | site={site.site_name} | err={exc}")
            errors.append({"site": site.site_name, "error": str(exc)})
            record_site_failure(supabase, site.id, str(exc), settings.site_failure_pause_threshold)
            failure_count += 1

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
    upsert_cost_log(supabase, "research_agent", total_usd=total_usd, token_count=total_tokens)

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
        supabase.table("run_logs").insert(run_log.model_dump()).execute()
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

    # Auto-chain to scoring agent
    arq_pool = ctx.get("redis")
    if arq_pool is not None:
        try:
            await arq_pool.enqueue_job("scoring_agent_task")
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

            idea_result = generate_ideas(article, anthropic_client, settings.claude_model_heavy)
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

    upsert_cost_log(supabase, "scoring_agent", total_usd=total_usd, token_count=total_tokens)

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
    from app.agents.creation.content_generator import generate_content
    from app.agents.creation.finance_flags import detect_finance_flags
    from app.agents.creation.db_writer import write_draft, upsert_cost_log
    from app.agents.scoring.embedder import embed_text
    from app.utils.slack import send_slack_alert
    from app.utils.logging import format_token_cost, log_agent_decision
    from app.db.models import Idea, DraftCreate, RunLogCreate, TriggerType

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
    draft_count = 0
    failure_count = 0
    errors: list[dict] = []
    trace_entries: list[str] = []
    sonnet_in = sonnet_out = 0

    for idea_id in idea_ids:
        processed_count += 1
        try:
            # Step 1 — Fetch idea
            idea_resp = (
                supabase.table("ideas")
                .select("*")
                .eq("id", idea_id)
                .execute()
            )
            if not idea_resp.data:
                logger.warning(f"creation_agent_task: idea not found | id={idea_id}")
                failure_count += 1
                continue
            idea = Idea(**idea_resp.data[0])

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
                    trace_entries.append(log_agent_decision(
                        logger, "kb_context_skipped",
                        "Voyage client unavailable — KB context omitted from prompt",
                        {"idea_id": idea_id, "content_type": content_type},
                    ))
                elif embedding:
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
                        trace_entries.append(log_agent_decision(
                            logger, "kb_retrieval_failed",
                            "KB RPC failed — draft will be generated without KB context",
                            {"idea_id": idea_id, "error": str(kb_exc)},
                        ))

            # Step 4 — Generate content with Claude Sonnet
            gen_result = generate_content(
                idea, article_context, brand_ctx, anthropic_client, settings.claude_model_heavy,
                kb_context=kb_context,
                content_type=content_type,
            )
            sonnet_in += gen_result.input_tokens
            sonnet_out += gen_result.output_tokens

            if gen_result.draft_create is None:
                trace_entries.append(log_agent_decision(
                    logger, "no_draft", "generate_content returned None",
                    {"idea_id": idea_id, "platform": idea.platform.value},
                ))
                failure_count += 1
                continue

            # Step 5 — Detect finance flags
            flags = detect_finance_flags(gen_result.draft_create.content_text)
            draft_with_flags = DraftCreate(**{
                **gen_result.draft_create.model_dump(),
                "finance_flags": flags,
            })

            # Step 6 — Write draft to DB
            draft_id = write_draft(supabase, draft_with_flags)
            if draft_id:
                draft_count += 1
                trace_entries.append(log_agent_decision(
                    logger, "draft_written", "Draft stored",
                    {"draft_id": draft_id, "idea_id": idea_id, "platform": idea.platform.value},
                ))
            else:
                failure_count += 1
                trace_entries.append(log_agent_decision(
                    logger, "draft_write_failed", "write_draft returned None",
                    {"idea_id": idea_id},
                ))

        except Exception as exc:
            logger.error(f"creation_agent_task: idea error | id={idea_id} | err={exc}")
            errors.append({"idea_id": idea_id, "error": str(exc)})
            failure_count += 1

    duration = time.time() - start_time

    sonnet_cost = format_token_cost(sonnet_in, sonnet_out, settings.claude_model_heavy)
    total_usd = sonnet_cost["estimated_usd"]
    total_tokens = sonnet_in + sonnet_out
    token_cost_dict = {"sonnet": sonnet_cost, "total_usd": round(total_usd, 6)}

    upsert_cost_log(supabase, "creation_agent", total_usd=total_usd, token_count=total_tokens)

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
    Open a VISIBLE browser at login_url so the user can log in manually.

    The browser uses a persistent profile — cookies are saved automatically on close.
    All future fetch_article calls for this domain reuse the saved session.
    Triggered via the orchestrator 'login_to_site' tool.
    """
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from pathlib import Path
    from urllib.parse import urlparse

    settings = ctx["settings"]
    domain = urlparse(login_url).netloc.lstrip("www.")
    profile_dir = Path(settings.browser_sessions_dir).expanduser() / domain
    profile_dir.mkdir(parents=True, exist_ok=True)

    logger.info("login_site_task: opening browser", extra={"domain": domain, "url": login_url})

    browser_cfg = BrowserConfig(
        headless=False,              # visible — user must interact
        verbose=False,
        user_data_dir=str(profile_dir),
        use_persistent_context=True, # automatically saves cookies/localStorage on close
    )

    # Waits until the URL changes away from the login page (i.e. redirect after auth)
    # or times out after 5 minutes.
    _wait_js = """
(async () => {
    const startUrl = window.location.href;
    const start = Date.now();
    while (Date.now() - start < 300000) {
        const cur = window.location.href;
        if (cur !== startUrl && !/login|signin|sign-in/i.test(cur)) break;
        await new Promise(r => setTimeout(r, 2000));
    }
    await new Promise(r => setTimeout(r, 1500));
})();
"""

    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        page_timeout=320_000,        # 5 min 20 sec — must exceed JS wait time
        js_code=_wait_js,
        delay_before_return_html=1500,
    )

    try:
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            await crawler.arun(url=login_url, config=run_cfg)
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
