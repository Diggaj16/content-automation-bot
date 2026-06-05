"""
Orchestrator chat endpoint.

POST /orchestrate
  Request:  { "message": str, "thread_id": str }
  Response: { "response": str, "tools_used": list[str], "thread_id": str }

The agent is built on first call and cached on app.state.orchestrator_agent.
Subsequent calls reuse the same compiled graph (thread-safe; conversation
history is per thread_id via MemorySaver).
"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from langchain_core.messages import AIMessage, ToolMessage
from pydantic import BaseModel, Field

from app.api.deps import get_supabase, get_settings
from app.config import Settings
from supabase import Client
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Orchestrator"])

# Lock prevents two concurrent cold-start requests from building the agent twice.
_agent_build_lock = asyncio.Lock()


class OrchestratorRequest(BaseModel):
    message:   str = Field(..., min_length=1, max_length=32000)
    thread_id: str = Field(..., min_length=1, max_length=128)


class OrchestratorResponse(BaseModel):
    response: str
    tools_used: list[str]
    thread_id: str


def _settings_fingerprint(settings: Settings) -> str:
    """Hash of the settings fields the agent depends on — rebuild if these change."""
    return f"{settings.anthropic_api_key}|{settings.tavily_api_key}|{settings.orchestrator_model}"


async def _get_or_build_agent(request: Request, supabase: Client, settings: Settings):
    """Return cached orchestrator agent, building (or rebuilding) as needed.

    Rebuilds automatically when API keys or the model change so a server
    restart is not required after updating .env.
    """
    fingerprint = _settings_fingerprint(settings)
    cached = request.app.state.orchestrator_agent
    cached_fp = getattr(request.app.state, "orchestrator_fingerprint", None)

    if cached is not None and cached_fp == fingerprint:
        return cached

    async def _build():
        async with _agent_build_lock:
            if (request.app.state.orchestrator_agent is None
                    or getattr(request.app.state, "orchestrator_fingerprint", None) != fingerprint):
                from app.agents.orchestrator.agent import build_orchestrator_agent
                arq_pool = getattr(request.app.state, "arq_pool", None)
                request.app.state.orchestrator_agent = build_orchestrator_agent(
                    supabase=supabase,
                    arq_pool=arq_pool,
                    anthropic_api_key=settings.anthropic_api_key,
                    model=settings.orchestrator_model,
                    tavily_api_key=settings.tavily_api_key,
                )
                request.app.state.orchestrator_fingerprint = fingerprint
                logger.info("orchestrator agent (re)built", extra={"has_tavily": bool(settings.tavily_api_key)})

    try:
        # asyncio.wait_for is compatible with Python 3.10+ (asyncio.timeout needs 3.11)
        await asyncio.wait_for(_build(), timeout=30)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=503, detail="Orchestrator initialisation timed out. Try again.")
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

    agent = await _get_or_build_agent(request, supabase, settings)

    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": body.message}]},
            config={"configurable": {"thread_id": body.thread_id}},
        )
    except Exception as exc:
        logger.warning("orchestrate endpoint failed", extra={"thread_id": body.thread_id, "error": str(exc)})
        raise HTTPException(status_code=500, detail="Orchestrator error. Please try again.")

    # Extract the final text response from the last AIMessage
    messages = result.get("messages", [])
    response_text = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
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
        if isinstance(msg, ToolMessage):
            name = getattr(msg, "name", None)
            if name and name not in tools_used:
                tools_used.append(name)

    return OrchestratorResponse(
        response=response_text or "No response generated.",
        tools_used=tools_used,
        thread_id=body.thread_id,
    )
