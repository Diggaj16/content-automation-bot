"""
Editor Agent: Refines readability, tone, and technical precision of the drafted content.
"""
import logging
from anthropic import Anthropic, AsyncAnthropic

from app.agents.creation.content_generator import _PLATFORM_GUIDES

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the Editor-in-Chief for Growthvine Capital. Polish the draft for flow, readability, "
    "and clarity while keeping the brand voice: clear, confident, data-driven, mechanism-focused, "
    "and accessible to financially-aware Indian readers (explain, don't show off jargon).\n"
    "- Tighten wording, cut fluff, prefer active voice.\n"
    "- Strictly preserve ALL structural formatting from the platform guide below: bold Unicode "
    "section headers, slide headers ([Slide N:...]), tweet numbering (1/, 2/...), bullet points, "
    "and the branded takeaway section.\n"
    "- Never remove or alter quantitative data (numbers, %, ₹/$ figures, dates, named entities).\n"
    "- Do NOT add a legal disclaimer — the brand's posts don't carry one.\n"
    "- Return ONLY the finalized text. No preamble or conversational text."
)


def _build_prompt(draft_text: str, platform: str) -> str:
    guide = _PLATFORM_GUIDES.get(platform, "")
    guide_section = f"\n\nPlatform formatting requirements:\n{guide}" if guide else ""
    return f"Platform: {platform}{guide_section}\n\nDraft:\n{draft_text}"


def refine_draft(draft_text: str, platform: str, client: Anthropic, model: str) -> str:
    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_prompt(draft_text, platform)}],
        )
        if response.content:
            return response.content[0].text.strip()
    except Exception as exc:
        logger.error(f"Editor failed: {exc}")
    return draft_text


async def async_refine_draft(draft_text: str, platform: str, client: AsyncAnthropic, model: str) -> str:
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_prompt(draft_text, platform)}],
        )
        if response.content:
            return response.content[0].text.strip()
    except Exception as exc:
        logger.error(f"Async Editor failed: {exc}")
    return draft_text
