"""
Structured logging for agent decisions.
Every key decision an agent makes is logged via log_agent_decision().
These strings accumulate into the reasoning_trace field of run_logs.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any


def get_logger(name: str) -> logging.Logger:
    """Get a named logger with a consistent format."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def log_agent_decision(
    logger: logging.Logger,
    decision: str,
    reasoning: str,
    context: dict[str, Any] | None = None,
) -> str:
    """
    Log a structured agent decision and return it as a JSON string
    so the caller can accumulate entries into a reasoning_trace.

    Usage:
        trace_entries = []
        entry = log_agent_decision(logger, "discard_article", "Below threshold", {"score": 3.2})
        trace_entries.append(entry)
        ...
        reasoning_trace = "\\n".join(trace_entries)
    """
    entry = {
        "ts":        datetime.now(timezone.utc).isoformat(),
        "decision":  decision,
        "reasoning": reasoning,
        "context":   context or {},
    }
    logger.info(json.dumps(entry))
    return json.dumps(entry)


def format_token_cost(
    input_tokens: int,
    output_tokens: int,
    model: str,
) -> dict[str, Any]:
    """
    Build the token_cost dict written to run_logs.
    Rates: per million tokens (update when Anthropic changes pricing).
    """
    rates: dict[str, dict[str, float]] = {
        "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
        "claude-haiku-4-5":  {"input": 0.25, "output": 1.25},
    }
    rate = rates.get(model, {"input": 3.00, "output": 15.00})
    cost = (input_tokens * rate["input"] + output_tokens * rate["output"]) / 1_000_000

    return {
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "model":         model,
        "estimated_usd": round(cost, 6),
    }
