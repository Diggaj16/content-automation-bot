"""
Agent trigger endpoints and system status.

POST /trigger/research  — manually enqueue research_agent_task
POST /trigger/scoring   — manually enqueue scoring_agent_task
POST /trigger/creation  — manually enqueue creation_agent_task
GET  /status            — recent run_logs + daily cost summary
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_arq_pool, get_db
from app.db.models import ContentType
from app.db.orm import CostLog, RunLog
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["System"])


class CreationTriggerRequest(BaseModel):
    idea_ids: list[str]
    content_type: ContentType = ContentType.NEWS_DRIVEN


@router.post("/trigger/research")
async def trigger_research(pool=Depends(get_arq_pool)) -> dict:
    """Manually enqueue the research agent. Returns 503 if Redis is unavailable."""
    if pool is None:
        raise HTTPException(
            status_code=503, detail="Queue unavailable — Redis not connected"
        )
    job = await pool.enqueue_job("research_agent_task")
    return {
        "job_id": job.job_id if job else None,
        "status": "enqueued",
        "agent": "research",
    }


@router.post("/trigger/scoring")
async def trigger_scoring(pool=Depends(get_arq_pool)) -> dict:
    """Manually enqueue the scoring agent. Returns 503 if Redis is unavailable."""
    if pool is None:
        raise HTTPException(
            status_code=503, detail="Queue unavailable — Redis not connected"
        )
    job = await pool.enqueue_job("scoring_agent_task")
    return {
        "job_id": job.job_id if job else None,
        "status": "enqueued",
        "agent": "scoring",
    }


@router.post("/trigger/creation")
async def trigger_creation(
    body: CreationTriggerRequest,
    pool=Depends(get_arq_pool),
) -> dict:
    """Manually enqueue the creation agent for the given approved idea IDs."""
    if pool is None:
        raise HTTPException(
            status_code=503, detail="Queue unavailable — Redis not connected"
        )
    if not body.idea_ids:
        raise HTTPException(status_code=422, detail="idea_ids must not be empty")
    if len(body.idea_ids) > 50:
        raise HTTPException(status_code=422, detail="idea_ids must not exceed 50 items per request")
    job = await pool.enqueue_job(
        "creation_agent_task",
        idea_ids=body.idea_ids,
        content_type=body.content_type.value,
    )
    return {
        "job_id": job.job_id if job else None,
        "status": "enqueued",
        "agent": "creation",
        "idea_count": len(body.idea_ids),
        "content_type": body.content_type.value,
    }


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, request: Request) -> dict:
    """Poll arq job status. Returns status + result when complete."""
    pool = request.app.state.arq_pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Queue unavailable — Redis not connected")
    from arq.jobs import Job
    job = Job(job_id, pool)
    status = await job.status()
    result = None
    if status.value == "complete":
        try:
            result = await job.result(timeout=0)
        except Exception:
            pass
    return {"job_id": job_id, "status": status.value, "result": result}


def _row_to_dict(model, row) -> dict:
    return {c.name: getattr(row, c.name) for c in model.__table__.columns}


@router.get("/status")
def get_status(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """Return recent agent run logs and the daily cost summary."""
    try:
        logs = db.execute(
            select(RunLog).order_by(RunLog.created_at.desc()).limit(limit)
        ).scalars().all()
        costs = db.execute(
            select(CostLog).order_by(CostLog.date.desc()).limit(30)
        ).scalars().all()
        return {
            "recent_runs": [_row_to_dict(RunLog, r) for r in logs],
            "cost_log": [_row_to_dict(CostLog, r) for r in costs],
        }
    except Exception as exc:
        logger.warning("triggers router error", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error")
