"""
Builds the LangGraph ReAct orchestrator agent.

Usage:
    agent = build_orchestrator_agent(supabase, arq_pool, api_key, model)
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "How many pending ideas?"}]},
        config={"configurable": {"thread_id": "session-abc"}},
    )
    last_message = result["messages"][-1].content
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from supabase import Client

from app.agents.orchestrator.tools import make_tools
from app.utils.logging import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are the operations assistant for an Indian finance content automation pipeline.
You help non-technical operators manage the pipeline through natural language.

Your capabilities:
- Trigger research, scoring, and creation agents
- Check pending ideas and recent agent run history
- Manage curated news sites (add, remove, list)
- View topic performance rankings
- Summarise analytics

Guidelines:
- Be concise and factual. State what you did and the current state.
- When triggering agents, confirm the action and report the job ID.
- When removing a curated site, state clearly that it was deactivated.
- Never fabricate data — use tools to fetch real state.
- If a tool returns an error, report it clearly and suggest what the user can do.
- Financial content note: this pipeline creates educational finance content for Indian audiences.
  It never gives investment advice.
"""


def build_orchestrator_agent(
    supabase: Client,
    arq_pool,
    anthropic_api_key: str,
    model: str = "claude-sonnet-4-5",
):
    """
    Build and return a compiled LangGraph ReAct agent.

    Call once at startup. The returned graph is thread-safe and can be
    called concurrently with different thread_id values in the config.
    """
    tools = make_tools(supabase, arq_pool)
    llm = ChatAnthropic(model=model, api_key=anthropic_api_key)
    memory = MemorySaver()

    agent = create_react_agent(
        model=llm,
        tools=tools,
        checkpointer=memory,
        prompt=_SYSTEM_PROMPT,
    )
    logger.info("orchestrator agent built", extra={"model": model, "tools": len(tools)})
    return agent
