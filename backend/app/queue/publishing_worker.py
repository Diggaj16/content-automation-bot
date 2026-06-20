"""
Dedicated arq worker for publishing_agent_task only.
Queue: arq:publishing

Start from backend/ with venv active:
    python -m arq app.queue.publishing_worker.PublishingWorkerSettings
"""
from app.queue.redis_settings import get_redis_settings
from app.queue.tasks import publishing_agent_task
from app.queue.worker import shutdown, startup


class PublishingWorkerSettings:
    functions = [publishing_agent_task]
    on_startup  = startup
    on_shutdown = shutdown
    redis_settings = get_redis_settings()
    queue_name = "arq:publishing"
    max_jobs = 5
    job_timeout = 300  # 5 min per batch

    # Publishing cron disabled — poster.py is stubbed (no real platform posting yet).
    # Trigger publishing_agent_task manually via /trigger/publishing once real
    # posting is implemented.
    cron_jobs: list = []
