"""
Stub arq task functions — one per agent.
Each agent plan replaces its stub with the real implementation.
"""
from anthropic import Anthropic
from app.utils.logging import get_logger

logger = get_logger(__name__)


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

            # Step 3 — Process each article that passes the threshold
            for link, score in zip(links, pre_result.scores):
                processed_count += 1
                try:
                    if score < site.pre_score_threshold:
                        trace_entries.append(log_agent_decision(
                            logger, "skip_low_score", "Below site threshold",
                            {"url": link.url, "score": score, "threshold": site.pre_score_threshold},
                        ))
                        continue

                    normalized = normalize_url(link.url)
                    if is_url_seen(normalized, supabase):
                        continue

                    content = await fetch_article(link.url)

                    if content.paywall_detected:
                        trace_entries.append(log_agent_decision(
                            logger, "skip_paywall", "Paywall or thin content",
                            {"url": link.url, "word_count": content.word_count},
                        ))
                        failure_count += 1
                        continue

                    if not is_article_fresh(content.publication_date, settings.article_max_age_days):
                        continue

                    if not is_article_long_enough(content.word_count, settings.article_min_words):
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
        f"success={success_count} failures={failure_count} "
        f"duration={duration:.1f}s cost=${total_usd:.4f}"
    )
    return {
        "status": "done",
        "processed": processed_count,
        "success": success_count,
        "failures": failure_count,
        "duration_seconds": round(duration, 2),
        "cost_usd": round(total_usd, 6),
    }


async def scoring_agent_task(ctx: dict) -> dict:
    """
    Scoring agent — reads unprocessed raw_content, scores, generates ideas.
    Triggered: by event after research_agent_task completes.
    """
    logger.info("scoring_agent_task called")
    return {"status": "stub", "agent": "scoring"}


async def creation_agent_task(
    ctx: dict,
    idea_ids: list[str],
) -> dict:
    """
    Content creation agent — generates platform drafts for approved ideas.
    Triggered: by orchestrator after weekly plan is approved.
    Args:
        idea_ids: List of approved idea UUIDs to generate content for.
    """
    logger.info(f"creation_agent_task called | idea_ids={idea_ids}")
    return {"status": "stub", "agent": "creation"}


async def publishing_agent_task(ctx: dict) -> dict:
    """
    Publishing agent — posts approved drafts that are due.
    Triggered: every 15 minutes by cron.
    """
    logger.info("publishing_agent_task called")
    return {"status": "stub", "agent": "publishing"}


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
    logger.info(f"analytics_agent_task called | post_id={post_id} | period={measurement_period}")
    return {"status": "stub", "agent": "analytics"}
