"""
Dedicated arq worker for scoring_agent_task only.
Queue: arq:scoring

Start from backend/ with venv active:
    python -m arq app.queue.scoring_worker.ScoringWorkerSettings
"""
from app.queue.redis_settings import get_redis_settings
from app.queue.tasks import scoring_agent_task
from app.queue.worker import shutdown, startup


class ScoringWorkerSettings:
    functions = [scoring_agent_task]
    on_startup  = startup
    on_shutdown = shutdown
    redis_settings = get_redis_settings()
    queue_name = "arq:scoring"
    max_jobs = 3
    job_timeout = 600  # 10 min
