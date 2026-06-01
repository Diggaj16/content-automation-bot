"""
Orchestrator chat endpoint.

POST /orchestrate
  Request:  { "message": str, "thread_id": str }
  Response: { "response": str, "tools_used": list[str], "thread_id": str }

The agent is built on first call and cached on app.state.orchestrator_agent.
Subsequent calls reuse the same compiled graph (thread-safe; conversation
history is per thread_id via MemorySaver).
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import get_supabase, get_settings
from app.config import Settings
from supabase import Client
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Orchestrator"])


class OrchestratorRequest(BaseModel):
    message: str
    thread_id: str


class OrchestratorResponse(BaseModel):
    response: str
    tools_used: list[str]
    thread_id: str


def _get_or_build_agent(request: Request, supabase: Client, settings: Settings):
    """Return cached orchestrator agent, building it on first call."""
    if not hasattr(request.app.state, "orchestrator_agent") or request.app.state.orchestrator_agent is None:
        from app.agents.orchestrator.agent import build_orchestrator_agent
        arq_pool = getattr(request.app.state, "arq_pool", None)
        request.app.state.orchestrator_agent = build_orchestrator_agent(
            supabase=supabase,
            arq_pool=arq_pool,
            anthropic_api_key=settings.anthropic_api_key,
            model=settings.orchestrator_model,
        )
    return request.app.state.orchestrator_agent


@router.post("/orchestrate", response_model=OrchestratorResponse)
async def orchestrate(
    body: OrchestratorRequest,
    request: Request,
    supabase: Client = Depends(get_supabase),
    settings: Settings = Depends(get_settings),
) -> OrchestratorResponse:
    """Send a message to the orchestrator and get a response."""
    if not body.message.strip():
        raise HTTPException(status_code=422, detail="message must not be empty")

    agent = _get_or_build_agent(request, supabase, settings)

    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": body.message}]},
            config={"configurable": {"thread_id": body.thread_id}},
        )
    except Exception as exc:
        logger.warning("orchestrate endpoint failed", extra={"thread_id": body.thread_id, "error": str(exc)})
        raise HTTPException(status_code=500, detail="Orchestrator error. Please try again.")

    # Extract the final text response from the last AI message
    messages = result.get("messages", [])
    response_text = ""
    for msg in reversed(messages):
        msg_type = type(msg).__name__
        if "AI" in msg_type or "ai" in msg_type.lower():
            content = msg.content
            if isinstance(content, str):
                response_text = content
                break
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        response_text = block.get("text", "")
                        break
                    elif isinstance(block, str):
                        response_text = block
                        break
                if response_text:
                    break

    # Collect tool names used (from ToolMessage entries)
    tools_used: list[str] = []
    for msg in messages:
        msg_type = type(msg).__name__
        if "Tool" in msg_type:
            name = getattr(msg, "name", None)
            if name and name not in tools_used:
                tools_used.append(name)

    return OrchestratorResponse(
        response=response_text or "No response generated.",
        tools_used=tools_used,
        thread_id=body.thread_id,
    )
