"""
Stub arq task functions — one per agent.
Each agent plan replaces its stub with the real implementation.
"""
import logging

logger = logging.getLogger(__name__)


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
    logger.info(f"research_agent_task called | topic={topic} | url={url}")
    return {"status": "stub", "agent": "research"}


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
