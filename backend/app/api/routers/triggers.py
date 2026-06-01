"""
Agent trigger endpoints and system status.

POST /trigger/research  — manually enqueue research_agent_task
POST /trigger/scoring   — manually enqueue scoring_agent_task
POST /trigger/creation  — manually enqueue creation_agent_task
GET  /status            — recent run_logs + daily cost summary
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from supabase import Client

from app.api.deps import get_arq_pool, get_supabase

router = APIRouter(tags=["System"])


class CreationTriggerRequest(BaseModel):
    idea_ids: list[str]
    content_type: str = "news_driven"


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
    job = await pool.enqueue_job(
        "creation_agent_task",
        idea_ids=body.idea_ids,
        content_type=body.content_type,
    )
    return {
        "job_id": job.job_id if job else None,
        "status": "enqueued",
        "agent": "creation",
        "idea_count": len(body.idea_ids),
        "content_type": body.content_type,
    }


@router.get("/status")
def get_status(
    limit: int = Query(default=10, ge=1, le=100),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Return recent agent run logs and the daily cost summary."""
    try:
        logs_resp = (
            supabase.table("run_logs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        cost_resp = (
            supabase.table("cost_log")
            .select("*")
            .order("date", desc=True)
            .limit(30)
            .execute()
        )
        return {
            "recent_runs": logs_resp.data or [],
            "cost_log": cost_resp.data or [],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
