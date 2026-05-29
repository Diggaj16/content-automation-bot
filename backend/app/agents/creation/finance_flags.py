"""
Finance flag detection for draft content.

Uses regex to identify potentially sensitive financial content that requires
human review before publishing. No AI calls — purely structural detection.
"""
import re
from typing import Optional

from app.db.models import FinanceFlag
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Patterns keyed by FinanceFlag.flag_type
_PATTERNS: dict[str, list[str]] = {
    "investment_advice": [
        r"\b(?:buy|sell|short|invest\s+in)\b",
        r"\bguaranteed\s+(?:return|profit|income|gain)\b",
        r"\b(?:should|must|need\s+to)\s+(?:buy|sell|invest)\b",
    ],
    "regulatory_claim": [
        r"\bSEBI[-\s](?:approved|registered|regulated|compliant|certified)\b",
        r"\bRBI[-\s](?:approved|registered|regulated|licensed)\b",
        r"\b(?:SEBI|RBI|NSE|BSE|IRDAI|PFRDA)\b",
    ],
    "company_name": [
        r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s+(?:Ltd|Limited|Corp|Inc|Pvt\.?|LLP)\b",
    ],
    "financial_figure": [
        r"₹\s*[\d,]+(?:\.\d+)?(?:\s*(?:crore|lakh|thousand|million|billion|cr|L))?",
        r"\b\d+(?:\.\d+)?%",
        r"\b\d{1,3}(?:,\d{3})+\b",
    ],
}

_CONTEXT_WINDOW = 100  # chars before/after match for context


def _extract_context(text: str, match: re.Match) -> str:
    start = max(0, match.start() - _CONTEXT_WINDOW)
    end = min(len(text), match.end() + _CONTEXT_WINDOW)
    return text[start:end].strip()


def detect_finance_flags(content_text: str) -> list[FinanceFlag]:
    """
    Scan content_text for potentially sensitive financial patterns.

    Returns a list of FinanceFlag objects for inclusion in the draft.
    Returns [] on empty input or any internal error. Never raises.
    """
    if not content_text:
        return []

    try:
        seen: set[str] = set()
        flags: list[FinanceFlag] = []

        for flag_type, patterns in _PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, content_text, re.IGNORECASE):
                    matched_text = match.group().strip()
                    key = f"{flag_type}:{matched_text.lower()}"
                    if key in seen:
                        continue
                    seen.add(key)
                    flags.append(FinanceFlag(
                        flag_type=flag_type,
                        content=matched_text,
                        context=_extract_context(content_text, match),
                    ))

        return flags

    except Exception as exc:
        logger.error(f"detect_finance_flags: unexpected error | err={exc}")
        return []
