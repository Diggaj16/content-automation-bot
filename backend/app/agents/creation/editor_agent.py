"""
Editor Agent: Refines readability, tone, and technical precision of the drafted content.
"""
import logging
from anthropic import Anthropic, AsyncAnthropic

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the Editor-in-Chief for Growthvine Capital. Review the provided draft "
    "and improve its flow, readability, and technical precision for a CFA Level 3 audience.\n"
    "- Ensure zero fluff, eliminate passive voice where possible.\n"
    "- Maintain all structural requirements of the platform.\n"
    "- Do NOT remove any disclaimers or quantitative data.\n"
    "- Return ONLY the finalized text. No preamble or conversational text."
)

def refine_draft(draft_text: str, platform: str, client: Anthropic, model: str) -> str:
    user_prompt = f"Platform: {platform}\n\nDraft:\n{draft_text}"
    try:
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        if response.content:
            return response.content[0].text.strip()
    except Exception as exc:
        logger.error(f"Editor failed: {exc}")
    return draft_text

async def async_refine_draft(draft_text: str, platform: str, client: AsyncAnthropic, model: str) -> str:
    user_prompt = f"Platform: {platform}\n\nDraft:\n{draft_text}"
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        if response.content:
            return response.content[0].text.strip()
    except Exception as exc:
        logger.error(f"Async Editor failed: {exc}")
    return draft_text
