"""
arq WorkerSettings — original combined worker (backward compatible).

Dedicated workers for each agent type are in:
  - research_worker.py
  - scoring_worker.py
  - creation_worker.py
  - publishing_worker.py
  - analytics_worker.py

Start the combined worker from the backend/ directory with venv active:
    python -m arq app.queue.worker.WorkerSettings

Prerequisites:
    - Redis running locally on port 6379
    - .env file present in backend/ with REDIS_URL set
"""
from arq import cron

from app.queue.redis_settings import get_redis_settings
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
    redis_settings = get_redis_settings()
    max_jobs    = 10
    job_timeout = 2400  # seconds — 40 min max per job (research across 7 sites + prescore retries)

    cron_jobs = [
        # 6:00 AM IST = 00:30 UTC
        cron(research_agent_task, hour=0, minute=30),
        # Publishing queue check every 15 minutes
        cron(publishing_agent_task, minute={0, 15, 30, 45}),
    ]