"""
arq WorkerSettings.

Start the worker from the backend/ directory with venv active:
    python -m arq app.queue.worker.WorkerSettings

Prerequisites:
    - Redis running locally on port 6379
    - .env file present in backend/ with REDIS_URL set
"""
from arq import cron
from arq.connections import RedisSettings

from app.queue.tasks import (
    analytics_agent_task,
    creation_agent_task,
    login_site_task,
    publishing_agent_task,
    research_agent_task,
    scoring_agent_task,
)


async def startup(ctx: dict) -> None:
    """Initialise shared resources available to all task functions via ctx."""
    import sys
    # Crawl4AI prints Unicode arrows (→) that break Windows cp1252 console.
    # Reconfigure stdout/stderr to UTF-8 so scraping never crashes on encoding.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    from app.db.client import get_supabase_client
    from app.config import get_settings
    ctx["supabase"] = get_supabase_client()
    ctx["settings"] = get_settings()


async def shutdown(ctx: dict) -> None:
    pass


def _get_redis_settings() -> RedisSettings:
    """Parse REDIS_URL from settings into arq RedisSettings."""
    from app.config import get_settings
    url = get_settings().redis_url   # e.g. "redis://localhost:6379"
    host, port = "localhost", 6379
    if "://" in url:
        netloc = url.split("://", 1)[1].split("/")[0]
        if ":" in netloc:
            host, port_str = netloc.rsplit(":", 1)
            port = int(port_str)
        else:
            host = netloc
    return RedisSettings(host=host, port=port)


class WorkerSettings:
    functions = [
        research_agent_task,
        scoring_agent_task,
        creation_agent_task,
        publishing_agent_task,
        analytics_agent_task,
        login_site_task,
    ]
    on_startup  = startup
    on_shutdown = shutdown
    # arq reads redis_settings as a class attribute — evaluated at import time.
    # Tests should not import this module directly; use mocks at the task level.
    redis_settings = _get_redis_settings()
    max_jobs    = 10
    job_timeout = 600   # seconds — 10 min max per job

    cron_jobs = [
        # 6:00 AM IST = 00:30 UTC
        cron(research_agent_task, hour=0, minute=30),
        # Publishing queue check every 15 minutes
        cron(publishing_agent_task, minute={0, 15, 30, 45}),
    ]
