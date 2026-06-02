"""
FastAPI application — human approval gates and agent trigger endpoints.

Run locally (from backend/ with venv active):
    uvicorn app.api.main:app --reload --port 8000
"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise shared state on startup; clean up on shutdown."""
    app.state.arq_pool = None
    app.state.orchestrator_agent = None
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
    from app.api.deps import verify_api_key

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

    _auth = [Depends(verify_api_key)]

    from app.api.routers.ideas import router as ideas_router
    _app.include_router(ideas_router, dependencies=_auth)

    from app.api.routers.drafts import router as drafts_router
    _app.include_router(drafts_router, dependencies=_auth)

    from app.api.routers.triggers import router as triggers_router
    _app.include_router(triggers_router, dependencies=_auth)

    from app.api.routers.tables import router as tables_router
    _app.include_router(tables_router, dependencies=_auth)

    from app.api.routers.subscribers import router as subscribers_router
    _app.include_router(subscribers_router)  # no auth — unsubscribe is a public link

    from app.api.routers.knowledge_base import router as kb_router
    _app.include_router(kb_router, dependencies=_auth)

    from app.api.routers.orchestrator import router as orchestrator_router
    _app.include_router(orchestrator_router, dependencies=_auth)

    return _app


app = create_app()
