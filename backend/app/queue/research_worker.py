"""
Dedicated arq worker for research_agent_task only.
Queue: arq:research

Start from backend/ with venv active:
    python -m arq app.queue.research_worker.ResearchWorkerSettings
"""
from arq import cron
from app.queue.redis_settings import get_redis_settings
from app.queue.tasks import research_agent_task
from app.queue.worker import shutdown, startup


class ResearchWorkerSettings:
    functions = [research_agent_task]
    redis_settings = get_redis_settings()
    queue_name = "arq:research"
    max_jobs = 2
    job_timeout = 3600  # 60 min — research across 7+ sites can be slow

    on_startup  = startup
    on_shutdown = shutdown

    cron_jobs = [
        # 6:00 AM IST = 00:30 UTC
        cron(research_agent_task, hour=0, minute=30),
    ]