"""
Content generation module for the creation agent.

Uses Claude Sonnet to write platform-specific content based on an approved idea,
the source article context, and past brand content examples.
"""
import json
import re
from dataclasses import dataclass
from typing import Optional

from anthropic import Anthropic, AsyncAnthropic

from app.db.models import DraftCreate, Idea
from app.utils.logging import get_logger

logger = get_logger(__name__)

_MAX_OUTPUT_TOKENS = 4096
_MAX_CONTEXT_CHARS = 4000  # per-source context cap to avoid token overflow

_SYSTEM_PROMPT = (
    "You write social and editorial content for Growthvine Capital, a boutique wealth "
    "management firm in Gurgaon. Growthvine's clients are professionals, executives, "
    "founders, HNIs, and NRIs — people who follow markets, care about their money, and "
    "want to understand what is actually happening and why. They are smart and curious "
    "but they did not go to business school. Write for them.\n\n"
    "VOICE\n\n"
    "Write the way a sharp, well-read analyst would explain something to a friend over "
    "dinner. Confident but never arrogant. Informed but never showing off. The reader "
    "should finish a Growthvine post feeling like they just got a clear explanation of "
    "something that felt complicated five minutes ago.\n\n"
    "Every piece should feel like it is going somewhere. Start with something concrete — "
    "a number, a date, a moment, a situation the reader can picture. Build toward the "
    "insight. Land on something that makes the reader think about what comes next. "
    "Do not open with a broad statement about the economy or markets. Do not close with "
    "a summary of what was already said.\n\n"
    "Mix short, punchy lines with fuller explanatory paragraphs. Vary sentence length "
    "deliberately. A two-word sentence after a long one lands harder than anything else.\n\n"
    "DATA AND MECHANISM\n\n"
    "Ground every claim in something specific — a number, a percentage, a rupee or dollar "
    "figure, a date, a named company or institution from the source material. Vague "
    "statements like 'markets rose significantly' or 'inflation has been high' are not "
    "acceptable. Say exactly what happened, by how much, and when.\n\n"
    "Always explain the mechanism. Do not just state what happened — walk the reader "
    "through how it happened, step by step, in plain language. If a central bank decision "
    "affects bond prices, explain the chain of events. If a rupee move affects an NRI's "
    "remittance, spell it out. The reader should understand the cause, the effect, and "
    "the connection between them.\n\n"
    "When a financial term appears that a non-specialist might not know, define it briefly "
    "in-line and keep moving. One clean sentence is enough. Do not over-explain or turn "
    "the definition into a digression.\n\n"
    "ANGLE AND FRAMING\n\n"
    "Look for the angle that makes the story interesting rather than just informative. "
    "Where the data supports it, challenge a commonly held assumption. Where the numbers "
    "tell a surprising story, let them. Where there is a human or behavioural dimension "
    "to a financial event, use it. The best Growthvine posts do not just report — "
    "they reframe.\n\n"
    "Use the Indian finance lens throughout. RBI, SEBI, Nifty, the rupee, IPOs, bonds, "
    "EPF, FDI, SIPs, and the regulatory environment are the natural reference points. "
    "When global events are relevant, always bring them back to their India impact.\n\n"
    "FORMATTING\n\n"
    "Use bold Unicode section headers (𝗟𝗶𝗸𝗲 𝘁𝗵𝗶𝘀) to structure the piece and give "
    "the reader clear entry points. Headers should describe what the section delivers, "
    "not just label the topic.\n\n"
    "End every piece with a branded takeaway section — either '𝗧𝗵𝗲 𝗕𝗼𝘁𝘁𝗼𝗺 𝗟𝗶𝗻𝗲' "
    "or ' 𝗧𝗵𝗲 𝗚𝗿𝗼𝘄𝘁𝗵𝘃𝗶𝗻𝗲 𝗣𝗲𝗿𝘀𝗽𝗲𝗰𝘁𝗶𝘃𝗲' — with one forward-looking observation "
    "and, where it feels natural, a single question that invites the reader to engage. "
    "The question should be genuinely interesting, not a generic call to comment.\n\n"
    "NEVER\n\n"
    "Give buy or sell recommendations, price targets, or any claim about guaranteed or "
    "expected returns.\n\n"
    "Use filler constructions that add no meaning: 'In today's fast-moving world', "
    "'Let's dive in', 'In conclusion', 'It goes without saying', or anything that sounds "
    "like a template warming up.\n\n"
    "Use double hyphens anywhere in the text. Use a comma, a full stop, or a new "
    "sentence instead.\n\n"
    "Frame an idea by stating what it is not before stating what it is. Make the point "
    "directly.\n\n"
    "Use emoji anywhere in the post, for any reason — not as bullets, not as section "
    "markers, not as a takeaway flourish. Plain text and the bold Unicode headers only.\n\n"
    "Add a legal disclaimer inside the post. Growthvine's posts do not carry one."
)

