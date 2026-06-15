"""
Dedicated arq worker for creation_agent_task only.
Queue: arq:creation

Start from backend/ with venv active:
    python -m arq app.queue.creation_worker.CreationWorkerSettings
"""
from app.queue.redis_settings import get_redis_settings
from app.queue.tasks import creation_agent_task


class CreationWorkerSettings:
    functions = [creation_agent_task]
    redis_settings = get_redis_settings()
    queue_name = "arq:creation"
    max_jobs = 3
    job_timeout = 1200  # 20 min