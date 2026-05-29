from datetime import datetime, timezone, date
from uuid import uuid4

import pytest

from app.db.models import (
    Platform, ApprovalStatus, DraftStatus, TriggerType, MeasurementPeriod,
    SubscriberSource,
    CuratedSiteCreate,
    StructuredSummary, RawContentCreate,
    IdeaCreate, IdeaApproval,
    FinanceFlag, DraftCreate, DraftApproval,
    PublishedPostCreate,
    LinkedInMetrics, TwitterMetrics, BlogMetrics, ContentAnalyticsCreate,
    EmailSubscriberCreate,
    StyleGuideInsights,
    TopicPerformanceUpsert,
    BrandMemoryCreate,
    KnowledgeBaseChunkCreate,
    RunLogCreate,
    SiteHealthLogCreate,
    CostLogUpsert,
)


# ── Enums ─────────────────────────────────────────────────────────────────────

def test_platform_values():
    assert Platform.LINKEDIN == "linkedin"
    assert Platform.TWITTER  == "twitter"
    assert Platform.BLOG     == "blog"
    assert Platform.EMAIL    == "email"


def test_approval_status_values():
    assert ApprovalStatus.PENDING  == "pending_approval"
    assert ApprovalStatus.APPROVED == "approved"
    assert ApprovalStatus.REJECTED == "rejected"


def test_draft_status_includes_published_and_failed():
    assert DraftStatus.PUBLISHED == "published"
    assert DraftStatus.FAILED    == "failed"


def test_trigger_type_values():
    assert TriggerType.CRON         == "cron"
    assert TriggerType.EVENT        == "event"
    assert TriggerType.MANUAL       == "manual"
    assert TriggerType.ORCHESTRATOR == "orchestrator"


def test_measurement_period_values():
    assert MeasurementPeriod.H24 == "24h"
    assert MeasurementPeriod.H72 == "72h"
    assert MeasurementPeriod.D7  == "7d"


# ── CuratedSite ───────────────────────────────────────────────────────────────

def test_curated_site_create_defaults():
    site = CuratedSiteCreate(
        site_name="LiveMint Stock Market",
        section_url="https://www.livemint.com/market/stock-market-news",
    )
    assert site.active is True
    assert site.pre_score_threshold == 4.0


def test_curated_site_create_high_threshold():
    site = CuratedSiteCreate(
        site_name="LiveMint India News",
        section_url="https://www.livemint.com/news/india",
        pre_score_threshold=6.0,
    )
    assert site.pre_score_threshold == 6.0


# ── RawContent ────────────────────────────────────────────────────────────────

def test_structured_summary():
    s = StructuredSummary(
        story_narrative="SEBI banned X.",
        key_data_points=["₹500 crore fine", "effective 1 June 2026"],
        mechanism="Regulatory action triggered by audit findings.",
        implications="Retail investors face higher transaction costs.",
        content_angles=["Why this hurts retail more than institutions"],
    )
    assert len(s.key_data_points) == 2
    assert len(s.content_angles) == 1


def test_raw_content_create_defaults():
    rc = RawContentCreate(
        url="https://livemint.com/article/123",
        normalized_url="livemint.com/article/123",
        title="SEBI bans X",
        source_name="LiveMint",
        full_text="Full article text here.",
    )
    assert rc.vision_fallback_used is False
    assert rc.paywall_detected is False
    assert rc.word_count == 0
    assert rc.publication_date is None


# ── Idea ──────────────────────────────────────────────────────────────────────

def test_idea_create():
    idea = IdeaCreate(
        platform=Platform.LINKEDIN,
        angle="Why SEBI's new F&O rules will hurt retail traders more than protect them",
        agent_reasoning="Unexpectedness 9/10",
        score=8.5,
    )
    assert idea.platform == Platform.LINKEDIN
    assert idea.score == 8.5
    assert idea.recent_coverage_flag is False


def test_idea_approval_with_edit():
    approval = IdeaApproval(
        approval_status=ApprovalStatus.APPROVED,
        edited_angle="SEBI F&O rules: protection framing vs retail reality",
    )
    assert approval.edited_angle is not None


def test_idea_rejection_no_edit():
    rejection = IdeaApproval(approval_status=ApprovalStatus.REJECTED)
    assert rejection.edited_angle is None


# ── Draft ─────────────────────────────────────────────────────────────────────

def test_draft_create_with_finance_flags():
    flag = FinanceFlag(
        flag_type="financial_figure",
        content="₹500 crore",
        context="The regulator imposed a ₹500 crore fine.",
    )
    draft = DraftCreate(
        platform=Platform.LINKEDIN,
        content_text="Post body here.",
        agent_reasoning="Contrarian framing from style guide.",
        finance_flags=[flag],
    )
    assert len(draft.finance_flags) == 1
    assert draft.finance_flags[0].flag_type == "financial_figure"


def test_draft_create_no_flags_by_default():
    draft = DraftCreate(
        platform=Platform.TWITTER,
        content_text="Short tweet.",
        agent_reasoning="News-driven punchy claim.",
    )
    assert draft.finance_flags == []


# ── Analytics ─────────────────────────────────────────────────────────────────

def test_linkedin_metrics_defaults():
    m = LinkedInMetrics()
    assert m.impressions == 0 and m.reactions == 0


def test_twitter_metrics_defaults():
    m = TwitterMetrics()
    assert m.bookmarks == 0


def test_blog_metrics_defaults():
    m = BlogMetrics()
    assert m.avg_engagement_time_seconds == 0.0


def test_content_analytics_create():
    ca = ContentAnalyticsCreate(
        post_id=uuid4(),
        platform="linkedin",
        measurement_period=MeasurementPeriod.D7,
        metrics=LinkedInMetrics(impressions=5000, reactions=120).model_dump(),
        performance_score=0.72,
    )
    assert ca.measurement_period == MeasurementPeriod.D7
    assert ca.metrics["impressions"] == 5000


# ── RunLog ────────────────────────────────────────────────────────────────────

def test_run_log_create():
    log = RunLogCreate(
        agent_name="research_agent",
        trigger_type=TriggerType.CRON,
        processed_count=40,
        success_count=38,
        failure_count=2,
        duration_seconds=187.3,
        reasoning_trace="Processed 7 sites.",
        token_cost={"input_tokens": 12000, "output_tokens": 4000, "model": "claude-haiku-4-5"},
    )
    assert log.failure_count == 2
    assert log.token_cost["input_tokens"] == 12000


# ── BrandMemory ───────────────────────────────────────────────────────────────

def test_brand_memory_create_defaults():
    bm = BrandMemoryCreate(
        content="Most people think helium is for balloons...",
        platform=Platform.LINKEDIN,
    )
    assert bm.performance_metrics == {}
    assert bm.published_at is None


# ── KnowledgeBase ─────────────────────────────────────────────────────────────

def test_knowledge_base_chunk_create():
    chunk = KnowledgeBaseChunkCreate(
        source_file="india_mutual_fund_regulations_2025.pdf",
        chunk_index=3,
        content="SEBI circular dated 15 Jan 2025 mandates that...",
    )
    assert chunk.chunk_index == 3


# ── CostLog ───────────────────────────────────────────────────────────────────

def test_cost_log_upsert():
    log = CostLogUpsert(
        agent_name="scoring_agent",
        date=date(2026, 5, 29),
        token_count=8500,
        estimated_cost_usd=0.043,
    )
    assert log.estimated_cost_usd == pytest.approx(0.043)
