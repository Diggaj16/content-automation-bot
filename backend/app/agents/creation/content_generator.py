"""
Content generation module for the creation agent.

Uses Claude Sonnet to write platform-specific content based on an approved idea,
the source article context, and past brand content examples.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Optional

from anthropic import Anthropic, AsyncAnthropic

from app.db.models import DraftCreate, Idea, Platform
from app.utils.logging import get_logger

logger = get_logger(__name__)

_MAX_OUTPUT_TOKENS = 2048
_MAX_CONTEXT_CHARS = 4000  # per-source context cap to avoid token overflow

_SYSTEM_PROMPT = (
    "You write content for the founder of Growthvine Capital, an elite wealth management and "
    "portfolio management firm in Gurgaon. The audience consists almost entirely of CFA Level 3 "
    "cleared professionals, institutional portfolio managers, and seasoned wealth advisors.\n\n"
    "Voice and style:\n"
    "- Highly analytical, descriptive, and institutional-grade. NO generic retail advice or 'bullshit'.\n"
    "- Use advanced financial terminology correctly (e.g., duration, convexity, Sharpe/Sortino ratios, VaR, portfolio attribution, yield curve dynamics).\n"
    "- Explore the deep fundamental, quantitative, and macroeconomic drivers (the WHY and HOW).\n"
    "- Use specific data points, percentages, basis points, and dates from the source material.\n"
    "- Present sophisticated perspectives (e.g., impact on equity risk premiums, strategic vs tactical asset allocation, structural vs cyclical factors).\n"
    "- Think in second-order and third-order effects — what does this mean downstream for institutional portfolios?\n"
    "- Historical context: connect to past cycles, crises, or precedents when relevant with quantitative backing.\n"
    "- Tone is strictly professional, highly intelligent, and direct — never sensationalist or clickbait.\n"
    "- NEVER give buy/sell recommendations or guaranteed-return claims.\n"
    "- ALWAYS end with a disclaimer: 'This content is for informational and educational "
    "purposes only and should not be considered as financial, investment, tax, or legal advice.'"
)

_PLATFORM_GUIDES: dict[str, str] = {
    "whatsapp": (
        "Write a highly concise WhatsApp broadcast message for institutional clients/advisors (under 150 words).\n\n"
        "Structure:\n"
        "- 🚨 Core macro/market update in one strong sentence.\n"
        "- 📉 Impact on portfolios (use bullets).\n"
        "- 💡 Actionable institutional perspective or tactical shift.\n"
        "Tone is urgent, strictly professional, and skimmable."
    ),
    "carousel": (
        "Write copy for a 5-10 slide analytical LinkedIn carousel.\n\n"
        "Structure each slide explicitly:\n"
        "[Slide 1: Hook] Data-driven question or statement.\n"
        "[Slide 2-4: The Mechanism] Break down the quantitative drivers.\n"
        "[Slide 5-7: Implications] What this means for specific asset classes.\n"
        "[Slide 8: The Second-Order Effect] A non-obvious outcome.\n"
        "[Slide 9: Conclusion] Institutional perspective.\n"
        "Keep text per slide minimal and impactful."
    ),
    "advisor_talking_points": (
        "Write internal talking points for wealth advisors to use in client meetings.\n\n"
        "Structure:\n"
        "- **The Event:** 1-sentence summary.\n"
        "- **The Why:** Bullet points explaining the structural cause.\n"
        "- **Client Impact:** How this affects specific portfolios.\n"
        "- **What to say if asked:** Provide 2-3 scripted, highly professional responses to common client fears or questions.\n"
        "Tone must be authoritative, calming, and analytical."
    ),
    "linkedin": (
        "Write a long-form LinkedIn post (1,800–2,500 characters).\n\n"
        "Structure:\n"
        "- Bold question or statement as the title (use Unicode bold: 𝗟𝗶𝗸𝗲 𝘁𝗵𝗶𝘀)\n"
        "- Opening paragraph: set the scene with a specific data point or recent event\n"
        "- 2-3 analytical paragraphs: explain the why, the mechanism, the historical context\n"
        "- A section with bullet points (use •) for different investor perspectives or key takeaways\n"
        "- 'A second-order effect worth watching:' paragraph — downstream consequences\n"
        "- Closing question that invites genuine reflection\n"
        "- Disclaimer in italic (use Unicode italic: 𝘓𝘪𝘬𝘦 𝘵𝘩𝘪𝘴)\n\n"
        "Rules:\n"
        "- Minimum one specific statistic or data point per paragraph\n"
        "- No emojis except sparingly (max 2 total)\n"
        "- No generic phrases like 'In today's world' or 'In conclusion'\n"
        "- Professional but direct — write for senior finance professionals"
    ),
    "twitter": (
        "Write a Twitter/X thread (6-8 tweets, each strictly under 280 characters).\n\n"
        "Structure:\n"
        "- Tweet 1: Bold hook with a surprising data point. Start with 🧵\n"
        "- Tweets 2-3: What happened and why (specific numbers)\n"
        "- Tweets 4-5: Historical parallel or contrarian perspective\n"
        "- Tweet 6: Second-order effect or what to watch for\n"
        "- Tweet 7-8: Nuanced takeaway + open question\n\n"
        "Rules:\n"
        "- Number each tweet: 1/, 2/, etc.\n"
        "- Separate tweets with a blank line\n"
        "- Each tweet must standalone — no cliffhangers mid-thought\n"
        "- No investment advice or stock recommendations"
    ),
    "blog": (
        "Write a full blog article (700–1,000 words).\n\n"
        "Structure:\n"
        "- SEO title as a question (e.g. 'Is This a Turning Point for Indian IT?')\n"
        "- Hook paragraph: one sharp data point + the core tension\n"
        "- 4-5 H2 sections with full paragraphs (not bullet lists)\n"
        "  - What triggered this?\n"
        "  - Historical context\n"
        "  - Multiple investor perspectives\n"
        "  - Second-order effects\n"
        "  - What to watch next\n"
        "- Conclusion: nuanced takeaway with an open question\n"
        "- Disclaimer paragraph\n\n"
        "Rules:\n"
        "- Every section must cite at least one specific number from the source material\n"
        "- Target: senior professionals and serious retail investors, not beginners"
    ),
    "email": (
        "Write an email newsletter section (350–500 words).\n\n"
        "Structure:\n"
        "- Subject line (max 55 chars): specific and data-driven, not vague\n"
        "- Preview text (max 90 chars): the key tension in one sentence\n"
        "- Opening: one sharp observation grounded in a real number\n"
        "- Body (3 paragraphs): what happened → why it matters → what to watch\n"
        "- 'Worth thinking about:' — one second-order consequence\n"
        "- Closing question for the reader\n"
        "- Disclaimer (one line, italic)\n\n"
        "Rules:\n"
        "- Conversational but intelligent — like a sharp colleague's weekly note\n"
        "- No investment advice or guaranteed-return claims"
    ),
}


@dataclass
class ContentGenerationResult:
    draft_create: Optional[DraftCreate] = None
    input_tokens: int = 0
    output_tokens: int = 0


def generate_content(
    idea: Idea,
    article_context: str,
    brand_context: str,
    client: Anthropic,
    model: str,
    kb_context: str = "",
    content_type: str = "news_driven",
) -> ContentGenerationResult:
    """
    Generate platform-specific content for an approved idea using Claude Sonnet.

    content_type controls which context sources are included in the prompt:
      - news_driven: article_context only
      - kb_driven:   kb_context only
      - combined:    both article_context and kb_context

    Args:
        idea:            The approved Idea (uses edited_angle if set, else angle).
        article_context: Formatted summary of the source article.
        brand_context:   Formatted past brand content examples from match_brand_memory.
        client:          Anthropic sync client.
        model:           Model name (e.g. "claude-sonnet-4-5").
        kb_context:      Formatted knowledge base chunks (empty if not retrieved).
        content_type:    One of "news_driven", "kb_driven", "combined".

    Returns:
        ContentGenerationResult with draft_create=None on any failure. Never raises.
    """
    angle = idea.edited_angle or idea.angle
    platform = idea.platform.value
    guide = _PLATFORM_GUIDES.get(platform, _PLATFORM_GUIDES["linkedin"])

    # Truncate each context source to avoid token overflow
    article_context = article_context[:_MAX_CONTEXT_CHARS] if article_context else ""
    brand_context   = brand_context[:_MAX_CONTEXT_CHARS]   if brand_context   else ""
    kb_context      = kb_context[:_MAX_CONTEXT_CHARS]      if kb_context      else ""

    context_section = ""

    if content_type == "kb_driven":
        # KB only — ignore article context
        if kb_context:
            context_section = f"\n\nKnowledge base context:\n{kb_context}"
    elif content_type == "combined":
        # Both sources
        if article_context:
            context_section = f"\n\nSource article context:\n{article_context}"
        if kb_context:
            context_section += f"\n\nKnowledge base context:\n{kb_context}"
    else:
        # news_driven (default) — article context only
        if article_context:
            context_section = f"\n\nSource article context:\n{article_context}"

    if brand_context:
        context_section += f"\n\n{brand_context}"

    target_persona = idea.target_persona or "CFA Level 3 Professional"

    user_prompt = (
        f"Content angle: {angle}\n"
        f"Target Persona: {target_persona}\n"
        f"Platform: {platform}\n"
        f"{context_section}\n\n"
        f"Platform writing guide:\n{guide}\n\n"
        "Return ONLY a JSON object with these exact keys:\n"
        '{"content_text": "the complete content ready to post", '
        '"reasoning": "1-2 sentences explaining why this angle works for this persona on this platform"}'
    )

    try:
        message = client.messages.create(
            model=model,
            max_tokens=_MAX_OUTPUT_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens

        if not message.content:
            logger.warning("generate_content: empty content list in response")
            return ContentGenerationResult(input_tokens=input_tokens, output_tokens=output_tokens)

        raw = message.content[0].text.strip()

        # Try JSON extraction first
        content_text = ""
        reasoning = ""
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                content_text = data.get("content_text", "").strip()
                reasoning = data.get("reasoning", "").strip()
            except json.JSONDecodeError:
                pass

        # Fallback: if JSON parse failed or returned empty, use the raw response directly.
        # This handles cases where Claude follows the format guide so literally it
        # forgets to wrap in JSON — the raw text IS the post.
        if not content_text and raw and len(raw.split()) > 20:
            logger.info(
                "generate_content: no JSON found, using raw response as content_text",
                extra={"platform": platform, "words": len(raw.split())},
            )
            content_text = raw
            reasoning = f"Generated for {platform}"

        if not content_text:
            logger.warning("generate_content: empty response", extra={"platform": platform})
            return ContentGenerationResult(input_tokens=input_tokens, output_tokens=output_tokens)

        draft_create = DraftCreate(
            platform=idea.platform,
            content_text=content_text,
            target_persona=target_persona,
            agent_reasoning=reasoning or f"Generated for {platform}",
            source_idea_id=idea.id,
            finance_flags=[],  # Populated separately by finance_flags module
        )

        return ContentGenerationResult(
            draft_create=draft_create,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    except json.JSONDecodeError as exc:
        logger.warning("generate_content: JSON parse error", extra={"platform": platform, "err": str(exc)})
        return ContentGenerationResult()
    except Exception as exc:
        logger.error("generate_content: API error", extra={"platform": platform, "err": str(exc)})
        return ContentGenerationResult()


async def async_generate_content(
    idea: Idea,
    article_context: str,
    brand_context: str,
    client: AsyncAnthropic,
    model: str,
    kb_context: str = "",
    content_type: str = "news_driven",
) -> ContentGenerationResult:
    """
    Async version of generate_content using AsyncAnthropic.
    Identical logic — does not block the event loop.
    """
    angle = idea.edited_angle or idea.angle
    platform = idea.platform.value
    guide = _PLATFORM_GUIDES.get(platform, _PLATFORM_GUIDES["linkedin"])

    # Truncate each context source to avoid token overflow
    article_context = article_context[:_MAX_CONTEXT_CHARS] if article_context else ""
    brand_context   = brand_context[:_MAX_CONTEXT_CHARS]   if brand_context   else ""
    kb_context      = kb_context[:_MAX_CONTEXT_CHARS]      if kb_context      else ""

    context_section = ""
    if content_type == "kb_driven":
        if kb_context:
            context_section = f"\n\nKnowledge base context:\n{kb_context}"
    elif content_type == "combined":
        if article_context:
            context_section = f"\n\nSource article context:\n{article_context}"
        if kb_context:
            context_section += f"\n\nKnowledge base context:\n{kb_context}"
    else:
        if article_context:
            context_section = f"\n\nSource article context:\n{article_context}"

    if brand_context:
        context_section += f"\n\n{brand_context}"

    target_persona = idea.target_persona or "CFA Level 3 Professional"

    user_prompt = (
        f"Content angle: {angle}\n"
        f"Target Persona: {target_persona}\n"
        f"Platform: {platform}\n"
        f"{context_section}\n\n"
        f"Platform writing guide:\n{guide}\n\n"
        "Return ONLY a JSON object with these exact keys:\n"
        '{"content_text": "the complete content ready to post", '
        '"reasoning": "1-2 sentences explaining why this angle works for this persona on this platform"}'
    )

    try:
        message = await client.messages.create(
            model=model,
            max_tokens=_MAX_OUTPUT_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens

        if not message.content:
            logger.warning("async_generate_content: empty content list in response")
            return ContentGenerationResult(input_tokens=input_tokens, output_tokens=output_tokens)

        raw = message.content[0].text.strip()

        content_text = ""
        reasoning = ""
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                content_text = data.get("content_text", "").strip()
                reasoning = data.get("reasoning", "").strip()
            except json.JSONDecodeError:
                pass

        if not content_text and raw and len(raw.split()) > 20:
            logger.info(
                "async_generate_content: no JSON found, using raw response as content_text",
                extra={"platform": platform, "words": len(raw.split())},
            )
            content_text = raw
            reasoning = f"Generated for {platform}"

        if not content_text:
            logger.warning("async_generate_content: empty response", extra={"platform": platform})
            return ContentGenerationResult(input_tokens=input_tokens, output_tokens=output_tokens)

        draft_create = DraftCreate(
            platform=idea.platform,
            content_text=content_text,
            target_persona=target_persona,
            agent_reasoning=reasoning or f"Generated for {platform}",
            source_idea_id=idea.id,
            finance_flags=[],
        )

        return ContentGenerationResult(
            draft_create=draft_create,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    except json.JSONDecodeError as exc:
        logger.warning("async_generate_content: JSON parse error", extra={"platform": platform, "err": str(exc)})
        return ContentGenerationResult()
    except Exception as exc:
        logger.error("async_generate_content: API error", extra={"platform": platform, "err": str(exc)})
        return ContentGenerationResult()
