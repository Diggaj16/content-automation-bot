"""
LangGraph tool factory for the orchestrator agent.

Call make_tools(supabase, arq_pool) once at startup — tools receive
supabase and arq_pool via closure so callers don't need to pass them
as tool arguments (which would leak internal types into the LLM's context).
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from langchain_core.tools import tool
from supabase import Client

from app.utils.logging import get_logger

logger = get_logger(__name__)


def make_tools(supabase: Client, arq_pool) -> list:
    """Build and return all 19 orchestrator tool callables."""

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
            from urllib.parse import urlparse
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
    def get_pending_ideas(limit: int = 10) -> str:
        """Return up to `limit` ideas awaiting approval at Gate 1. Shows id, angle, platform, and score."""
        try:
            resp = (
                supabase.table("ideas")
                .select("id, angle, platform, score, created_at")
                .eq("approval_status", "pending_approval")
                .order("score", desc=True)
                .limit(limit)
                .execute()
            )
            ideas = resp.data or []
            if not ideas:
                return "No pending ideas at Gate 1."
            lines = [
                f"[{i['platform']}] score={i.get('score'):.1f} | {i['angle']} (id: {i['id']})"
                if isinstance(i.get('score'), (int, float))
                else f"[{i['platform']}] {i['angle']} (id: {i['id']})"
                for i in ideas
            ]
            return f"{len(ideas)} pending idea(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("get_pending_ideas failed", extra={"error": str(exc)})
            return f"Error fetching pending ideas: {exc}"

    @tool
    def get_analytics_summary() -> str:
        """Return last 5 run logs and average performance per platform from content analytics."""
        try:
            logs_resp = (
                supabase.table("run_logs")
                .select("agent_name, trigger_type, success_count, failure_count, duration_seconds, token_cost, created_at")
                .order("created_at", desc=True)
                .limit(5)
                .execute()
            )
            analytics_resp = (
                supabase.table("content_analytics")
                .select("platform, performance_score")
                .limit(100)
                .execute()
            )

            lines = ["=== Recent Runs ==="]
            for log in (logs_resp.data or []):
                cost = log.get("token_cost", {}) or {}
                total_usd = cost.get("total_usd", 0)
                lines.append(
                    f"{log['agent_name']} | success={log['success_count']} "
                    f"fail={log['failure_count']} | ${total_usd:.4f} | {log['created_at'][:16]}"
                )

            platform_scores: dict[str, list[float]] = {}
            for row in (analytics_resp.data or []):
                p = row["platform"]
                s = row.get("performance_score")
                if s is not None:
                    platform_scores.setdefault(p, []).append(s)

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

        try:
            resp = supabase.table("curated_sites").insert({
                "site_name": name,
                "section_url": url,
                "active": True,
                "pre_score_threshold": threshold,
                "consecutive_failures": 0,
            }).execute()
            if resp.data:
                site_id = resp.data[0].get("id", "unknown")
                return f"Added curated site '{name}' (id={site_id}, threshold={threshold})."
            return f"Added '{name}' but insert returned no data."
        except Exception as exc:
            logger.warning("add_curated_site failed", extra={"error": str(exc)})
            return f"Error adding site: {exc}"

    @tool
    def remove_curated_site(site_name: str) -> str:
        """Deactivate a curated site by name (soft delete — sets active=false).
        The site will no longer be scraped in future research runs."""
        try:
            resp = (
                supabase.table("curated_sites")
                .update({"active": False})
                .eq("site_name", site_name)
                .execute()
            )
            if not resp.data:
                return f"No site named '{site_name}' found."
            return f"Site '{site_name}' has been deactivated and will no longer be scraped."
        except Exception as exc:
            logger.warning("remove_curated_site failed", extra={"error": str(exc)})
            return f"Error removing site: {exc}"

    @tool
    def list_curated_sites() -> str:
        """List all curated news sites with their active status, failure count, and last run time."""
        try:
            resp = (
                supabase.table("curated_sites")
                .select("site_name, section_url, active, consecutive_failures, last_run_at, pre_score_threshold")
                .order("site_name")
                .execute()
            )
            sites = resp.data or []
            if not sites:
                return "No curated sites configured."
            lines = []
            for s in sites:
                status = "ACTIVE" if s.get("active") else "INACTIVE"
                last_run = s["last_run_at"][:16] if s.get("last_run_at") else "never"
                lines.append(
                    f"[{status}] {s['site_name']} | threshold={s.get('pre_score_threshold', 'n/a')} "
                    f"| failures={s.get('consecutive_failures', 0)} | last_run={last_run}"
                )
            return f"{len(sites)} curated site(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("list_curated_sites failed", extra={"error": str(exc)})
            return f"Error listing sites: {exc}"

    @tool
    def get_topic_performance() -> str:
        """Return all topic categories ranked by performance score from the topic_performance_model."""
        try:
            resp = (
                supabase.table("topic_performance_model")
                .select("topic_category, performance_score, sample_count, updated_at")
                .order("performance_score", desc=True)
                .execute()
            )
            rows = resp.data or []
            if not rows:
                return "No topic performance data yet."
            lines = []
            for r in rows:
                lines.append(
                    f"{r['topic_category']}: score={r['performance_score']:.2f} "
                    f"({r['sample_count']} samples)"
                )
            return "Topic performance (best to worst):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("get_topic_performance failed", extra={"error": str(exc)})
            return f"Error fetching topic performance: {exc}"

    @tool
    def get_run_logs(limit: int = 5) -> str:
        """Return the last N agent run logs with timing, cost, and success/failure counts."""
        try:
            resp = (
                supabase.table("run_logs")
                .select("agent_name, trigger_type, success_count, failure_count, duration_seconds, token_cost, created_at")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            rows = resp.data or []
            if not rows:
                return "No run logs found."
            lines = []
            for r in rows:
                cost = r.get("token_cost", {}) or {}
                total_usd = cost.get("total_usd", 0)
                lines.append(
                    f"{r['created_at'][:16]} | {r['agent_name']} ({r['trigger_type']}) "
                    f"| ok={r['success_count']} fail={r['failure_count']} "
                    f"| {r['duration_seconds']:.1f}s | ${total_usd:.4f}"
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
            query = (
                supabase.table("ideas")
                .select("id, angle, platform, score, approval_status, created_at")
                .eq("approval_status", status)
                .order("score", desc=True)
                .limit(limit)
            )
            if platform:
                query = query.eq("platform", platform)
            resp = query.execute()
            ideas = resp.data or []
            if not ideas:
                return f"No {status.replace('_', ' ')} ideas found."
            lines = []
            for i in ideas:
                score = f"score={i['score']:.1f}" if isinstance(i.get('score'), (int, float)) else "score=?"
                lines.append(
                    f"[{i['platform']}] {score} | {i['angle']}\n  id: {i['id']}"
                )
            return f"{len(ideas)} {status.replace('_', ' ')} idea(s):\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("get_ideas failed", extra={"error": str(exc)})
            return f"Error fetching ideas: {exc}"

    @tool
    async def approve_idea(idea_id: str, edited_angle: Optional[str] = None) -> str:
        """Approve a Gate 1 idea. Optionally provide an edited_angle to refine the angle before approving.
        idea_id: the UUID of the idea (from get_ideas output)."""
        try:
            payload: dict = {"approval_status": "approved"}
            if edited_angle:
                payload["edited_angle"] = edited_angle
            resp = supabase.table("ideas").update(payload).eq("id", idea_id).execute()
            if not resp.data:
                return f"Idea {idea_id!r} not found."
            angle = resp.data[0].get("angle") or resp.data[0].get("edited_angle") or idea_id
            return f"✓ Approved idea: {angle!r}"
        except Exception as exc:
            logger.warning("approve_idea failed", extra={"idea_id": idea_id, "error": str(exc)})
            return f"Error approving idea: {exc}"

    @tool
    async def reject_idea(idea_id: str) -> str:
        """Reject a Gate 1 idea.
        idea_id: the UUID of the idea (from get_ideas output)."""
        try:
            resp = supabase.table("ideas").update({"approval_status": "rejected"}).eq("id", idea_id).execute()
            if not resp.data:
                return f"Idea {idea_id!r} not found."
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
                supabase.table("ideas").update({"approval_status": "rejected"}).eq("id", idea_id).execute()
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
            query = (
                supabase.table("drafts")
                .select("id, platform, content_text, finance_flags, approval_status, created_at")
                .eq("approval_status", status)
                .order("created_at", desc=True)
                .limit(limit)
            )
            if platform:
                query = query.eq("platform", platform)
            resp = query.execute()
            drafts = resp.data or []
            if not drafts:
                return f"No {status.replace('_', ' ')} drafts found."
            lines = []
            for d in drafts:
                preview = (d.get("content_text") or "")[:120].replace("\n", " ")
                flags = d.get("finance_flags") or []
                flag_str = f" ⚠ {len(flags)} flag(s)" if flags else ""
                lines.append(
                    f"[{d['platform']}]{flag_str} | {preview}…\n  id: {d['id']}"
                )
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
            payload: dict = {"approval_status": "approved"}
            if scheduled_at:
                payload["scheduled_at"] = scheduled_at
            resp = supabase.table("drafts").update(payload).eq("id", draft_id).execute()
            if not resp.data:
                return f"Draft {draft_id!r} not found."
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
            resp = supabase.table("drafts").update({"approval_status": "rejected"}).eq("id", draft_id).execute()
            if not resp.data:
                return f"Draft {draft_id!r} not found."
            return f"✓ Rejected draft {draft_id[:8]}…"
        except Exception as exc:
            logger.warning("reject_draft failed", extra={"draft_id": draft_id, "error": str(exc)})
            return f"Error rejecting draft: {exc}"

    return [
        # Pipeline triggers
        trigger_research,
        trigger_scoring,
        trigger_creation,
        # Ideas (Gate 1)
        get_ideas,
        approve_idea,
        reject_idea,
        bulk_reject_ideas,
        send_ideas_to_creation,
        # Drafts (Gate 2)
        get_drafts,
        approve_draft,
        reject_draft,
        # Analytics & browsing
        get_analytics_summary,
        get_topic_performance,
        get_run_logs,
        # Site management
        add_curated_site,
        remove_curated_site,
        list_curated_sites,
        # Auth
        login_to_site,
        # Legacy
        get_pending_ideas,
    ]
