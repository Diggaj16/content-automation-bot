"""
LangGraph tool factory for the orchestrator agent.

Call make_tools(arq_pool, ...) once at startup — the agent (and these tools,
captured via closure) is built once and cached for the app's lifetime. A
SQLAlchemy Session must NOT be captured the same way a long-lived Supabase
client was — each tool opens its own short-lived session_scope() per call.
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from langchain_core.tools import tool
from sqlalchemy import select

from app.db.orm import (
    BrandMemory,
    CuratedSite,
    Draft,
    EmailSubscriber,
    Idea,
    KnowledgeBase,
    PublishedPost,
    RawContent,
    RunLog,
    TopicPerformanceModel,
    UserDecisionSummary,
)
from app.db.session import session_scope
from app.db.vector_search import match_brand_memory
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _duckduckgo_search(query: str, max_results: int = 3) -> list[dict]:
    """Search using DuckDuckGo. Returns list of {url, title, snippet}."""
    try:
        from duckduckgo_search import DDGS  # type: ignore[import-untyped]
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "url": r.get("href") or r.get("url", ""),
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                })
        return results
    except Exception as exc:
        logger.warning("_duckduckgo_search failed", extra={"query": query, "error": str(exc)})
        return []


def _tavily_search(query: str, api_key: str, max_results: int = 3) -> list[dict]:
    """Search using Tavily API. Returns list of {url, title, snippet}."""
    try:
        from tavily import TavilyClient  # type: ignore[import-untyped]
        client = TavilyClient(api_key=api_key)
        resp = client.search(query=query, max_results=max_results, search_depth="advanced")
        return [
            {
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "snippet": r.get("content", ""),
            }
            for r in resp.get("results", [])
        ]
    except Exception as exc:
        logger.warning("_tavily_search failed", extra={"query": query, "error": str(exc)})
        return []


def _fetch_article_sync(url: str):
    """Synchronous wrapper around async fetch_article for use inside tools.

    Creates the coroutine inside the worker thread (thread-safe), and uses
    a non-blocking executor shutdown so a timeout doesn't freeze the caller.
    Note: fetch_article signature is (url, *, timeout_ms, browser) — no sessions_dir.
    """
    import asyncio
    import concurrent.futures
    from app.agents.research.extractor import fetch_article

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                future = executor.submit(
                    lambda: asyncio.run(fetch_article(url))
                )
                return future.result(timeout=30)
            except concurrent.futures.TimeoutError:
                logger.warning("_fetch_article_sync timed out", extra={"url": url})
                return None
            finally:
                executor.shutdown(wait=False, cancel_futures=True)
        else:
            return loop.run_until_complete(fetch_article(url))
    except Exception as exc:
        logger.warning("_fetch_article_sync failed", extra={"url": url, "error": str(exc)})
        return None


def _is_safe_url(url: str) -> bool:
    """Return False for private/loopback IPs to prevent SSRF via search results.

    Resolves hostnames via DNS so DNS-rebinding attacks (e.g. attacker.com → 10.0.0.1)
    are also blocked. Fails closed on resolution errors.
    """
    import ipaddress
    import socket
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if not host:
            return False

        def _is_safe_ip(ip_str: str) -> bool:
            try:
                addr = ipaddress.ip_address(ip_str)
                return (
                    addr.is_global
                    and not addr.is_private
                    and not addr.is_loopback
                    and not addr.is_link_local
                    and not addr.is_reserved
                )
            except ValueError:
                return False

        # Try literal IP first (no DNS needed)
        try:
            ipaddress.ip_address(host)
            return _is_safe_ip(host)
        except ValueError:
            pass  # Not a literal IP — resolve via DNS below

        # Block known-bad hostnames before DNS hit
        _BLOCKED_HOSTNAMES = {"localhost", "ip6-localhost", "ip6-loopback"}
        if host.lower() in _BLOCKED_HOSTNAMES:
            return False

        # Resolve hostname → IPs; fail closed if resolution fails or returns private IP
        try:
            results = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
            resolved_ips = {r[4][0] for r in results}
            return all(_is_safe_ip(ip) for ip in resolved_ips)
        except (socket.gaierror, OSError):
            # DNS resolution failed — fail closed (block)
            logger.warning("_is_safe_url: DNS resolution failed", extra={"host": host})
            return False

    except Exception:
        return False  # fail closed on any unexpected error


def _dt16(dt) -> str:
    """Format a datetime like the old Supabase ISO-string[:16] slices did. None-safe."""
    return dt.isoformat()[:16] if dt else "never"


def make_tools(arq_pool, tavily_api_key: str | None = None, anthropic_api_key: str | None = None) -> list:
    """Build and return all orchestrator tool callables."""

    @tool
    async def trigger_research(topic: Optional[str] = None) -> str:
        """Trigger the research agent to discover and scrape new articles.
        Optionally pass a topic hint (e.g. 'SEBI announcement') to guide research."""
        try:
            job = await arq_pool.enqueue_job("research_agent_task", topic=topic)
            job_id = job.job_id if job else "unknown"
            return f"Research agent enqueued (job_id={job_id}). Topic hint: {topic or 'none'}."
        except Exception as exc:
            logger.warning("trigger_research failed", extra={"error": str(exc)})
            return f"Error triggering research: {exc}"

    @tool
    async def trigger_scoring() -> str:
        """Trigger the scoring agent to generate content ideas from unprocessed articles."""
        try:
            job = await arq_pool.enqueue_job("scoring_agent_task")
            job_id = job.job_id if job else "unknown"
            return f"Scoring agent enqueued (job_id={job_id})."
        except Exception as exc:
            logger.warning("trigger_scoring failed", extra={"error": str(exc)})
            return f"Error triggering scoring: {exc}"

    @tool
    async def login_to_site(site_url: str) -> str:
        """Open a browser window so the user can log in to a paywalled site.
        A visible browser will appear on this machine — log in normally.
        The session (cookies) is saved automatically; all future scrapes for this
        domain will use it without asking you to log in again.
        site_url: full URL to open, e.g. https://www.livemint.com or https://economictimes.com/login"""
        try:
            if not _is_safe_url(site_url):
                return f"Error: Cannot open browser for private/internal URL '{site_url}'."
            domain = urlparse(site_url).netloc.lstrip("www.")
            job = await arq_pool.enqueue_job("login_site_task", login_url=site_url)
            job_id = job.job_id if job else "unknown"
            return (
                f"Browser opening for {domain} (job_id={job_id}). "
                f"A browser window will appear — log in there. "
                f"Your session is saved automatically; you won't need to log in again unless it expires."
            )
        except Exception as exc:
            logger.warning("login_to_site failed", extra={"error": str(exc)})
            return f"Error opening browser for login: {exc}"

    _VALID_CONTENT_TYPES = {"news_driven", "kb_driven", "combined"}

    @tool
    async def trigger_creation(idea_ids: list[str], content_type: str = "combined") -> str:
        """Trigger the creation agent to generate drafts for approved ideas.
        idea_ids: list of approved idea UUID strings.
        content_type: one of 'news_driven' (article context only),
          'kb_driven' (knowledge-base context only), or
          'combined' (article + KB context, default)."""
        if not idea_ids:
            return "Error: idea_ids must not be empty."
        if content_type not in _VALID_CONTENT_TYPES:
            return (
                f"Error: invalid content_type '{content_type}'. "
                f"Must be one of: {', '.join(sorted(_VALID_CONTENT_TYPES))}."
            )
        try:
            job = await arq_pool.enqueue_job(
                "creation_agent_task",
                idea_ids=idea_ids,
                content_type=content_type,
            )
            job_id = job.job_id if job else "unknown"
            return (
                f"Creation agent enqueued for {len(idea_ids)} idea(s) "
                f"(job_id={job_id}, content_type={content_type})."
            )
        except Exception as exc:
            logger.warning("trigger_creation failed", extra={"error": str(exc)})
            return f"Error triggering creation: {exc}"

    @tool
    def get_analytics_summary() -> str:
        """Return last 5 run logs and average performance per platform from content analytics."""
        try:
            from app.db.orm import ContentAnalytics
            with session_scope() as db:
                logs = db.execute(
                    select(RunLog).order_by(RunLog.created_at.desc()).limit(5)
                ).scalars().all()
                analytics_rows = db.execute(select(ContentAnalytics).limit(100)).scalars().all()

                lines = ["=== Recent Runs ==="]
                for log in logs:
                    cost = log.token_cost or {}
                    total_usd = cost.get("total_usd", 0)
                    lines.append(
                        f"{log.agent_name} | success={log.success_count} "
                        f"fail={log.failure_count} | ${total_usd:.4f} | {_dt16(log.created_at)}"
                    )

                platform_scores: dict[str, list[float]] = {}
                for row in analytics_rows:
                    if row.performance_score is not None:
                        platform_scores.setdefault(row.platform, []).append(row.performance_score)

                if platform_scores:
                    lines.append("\n=== Platform Averages ===")
                    for platform, scores in sorted(platform_scores.items()):
                        avg = sum(scores) / len(scores)
                        lines.append(f"{platform}: avg score={avg:.2f} ({len(scores)} posts)")

                return "\n".join(lines)
        except Exception as exc:
            logger.warning("get_analytics_summary failed", extra={"error": str(exc)})
            return f"Error fetching analytics: {exc}"

    @tool
    def add_curated_site(name: str, url: str, threshold: float = 4.0) -> str:
        """Add a new curated news site to the research pipeline.
        name: display name (e.g. 'ET Markets'). url: full section URL. threshold: pre-score threshold 1.0-10.0."""
        try:
            parsed = urlparse(url)
            if not (parsed.scheme in ("http", "https") and parsed.netloc):
                return f"Error: Invalid URL '{url}'. Must start with http:// or https://."
        except Exception:
            return f"Error: Invalid URL '{url}'."
        if not _is_safe_url(url):
            return f"Error: URL '{url}' resolves to a private/internal address and cannot be added."

        try:
            with session_scope() as db:
                site = CuratedSite(
                    site_name=name,
                    section_url=url,
                    active=True,
                    pre_score_threshold=threshold,
                    consecutive_failures=0,
                )
                db.add(site)
                db.flush()
                site_id = str(site.id)
            return f"Added curated site '{name}' (id={site_id}, threshold={threshold})."
        except Exception as exc:
            logger.warning("add_curated_site failed", extra={"error": str(exc)})
            return f"Error adding site: {exc}"

    @tool
    def remove_curated_site(site_name: str) -> str:
        """Deactivate a curated site by name (soft delete — sets active=false).
        The site will no longer be scraped in future research runs."""
        try:
            with session_scope() as db:
                site = db.execute(select(CuratedSite).where(CuratedSite.site_name == site_name)).scalar_one_or_none()
                if site is None:
                    return f"No site named '{site_name}' found."
                site.active = False
            return f"Site '{site_name}' has been deactivated and will no longer be scraped."
        except Exception as exc:
            logger.warning("remove_curated_site failed", extra={"error": str(exc)})
            return f"Error removing site: {exc}"

    @tool
    def list_curated_sites() -> str:
        """List all curated news sites with their active status, failure count, and last run time."""
        try:
            with session_scope() as db:
                sites = db.execute(select(CuratedSite).order_by(CuratedSite.site_name)).scalars().all()
                if not sites:
                    return "No curated sites configured."
                lines = []
                for s in sites:
                    status = "ACTIVE" if s.active else "INACTIVE"
                    lines.append(
                        f"[{status}] {s.site_name} | threshold={s.pre_score_threshold} "
                        f"| failures={s.consecutive_failures} | last_run={_dt16(s.last_run_at)}"
                    )
                return f"{len(sites)} curated site(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("list_curated_sites failed", extra={"error": str(exc)})
            return f"Error listing sites: {exc}"

    @tool
    def get_topic_performance() -> str:
        """Return all topic categories ranked by performance score from the topic_performance_model."""
        try:
            with session_scope() as db:
                rows = db.execute(
                    select(TopicPerformanceModel).order_by(TopicPerformanceModel.performance_score.desc())
                ).scalars().all()
                if not rows:
                    return "No topic performance data yet."
                lines = [
                    f"{r.topic_category}: score={r.performance_score:.2f} ({r.sample_count} samples)"
                    for r in rows
                ]
                return "Topic performance (best to worst):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("get_topic_performance failed", extra={"error": str(exc)})
            return f"Error fetching topic performance: {exc}"

    @tool
    def get_run_logs(limit: int = 5) -> str:
        """Return the last N agent run logs with timing, cost, and success/failure counts."""
        try:
            with session_scope() as db:
                rows = db.execute(
                    select(RunLog).order_by(RunLog.created_at.desc()).limit(limit)
                ).scalars().all()
                if not rows:
                    return "No run logs found."
                lines = []
                for r in rows:
                    cost = r.token_cost or {}
                    total_usd = cost.get("total_usd", 0)
                    duration = f"{r.duration_seconds:.1f}s" if r.duration_seconds is not None else "?s"
                    lines.append(
                        f"{_dt16(r.created_at)} | {r.agent_name} ({r.trigger_type}) "
                        f"| ok={r.success_count} fail={r.failure_count} "
                        f"| {duration} | ${total_usd:.4f}"
                    )
                return f"Last {len(rows)} run log(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("get_run_logs failed", extra={"error": str(exc)})
            return f"Error fetching run logs: {exc}"

    # ── Ideas (Gate 1) ──────────────────────────────────────────────────────

    @tool
    async def get_ideas(
        status: str = "pending_approval",
        platform: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        """Browse content ideas. status: 'pending_approval', 'approved', or 'rejected'.
        Optionally filter by platform (linkedin, twitter, blog, email).
        Returns id, angle, platform, score, and date for each idea."""
        try:
            with session_scope() as db:
                stmt = select(Idea).where(Idea.approval_status == status).order_by(Idea.score.desc()).limit(limit)
                if platform:
                    stmt = stmt.where(Idea.platform == platform)
                ideas = db.execute(stmt).scalars().all()
                if not ideas:
                    return f"No {status.replace('_', ' ')} ideas found."
                lines = []
                for i in ideas:
                    score = f"score={i.score:.1f}" if isinstance(i.score, (int, float)) else "score=?"
                    lines.append(f"[{i.platform}] {score} | {i.angle}\n  id: {i.id}")
                return f"{len(ideas)} {status.replace('_', ' ')} idea(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("get_ideas failed", extra={"error": str(exc)})
            return f"Error fetching ideas: {exc}"

    @tool
    async def approve_idea(idea_id: str, edited_angle: Optional[str] = None) -> str:
        """Approve a Gate 1 idea. Optionally provide an edited_angle to refine the angle before approving.
        idea_id: the UUID of the idea (from get_ideas output)."""
        try:
            with session_scope() as db:
                idea = db.get(Idea, idea_id)
                if idea is None:
                    return f"Idea {idea_id!r} not found."
                idea.approval_status = "approved"
                if edited_angle:
                    idea.edited_angle = edited_angle
                angle = idea.edited_angle or idea.angle
            return f"✓ Approved idea: {angle!r}"
        except Exception as exc:
            logger.warning("approve_idea failed", extra={"idea_id": idea_id, "error": str(exc)})
            return f"Error approving idea: {exc}"

    @tool
    async def reject_idea(idea_id: str) -> str:
        """Reject a Gate 1 idea.
        idea_id: the UUID of the idea (from get_ideas output)."""
        try:
            with session_scope() as db:
                idea = db.get(Idea, idea_id)
                if idea is None:
                    return f"Idea {idea_id!r} not found."
                idea.approval_status = "rejected"
            return f"✓ Rejected idea {idea_id[:8]}…"
        except Exception as exc:
            logger.warning("reject_idea failed", extra={"idea_id": idea_id, "error": str(exc)})
            return f"Error rejecting idea: {exc}"

    @tool
    async def bulk_reject_ideas(idea_ids: list[str]) -> str:
        """Reject multiple ideas at once. ALWAYS confirm the list with the user before calling this.
        idea_ids: list of UUID strings from get_ideas output."""
        if not idea_ids:
            return "Error: idea_ids must not be empty."
        count = 0
        errors = []
        for idea_id in idea_ids:
            try:
                with session_scope() as db:
                    idea = db.get(Idea, idea_id)
                    if idea is not None:
                        idea.approval_status = "rejected"
                        count += 1
            except Exception as exc:
                errors.append(f"{idea_id[:8]}: {exc}")
        result = f"✓ Rejected {count}/{len(idea_ids)} idea(s)."
        if errors:
            result += f"\nFailed: {'; '.join(errors)}"
        return result

    @tool
    async def send_ideas_to_creation(
        idea_ids: list[str],
        content_type: str = "news_driven",
    ) -> str:
        """Send approved ideas to the creation agent to generate drafts.
        content_type: 'news_driven', 'kb_driven', or 'combined'.
        idea_ids: list of approved idea UUIDs."""
        if not idea_ids:
            return "Error: idea_ids must not be empty."
        if content_type not in {"news_driven", "kb_driven", "combined"}:
            return f"Error: invalid content_type '{content_type}'. Use: news_driven, kb_driven, combined."
        if arq_pool is None:
            return "Error: job queue unavailable (Redis not connected)."
        try:
            job = await arq_pool.enqueue_job(
                "creation_agent_task",
                idea_ids=idea_ids,
                content_type=content_type,
            )
            job_id = job.job_id if job else "unknown"
            return (
                f"✓ Creation queued for {len(idea_ids)} idea(s) "
                f"(content_type={content_type}, job_id={job_id})."
            )
        except Exception as exc:
            logger.warning("send_ideas_to_creation failed", extra={"error": str(exc)})
            return f"Error triggering creation: {exc}"

    @tool
    async def retry_failed_drafts(content_type: str = "news_driven") -> str:
        """Retry draft generation for all ideas where draft creation previously failed.
        Finds ideas with draft_status='failed' and re-queues them for the creation agent."""
        if arq_pool is None:
            return "Error: job queue unavailable (Redis not connected)."
        try:
            with session_scope() as db:
                failed = db.execute(
                    select(Idea.id).where(Idea.draft_status == "failed", Idea.approval_status == "approved")
                ).scalars().all()
                failed_ids = [str(i) for i in failed]
                if not failed_ids:
                    return "No failed draft ideas found."
                db.execute(
                    Idea.__table__.update()
                    .where(Idea.id.in_(failed))
                    .values(draft_status="pending")
                )
            job = await arq_pool.enqueue_job(
                "creation_agent_task",
                idea_ids=failed_ids,
                content_type=content_type,
            )
            job_id = job.job_id if job else "unknown"
            return (
                f"✓ Retrying draft generation for {len(failed_ids)} failed idea(s) "
                f"(job_id={job_id}). Check /drafts when complete."
            )
        except Exception as exc:
            logger.warning("retry_failed_drafts failed", extra={"error": str(exc)})
            return f"Error: {exc}"

    # ── Drafts (Gate 2) ─────────────────────────────────────────────────────

    @tool
    async def get_drafts(
        status: str = "pending_approval",
        platform: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        """Browse content drafts. status: 'pending_approval', 'approved', or 'rejected'.
        Shows platform, preview of content, finance flags, and date."""
        try:
            with session_scope() as db:
                stmt = select(Draft).where(Draft.approval_status == status).order_by(Draft.created_at.desc()).limit(limit)
                if platform:
                    stmt = stmt.where(Draft.platform == platform)
                drafts = db.execute(stmt).scalars().all()
                if not drafts:
                    return f"No {status.replace('_', ' ')} drafts found."
                lines = []
                for d in drafts:
                    preview = (d.content_text or "")[:120].replace("\n", " ")
                    flags = d.finance_flags or []
                    flag_str = f" ⚠ {len(flags)} flag(s)" if flags else ""
                    lines.append(f"[{d.platform}]{flag_str} | {preview}…\n  id: {d.id}")
                return f"{len(drafts)} {status.replace('_', ' ')} draft(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("get_drafts failed", extra={"error": str(exc)})
            return f"Error fetching drafts: {exc}"

    @tool
    async def approve_draft(draft_id: str, scheduled_at: Optional[str] = None) -> str:
        """Approve a Gate 2 draft for publishing.
        draft_id: UUID from get_drafts output.
        scheduled_at: optional ISO datetime string (e.g. '2026-06-02T09:00:00+05:30')."""
        try:
            with session_scope() as db:
                draft = db.get(Draft, draft_id)
                if draft is None:
                    return f"Draft {draft_id!r} not found."
                draft.approval_status = "approved"
                if scheduled_at:
                    draft.scheduled_at = scheduled_at
            sched = f" (scheduled: {scheduled_at})" if scheduled_at else ""
            return f"✓ Approved draft {draft_id[:8]}…{sched}"
        except Exception as exc:
            logger.warning("approve_draft failed", extra={"draft_id": draft_id, "error": str(exc)})
            return f"Error approving draft: {exc}"

    @tool
    async def reject_draft(draft_id: str) -> str:
        """Reject a Gate 2 draft.
        draft_id: UUID from get_drafts output."""
        try:
            with session_scope() as db:
                draft = db.get(Draft, draft_id)
                if draft is None:
                    return f"Draft {draft_id!r} not found."
                draft.approval_status = "rejected"
            return f"✓ Rejected draft {draft_id[:8]}…"
        except Exception as exc:
            logger.warning("reject_draft failed", extra={"draft_id": draft_id, "error": str(exc)})
            return f"Error rejecting draft: {exc}"

    # ── Brand memory ─────────────────────────────────────────────────────────

    @tool
    async def add_brand_memory(content: str, platform: str) -> str:
        """Save a piece of brand content (e.g. a LinkedIn post you wrote) as a style reference.
        The creation agent will use these examples to match your brand voice when generating new posts.
        platform: 'linkedin', 'twitter', 'blog', or 'email'."""
        try:
            from app.config import get_settings
            from app.agents.embedding.client import make_embed_client
            _settings = get_settings()
            _embed = make_embed_client(
                google_api_key=_settings.google_api_key,
                local_model=_settings.local_embedding_model,
            )
            embedding = _embed.embed_one(content)
            with session_scope() as db:
                bm = BrandMemory(
                    content=content,
                    platform=platform,
                    performance_metrics={},
                    embedding=embedding or None,
                )
                db.add(bm)
                db.flush()
                bm_id = str(bm.id)
            embedded = "with embedding" if embedding else "without embedding (embedder unavailable)"
            return f"Saved to brand memory for {platform} {embedded} (id={bm_id[:8]}...)"
        except Exception as exc:
            logger.warning("add_brand_memory failed", extra={"error": str(exc)})
            return f"Error adding brand memory: {exc}"

    @tool
    async def list_brand_memory(platform: Optional[str] = None, limit: int = 5) -> str:
        """List recent brand memory posts used as style reference by the creation agent.
        Optionally filter by platform."""
        try:
            with session_scope() as db:
                stmt = select(BrandMemory).order_by(BrandMemory.created_at.desc()).limit(limit)
                if platform:
                    stmt = stmt.where(BrandMemory.platform == platform)
                rows = db.execute(stmt).scalars().all()
                if not rows:
                    return "No brand memory entries found."
                lines = [
                    f"[{r.platform}] {(r.content or '')[:100]}...\n  id: {r.id}"
                    for r in rows
                ]
                return f"{len(rows)} brand memory entry(ies):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("list_brand_memory failed", extra={"error": str(exc)})
            return f"Error listing brand memory: {exc}"

    # ── Email subscribers ─────────────────────────────────────────────────────

    @tool
    async def list_subscribers(limit: int = 10) -> str:
        """List active email subscribers."""
        try:
            with session_scope() as db:
                rows = db.execute(
                    select(EmailSubscriber)
                    .where(EmailSubscriber.active.is_(True))
                    .order_by(EmailSubscriber.created_at.desc())
                    .limit(limit)
                ).scalars().all()
                if not rows:
                    return "No active subscribers found."
                lines = [f"{r.name or '—'} <{r.email}>" for r in rows]
                return f"{len(rows)} active subscriber(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("list_subscribers failed", extra={"error": str(exc)})
            return f"Error listing subscribers: {exc}"

    @tool
    async def add_email_subscriber(email: str, name: Optional[str] = None) -> str:
        """Add a new email subscriber.
        email: valid email address. name: optional display name."""
        import uuid as _uuid
        try:
            with session_scope() as db:
                sub = EmailSubscriber(
                    email=email,
                    name=name or None,
                    active=True,
                    unsubscribe_token=str(_uuid.uuid4()),
                )
                db.add(sub)
            return f"✓ Added subscriber: {email}"
        except Exception as exc:
            logger.warning("add_email_subscriber failed", extra={"email": email, "error": str(exc)})
            return f"Error adding subscriber: {exc}"

    @tool
    async def remove_email_subscriber(email: str) -> str:
        """Deactivate (soft-delete) an email subscriber by email address."""
        try:
            with session_scope() as db:
                sub = db.execute(select(EmailSubscriber).where(EmailSubscriber.email == email)).scalar_one_or_none()
                if sub is None:
                    return f"No subscriber found with email {email!r}."
                sub.active = False
            return f"Removed subscriber: {email}"
        except Exception as exc:
            logger.warning("remove_email_subscriber failed", extra={"email": email, "error": str(exc)})
            return f"Error removing subscriber: {exc}"

    # ── Content browsing ──────────────────────────────────────────────────────

    @tool
    async def get_decision_summaries(limit: int = 5) -> str:
        """Show recent rejection pattern summaries — AI-generated analyses of why ideas were rejected.
        Useful for understanding what content to avoid."""
        try:
            with session_scope() as db:
                rows = db.execute(
                    select(UserDecisionSummary).order_by(UserDecisionSummary.created_at.desc()).limit(limit)
                ).scalars().all()
                if not rows:
                    return "No decision summaries yet."
                lines = [
                    f"[{r.created_at.isoformat()[:10]}] ({r.rejection_count} rejections)\n{r.summary_text}"
                    for r in rows
                ]
                return "\n\n".join(lines)
        except Exception as exc:
            logger.warning("get_decision_summaries failed", extra={"error": str(exc)})
            return f"Error fetching decision summaries: {exc}"

    @tool
    async def get_recent_articles(limit: int = 5, source_name: Optional[str] = None) -> str:
        """Browse recently scraped articles from the research pipeline.
        Optionally filter by source_name (e.g. 'ET Markets', 'LiveMint')."""
        try:
            with session_scope() as db:
                stmt = select(RawContent).order_by(RawContent.created_at.desc()).limit(limit)
                if source_name:
                    stmt = stmt.where(RawContent.source_name == source_name)
                rows = db.execute(stmt).scalars().all()
                if not rows:
                    return "No articles found."
                lines = [
                    f"[{r.source_name}] score={r.pre_score if r.pre_score is not None else '?'} | {r.title}\n  {r.url[:80]}"
                    for r in rows
                ]
                return f"{len(rows)} article(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("get_recent_articles failed", extra={"error": str(exc)})
            return f"Error fetching articles: {exc}"

    @tool
    async def get_published_posts(platform: Optional[str] = None, limit: int = 5) -> str:
        """Show recently published posts. Optionally filter by platform."""
        try:
            with session_scope() as db:
                stmt = select(PublishedPost).order_by(PublishedPost.published_at.desc()).limit(limit)
                if platform:
                    stmt = stmt.where(PublishedPost.platform == platform)
                rows = db.execute(stmt).scalars().all()
                if not rows:
                    return "No published posts found."
                # published_posts has no content column — show the platform post
                # identifier instead (the old Supabase query referenced a
                # content_preview column that never existed in any migration
                # and always errored; this is the corrected version).
                lines = [
                    f"[{r.platform}] {r.published_at.isoformat()[:10]} | post_identifier={r.post_identifier}"
                    for r in rows
                ]
                return f"{len(rows)} published post(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("get_published_posts failed", extra={"error": str(exc)})
            return f"Error fetching published posts: {exc}"

    @tool
    async def list_kb_files() -> str:
        """List knowledge base files that have been uploaded and chunked for retrieval."""
        try:
            with session_scope() as db:
                rows = db.execute(
                    select(KnowledgeBase.source_file).order_by(KnowledgeBase.source_file)
                ).scalars().all()
                if not rows:
                    return "No knowledge base files uploaded."
                files: dict[str, int] = {}
                for source_file in rows:
                    files[source_file] = files.get(source_file, 0) + 1
                lines = [f"{fname} ({count} chunks)" for fname, count in files.items()]
                return f"{len(files)} KB file(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("list_kb_files failed", extra={"error": str(exc)})
            return f"Error listing KB files: {exc}"

    # ── Web search ───────────────────────────────────────────────────────────

    @tool
    async def search_web(query: str, max_results: int = 3) -> str:
        """Search the web for current information on a topic.
        Uses Tavily (if configured) or DuckDuckGo as fallback.
        Returns URLs, titles, and brief snippets — use search_and_scrape for full content."""
        results = (
            _tavily_search(query, tavily_api_key, max_results)
            if tavily_api_key
            else _duckduckgo_search(query, max_results)
        )
        if not results:
            return f"No search results found for: {query!r}"
        lines = [
            f"{i+1}. {r['title']}\n   {r['url']}\n   {r['snippet'][:120]}"
            for i, r in enumerate(results)
        ]
        return f"Search results for '{query}':\n\n" + "\n\n".join(lines)

    @tool
    async def search_and_scrape(query: str, max_results: int = 3) -> str:
        """Search the web AND scrape full article text from results.
        Use this as the grounding step before generate_post to get current, accurate information.
        Returns combined article text ready to use as source material."""
        results = (
            _tavily_search(query, tavily_api_key, max_results)
            if tavily_api_key
            else _duckduckgo_search(query, max_results)
        )
        if not results:
            return f"No search results found for: {query!r}"

        articles = []
        for r in results:
            url = r.get("url", "")
            if not url or not _is_safe_url(url):
                continue
            content = _fetch_article_sync(url)
            if content is None or content.paywall_detected or content.word_count < 50:
                continue
            snippet = content.full_text[:2500]
            articles.append(f"Source: {r['title']} ({url})\n{snippet}")

        if not articles:
            return (
                f"Found {len(results)} search result(s) for '{query}' but "
                f"all were paywalled or empty. Try a different query or provide context manually."
            )
        return (
            f"Scraped {len(articles)} article(s) for '{query}':\n\n"
            + "\n\n---\n\n".join(articles)
        )

    @tool
    async def generate_post(
        topic: str,
        platform: str = "linkedin",
        content_type: str = "news_driven",
    ) -> str:
        """Generate a social media post on demand using web search + brand voice.

        Workflow: (1) search_and_scrape for current info on the topic,
        (2) fetch brand voice examples from brand_memory,
        (3) call Claude to write the post in brand voice.
        The draft is returned in chat — say 'save this' to persist it.

        platform: 'linkedin', 'twitter', 'blog', or 'email'
        content_type: 'news_driven' (use article facts), 'kb_driven' (use KB docs), 'combined'"""
        if not anthropic_api_key:
            return "Error: ANTHROPIC_API_KEY not configured."

        # Step 1 — Get current information
        scraped = (
            _tavily_search(topic, tavily_api_key, 3)
            if tavily_api_key
            else _duckduckgo_search(topic, 3)
        )
        article_text = ""
        for r in scraped:
            url = r.get("url", "")
            if not url or not _is_safe_url(url):
                continue
            content = _fetch_article_sync(url)
            if content and not content.paywall_detected and content.word_count >= 50:
                article_text += f"\n\nSource: {r['title']}\n{content.full_text[:2000]}"
                break  # one good article is enough for generation

        if not article_text:
            return (
                f"Error: Could not retrieve source material for '{topic}'. "
                f"Web search returned no accessible articles. "
                f"Please try a more specific query or provide source text directly."
            )

        # Step 2 — Get brand voice via embedding similarity (not just recency)
        examples: list[str] = []
        try:
            from app.config import get_settings as _gs
            from app.agents.embedding.client import make_embed_client as _mec
            _s = _gs()
            _ec = _mec(google_api_key=_s.google_api_key, local_model=_s.local_embedding_model)
            topic_vec = _ec.embed_one(topic)
            if topic_vec:
                with session_scope() as db:
                    rows = match_brand_memory(
                        db, topic_vec, match_count=3, filter_platform=platform, days_back=None
                    )
                    examples = [r["content"] for r in rows]
            else:
                raise ValueError("empty embedding")
        except Exception:
            # fallback: most recent 3
            try:
                with session_scope() as db:
                    fb = db.execute(
                        select(BrandMemory)
                        .where(BrandMemory.platform == platform)
                        .order_by(BrandMemory.created_at.desc())
                        .limit(3)
                    ).scalars().all()
                    examples = [r.content for r in fb]
            except Exception:
                examples = []
        brand_examples = (
            "Brand voice examples (match this style):\n\n" + "\n\n---\n\n".join(examples)
            if examples else ""
        )

        # Step 3 — Generate with Claude Sonnet for quality
        try:
            from anthropic import Anthropic
            from app.config import get_settings as _gs2
            _model = _gs2().claude_model_heavy
            client = Anthropic(api_key=anthropic_api_key)
            system = f"""You write educational Indian finance content for {platform}.
Write in the exact style and tone of the brand voice examples provided.
Rules: educational not advisory, no specific investment recommendations, add a disclaimer at the end,
use relevant hashtags for {platform}, keep it concise and engaging."""

            user_prompt = f"""Write a {platform} post about: {topic}

{brand_examples}

Source material (use facts from this, don't fabricate numbers):
{article_text[:3000]}

Write the full post now. Return only the post text, nothing else."""

            message = client.messages.create(
                model=_model,
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": user_prompt}],
            )
            from anthropic.types import TextBlock as _TextBlock
            first = message.content[0] if message.content else None
            post_text = first.text.strip() if isinstance(first, _TextBlock) else ""
            if not post_text:
                return "Error: Claude returned empty response."
            return (
                f"Generated {platform} post about '{topic}':\n\n"
                f"{post_text}\n\n"
                f"---\nSay 'save this as a draft' to save it, or ask me to revise it."
            )
        except Exception as exc:
            logger.warning("generate_post: Claude call failed", extra={"error": str(exc)})
            return f"Error generating post: {exc}"

    @tool
    async def save_draft(content: str, platform: str) -> str:
        """Save a generated post as a pending draft for review and approval.
        content: the full post text. platform: 'linkedin', 'twitter', 'blog', or 'email'."""
        try:
            with session_scope() as db:
                draft = Draft(
                    content_text=content,
                    platform=platform,
                    approval_status="pending_approval",
                    agent_reasoning="Generated on-demand via orchestrator",
                    finance_flags=[],
                )
                db.add(draft)
                db.flush()
                draft_id = str(draft.id)
            return (
                f"Saved as pending draft (id={draft_id[:8]}...). "
                f"Go to Gate 2 (Drafts) to review and approve it for publishing."
            )
        except Exception as exc:
            logger.warning("save_draft failed", extra={"error": str(exc)})
            return f"Error saving draft: {exc}"

    @tool
    def generate_macro_briefing(days_back: int = 7) -> str:
        """
        Synthesizes the last N days of processed articles into a high-level institutional macro briefing.
        Useful to summarize current market trends before generating complex content.
        """
        try:
            with session_scope() as db:
                articles = db.execute(
                    select(RawContent)
                    .where(RawContent.processed.is_(True))
                    .order_by(RawContent.created_at.desc())
                    .limit(20)
                ).scalars().all()
                if not articles:
                    return f"No processed articles found in the last {days_back} days."

                briefing = f"--- Macro Briefing (Last {days_back} days) ---\n"
                for a in articles:
                    summary = a.structured_summary or {}
                    narrative = summary.get("story_narrative", a.title)
                    implications = summary.get("implications", "")
                    briefing += f"\n- {narrative}\n  Impact: {implications}"

                return briefing
        except Exception as exc:
            return f"Error generating macro briefing: {str(exc)}"

    return [
        # Pipeline triggers
        trigger_research, trigger_scoring, generate_macro_briefing,
        # Ideas (Gate 1)
        get_ideas, approve_idea, reject_idea, bulk_reject_ideas, send_ideas_to_creation, retry_failed_drafts,
        # Drafts (Gate 2)
        get_drafts, approve_draft, reject_draft,
        # Brand & subscribers
        add_brand_memory, list_brand_memory,
        list_subscribers, add_email_subscriber, remove_email_subscriber,
        # Analytics & browsing
        get_analytics_summary, get_topic_performance, get_run_logs,
        get_decision_summaries, get_recent_articles, get_published_posts, list_kb_files,
        # Site management
        add_curated_site, remove_curated_site, list_curated_sites,
        # Auth
        login_to_site,
        # Web search & on-demand generation
        search_web, search_and_scrape, generate_post, save_draft,
    ]