_PLATFORM_GUIDES: dict[str, str] = {
    "whatsapp": (
        "Write a tight WhatsApp broadcast message for clients/advisors (under 150 words, 4-7 short lines).\n\n"
        "Open with a concrete number, date, or situation the reader can picture — not a generic alert line. "
        "Explain the mechanism in one or two short sentences: what happened and why it actually matters to "
        "their money or compliance position. Close with a single forward-looking or actionable line.\n\n"
        "Rules:\n"
        "- Short lines, no long paragraphs — this is a broadcast message, not a memo.\n"
        "- No emoji anywhere in the message.\n"
        "- No filler, no formal disclaimer, no listicle structure.\n"
        "- Tone is direct, specific, and skimmable — never alarmist."
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
        "Write a long-form LinkedIn post in the Growthvine house style (roughly 250–650 words). "
        "Mirror the structure and voice of the past brand examples provided above.\n\n"
        "Structure:\n"
        "- HOOK: open with a bold Unicode header (𝗟𝗶𝗸𝗲 𝘁𝗵𝗶𝘀). Either a topic label "
        "(e.g. 𝗥𝗕𝗜 𝗠𝗣𝗖 𝗨𝗽𝗱𝗮𝘁𝗲) or a provocative/contrarian one-liner "
        "(e.g. 𝗧𝗵𝗲 𝗺𝗮𝗿𝗸𝗲𝘁 𝘀𝗲𝘁 𝗮 𝗿𝗲𝗰𝗼𝗿𝗱 — 𝘁𝗵𝗲 𝗱𝗮𝘁𝗮 𝘀𝗮𝘆𝘀 𝗼𝘁𝗵𝗲𝗿𝘄𝗶𝘀𝗲).\n"
        "- OPENING: set the scene in 2–4 lines with a specific stat or a short narrative beat.\n"
        "- CONTEXT ASIDE (only when a term needs it): one or two lines defining the key concept for non-specialists.\n"
        "- BODY: 3–6 short sections, each introduced by its OWN bold Unicode subheader, each explaining "
        "one facet of the story with concrete numbers. Use • or ▸ bullets for lists of measures, reasons, or takeaways.\n"
        "- TAKEAWAY: a closing section under a bold header such as 'The Bottom Line' or "
        "'The Growthvine Capital Perspective' (rendered in the same bold Unicode style as the "
        "other headers) that ties it together in 2–4 lines.\n"
        "- Optionally a single engagement question on the final line.\n\n"
        "Rules:\n"
        "- Every section must contain at least one specific number, date, or named entity from the source.\n"
        "- Bold Unicode for ALL section headers; normal text for the body.\n"
        "- No emoji anywhere in the post. Use • or ▸ for bullets, never emoji.\n"
        "- No formal disclaimer line. No generic filler ('In today's world', 'In conclusion')."
    ),
    "twitter": (
        "Write a Twitter/X thread (6-8 tweets, each strictly under 280 characters).\n\n"
        "Structure:\n"
        "- Tweet 1: Bold hook with a surprising data point. No emoji.\n"
        "- Tweets 2-3: What happened and why (specific numbers)\n"
        "- Tweets 4-5: Historical parallel or contrarian perspective\n"
        "- Tweet 6: Second-order effect or what to watch for\n"
        "- Tweet 7-8: Nuanced takeaway + open question\n\n"
        "Rules:\n"
        "- Number each tweet: 1/, 2/, etc.\n"
        "- Separate tweets with a blank line\n"
        "- Each tweet must standalone — no cliffhangers mid-thought\n"
        "- No emoji anywhere in the thread\n"
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
        "- Conclusion: a branded takeaway ('The Bottom Line' / 'The Growthvine Capital Perspective') with an open question\n\n"
        "Rules:\n"
        "- Use bold Unicode for section headers, matching the brand examples\n"
        "- Every section must cite at least one specific number from the source material\n"
        "- Explain any specialist term briefly in-line; no formal disclaimer line"
    ),
    "email": (
        "Write an email newsletter section (350–500 words).\n\n"
        "Structure:\n"
        "- Subject line (max 55 chars): specific and data-driven, not vague\n"
        "- Preview text (max 90 chars): the key tension in one sentence\n"
        "- Opening: one sharp observation grounded in a real number\n"
        "- Body (3 paragraphs): what happened → why it matters → what to watch\n"
        "- 'Worth thinking about:' — one second-order consequence\n"
        "- Closing question for the reader\n\n"
        "Rules:\n"
        "- Conversational but intelligent — like a sharp colleague's weekly note\n"
        "- No investment advice, guaranteed-return claims, or formal disclaimer line"
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

    target_persona = idea.target_persona or "an informed Indian investor"

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

        # Fallback: if JSON parse failed or returned empty, try to extract just
        # content_text value from malformed JSON before giving up.
        if not content_text and raw:
            ct_match = re.search(r'"content_text"\s*:\s*"(.*?)(?<!\\)"\s*[,}]', raw, re.DOTALL)
            if ct_match:
                content_text = ct_match.group(1).replace('\\"', '"').replace("\\n", "\n").strip()
                reasoning = f"Generated for {platform}"
                logger.info(
                    "generate_content: extracted content_text from malformed JSON",
                    extra={"platform": platform},
                )
            elif len(raw.split()) > 20 and not raw.lstrip().startswith("{"):
                # Raw response IS the post (Claude skipped JSON wrapping entirely)
                content_text = raw
                reasoning = f"Generated for {platform}"
                logger.info(
                    "generate_content: using raw response as content_text (no JSON wrapper)",
                    extra={"platform": platform, "words": len(raw.split())},
                )

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

    target_persona = idea.target_persona or "an informed Indian investor"

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

        if not content_text and raw:
            ct_match = re.search(r'"content_text"\s*:\s*"(.*?)(?<!\\)"\s*[,}]', raw, re.DOTALL)
            if ct_match:
                content_text = ct_match.group(1).replace('\\"', '"').replace("\\n", "\n").strip()
                reasoning = f"Generated for {platform}"
                logger.info(
                    "async_generate_content: extracted content_text from malformed JSON",
                    extra={"platform": platform},
                )
            elif len(raw.split()) > 20 and not raw.lstrip().startswith("{"):
                content_text = raw
                reasoning = f"Generated for {platform}"
                logger.info(
                    "async_generate_content: using raw response as content_text (no JSON wrapper)",
                    extra={"platform": platform, "words": len(raw.split())},
                )

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
