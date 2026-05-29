"""
FastAPI application — human approval gates and agent trigger endpoints.

Run locally (from backend/ with venv active):
    uvicorn app.api.main:app --reload --port 8000
"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise shared state on startup; clean up on shutdown."""
    app.state.arq_pool = None
    try:
        import arq
        from app.queue.worker import WorkerSettings
        pool = await arq.create_pool(WorkerSettings.redis_settings)
        app.state.arq_pool = pool
        logger.info("api: arq pool connected")
    except Exception as exc:
        logger.warning(
            f"api: arq pool unavailable — trigger endpoints will return 503 | err={exc}"
        )

    yield

    if app.state.arq_pool is not None:
        await app.state.arq_pool.close()
        logger.info("api: arq pool closed")


def create_app() -> FastAPI:
    """
    Factory function — call this to obtain a configured FastAPI instance.
    Importable without side-effects (lifespan runs only when serving).
    """
    _app = FastAPI(
        title="Content Automation API",
        description="Human approval gates and agent trigger endpoints",
        version="0.1.0",
        lifespan=lifespan,
    )

    _app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],    # tighten in production
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers included in later tasks (ideas, drafts, triggers)

    return _app


app = create_app()
