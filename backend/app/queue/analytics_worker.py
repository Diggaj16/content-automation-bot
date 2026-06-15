"""
Dedicated arq worker for analytics_agent_task only.
Queue: arq:analytics

Start from backend/ with venv active:
    python -m arq app.queue.analytics_worker.AnalyticsWorkerSettings
"""
from app.queue.redis_settings import get_redis_settings
from app.queue.tasks import analytics_agent_task


class AnalyticsWorkerSettings:
    functions = [analytics_agent_task]
    redis_settings = get_redis_settings()
    queue_name = "arq:analytics"
    max_jobs = 5
    job_timeout = 120  # 2 min