"""
Compliance Agent: Enforces SEBI rules, checks for performance guarantees.
"""
import json
import logging
from anthropic import Anthropic, AsyncAnthropic
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the Chief Compliance Officer (CCO) for Growthvine Capital. Review the following "
    "content against SEBI (Securities and Exchange Board of India) advertising regulations and "
    "wealth management compliance standards.\n"
    "Look for:\n"
    "1. Guaranteed return claims (e.g., 'sure profit', 'guaranteed 12%').\n"
    "2. Explicit stock or mutual fund buy/sell recommendations (unless framed purely educationally).\n"
    "3. Missing standard disclaimers.\n\n"
    "Respond with ONLY a JSON object:\n"
    "{\n"
    '  "status": "approved" | "flagged" | "rejected",\n'
    '  "reason": "If flagged or rejected, explain the exact violation.",\n'
    '  "fixed_text": "If you can safely rewrite the problematic sentence to be compliant without changing the meaning, provide the FULL updated content here. Otherwise, leave it as the original text."\n'
    "}"
)

@dataclass
class ComplianceResult:
    status: str
    reason: str
    fixed_text: str

def check_compliance(draft_text: str, client: Anthropic, model: str) -> ComplianceResult:
    try:
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": draft_text}],
        )
        if response.content:
            raw = response.content[0].text.strip()
            # Extract JSON
            import re
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return ComplianceResult(
                    status=data.get("status", "flagged"),
                    reason=data.get("reason", "Failed to parse compliance logic."),
                    fixed_text=data.get("fixed_text", draft_text)
                )
    except Exception as exc:
        logger.error(f"Compliance check failed: {exc}")

    return ComplianceResult("flagged", "Compliance check exception occurred.", draft_text)

async def async_check_compliance(draft_text: str, client: AsyncAnthropic, model: str) -> ComplianceResult:
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": draft_text}],
        )
        if response.content:
            raw = response.content[0].text.strip()
            # Extract JSON
            import re
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return ComplianceResult(
                    status=data.get("status", "flagged"),
                    reason=data.get("reason", "Failed to parse compliance logic."),
                    fixed_text=data.get("fixed_text", draft_text)
                )
    except Exception as exc:
        logger.error(f"Async Compliance check failed: {exc}")

    return ComplianceResult("flagged", "Compliance check exception occurred.", draft_text)
