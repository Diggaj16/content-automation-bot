"""
Shared helper to parse REDIS_URL into arq RedisSettings.
Extracted from worker.py so each dedicated worker can import it without duplication.
"""
from arq.connections import RedisSettings


def get_redis_settings() -> RedisSettings:
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