"""
Pydantic models for every database table.

Convention:
  - <Table>       — full DB row (includes id, created_at, DB-generated fields)
  - <Table>Create — data required to INSERT a new row
  - <Table>Update — optional fields for partial updates (where needed)
"""
from __future__ import annotations

from datetime import datetime, date
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field
from enum import Enum


# ── Enums ────────────────────────────────────────────────────────────────────

class Platform(str, Enum):
    LINKEDIN = "linkedin"
    TWITTER  = "twitter"
    BLOG     = "blog"
    EMAIL    = "email"
    WHATSAPP = "whatsapp"
    CAROUSEL = "carousel"
    ADVISOR_TALKING_POINTS = "advisor_talking_points"


class ApprovalStatus(str, Enum):
    PENDING  = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class DraftStatus(str, Enum):
    PENDING   = "pending_approval"
    APPROVED  = "approved"
    REJECTED  = "rejected"
    PUBLISHED = "published"
    FAILED    = "failed"


class TriggerType(str, Enum):
    CRON         = "cron"
    EVENT        = "event"
    MANUAL       = "manual"
    ORCHESTRATOR = "orchestrator"


class ContentType(str, Enum):
    NEWS_DRIVEN = "news_driven"
    KB_DRIVEN   = "kb_driven"
    COMBINED    = "combined"


class MeasurementPeriod(str, Enum):
    H24 = "24h"
    H72 = "72h"
    D7  = "7d"


class SubscriberSource(str, Enum):
    MANUAL       = "manual"
    WEBSITE_FORM = "website_form"


# ── curated_sites ─────────────────────────────────────────────────────────────

class CuratedSite(BaseModel):
    id:                   UUID
    site_name:            str
    section_url:          str
    active:               bool
    last_run_at:          Optional[datetime]
    consecutive_failures: int
    pre_score_threshold:  float
    created_at:           datetime
    updated_at:           datetime


class CuratedSiteCreate(BaseModel):
    site_name:           str
    section_url:         str
    active:              bool  = True
    pre_score_threshold: float = 4.0


class CuratedSiteUpdate(BaseModel):
    active:               Optional[bool]     = None
    last_run_at:          Optional[datetime] = None
    consecutive_failures: Optional[int]      = None
    pre_score_threshold:  Optional[float]    = None


# ── raw_content ───────────────────────────────────────────────────────────────

class StructuredSummary(BaseModel):
    """Five-section summary written by the research agent."""
    story_narrative: str          # 2-3 sentence hook
    key_data_points: list[str]    # specific numbers, dates, names
    mechanism:       str          # underlying cause
    implications:    str          # what this means for the audience
    content_angles:  list[str]    # 2-3 rough angles worth pursuing
    affected_segments: list[str]  = Field(default_factory=list) # e.g. SIP investors, HNI, FD investors
    sentiment:       str          = "neutral" # bullish, bearish, neutral, educational


class RawContent(BaseModel):
    id:                   UUID
    url:                  str
    normalized_url:       str
    title:                str
    source_name:          str
    publication_date:     Optional[datetime]
    fetch_date:           datetime
    full_text:            str
    structured_summary:   Optional[StructuredSummary]
    affected_segments:    list[str]
    word_count:           int
    pre_score:            Optional[float]
    vision_fallback_used: bool
    paywall_detected:     bool
    processed:            bool
    created_at:           datetime


class RawContentCreate(BaseModel):
    url:                  str
    normalized_url:       str
    title:                str
    source_name:          str
    publication_date:     Optional[datetime]          = None
    full_text:            str
    structured_summary:   Optional[StructuredSummary] = None
    affected_segments:    list[str]                   = Field(default_factory=list)
    word_count:           int                         = 0
    pre_score:            Optional[float]             = None
    vision_fallback_used: bool                        = False
    paywall_detected:     bool                        = False


# ── ideas ─────────────────────────────────────────────────────────────────────

class Idea(BaseModel):
    id:                   UUID
    platform:             Platform
    angle:                str
    target_persona:       Optional[str]
    edited_angle:         Optional[str]
    source_article_id:    Optional[UUID]
    agent_reasoning:      str
    source_article_date:  Optional[datetime]
    approval_status:      ApprovalStatus
    score:                Optional[float]
    recent_coverage_flag: bool
    created_at:           datetime
    updated_at:           datetime


class IdeaCreate(BaseModel):
    platform:             Platform
    angle:                str
    target_persona:       Optional[str]      = None
    source_article_id:    Optional[UUID]     = None
    agent_reasoning:      str
    source_article_date:  Optional[datetime] = None
    score:                Optional[float]    = None
    recent_coverage_flag: bool               = False


class IdeaApproval(BaseModel):
    """Payload from the human at Gate 1."""
    approval_status: Literal["approved", "rejected"]
    edited_angle:    Optional[str] = None


# ── user_decision_summaries ───────────────────────────────────────────────────

class UserDecisionSummary(BaseModel):
    id:              UUID
    summary_text:    str
    rejection_count: int
    created_at:      datetime


class UserDecisionSummaryCreate(BaseModel):
    summary_text:    str
    rejection_count: int = 1


# ── drafts ────────────────────────────────────────────────────────────────────

class FinanceFlag(BaseModel):
    """A single flagged item within a draft."""
    flag_type: str  # "company_name" | "financial_figure" | "regulatory_claim" | "investment_advice"
    content:   str  # the flagged text
    context:   str  # surrounding sentence for human review


class Draft(BaseModel):
    id:                     UUID
    platform:               Platform
    content_text:           str
    target_persona:         Optional[str]
    compliance_status:      str
    agent_reasoning:        str
    source_idea_id:         Optional[UUID]
    finance_flags:          list[FinanceFlag]
    suggested_publish_time: Optional[datetime]
    scheduled_at:           Optional[datetime]
    approval_status:        DraftStatus
    created_at:             datetime
    updated_at:             datetime


class DraftCreate(BaseModel):
    platform:               Platform
    content_text:           str
    target_persona:         Optional[str]     = None
    compliance_status:      str               = "pending"
    agent_reasoning:        str
    source_idea_id:         Optional[UUID]    = None
    finance_flags:          list[FinanceFlag] = Field(default_factory=list)
    suggested_publish_time: Optional[datetime] = None


class DraftApproval(BaseModel):
    """Payload from the human at Gate 2."""
    approval_status: Literal["approved", "rejected"]
    content_text:    Optional[str]      = None
    scheduled_at:    Optional[datetime] = None


# ── published_posts ───────────────────────────────────────────────────────────

class PublishedPost(BaseModel):
    id:              UUID
    platform:        str
    post_identifier: str
    published_at:    datetime
    draft_id:        Optional[UUID]
    created_at:      datetime


class PublishedPostCreate(BaseModel):
    platform:        str
    post_identifier: str
    draft_id:        Optional[UUID] = None


# ── content_analytics ─────────────────────────────────────────────────────────

class LinkedInMetrics(BaseModel):
    impressions: int   = 0
    reactions:   int   = 0
    comments:    int   = 0
    shares:      int   = 0


class TwitterMetrics(BaseModel):
    likes:       int   = 0
    retweets:    int   = 0
    impressions: int   = 0
    bookmarks:   int   = 0


class BlogMetrics(BaseModel):
    page_views:                  int   = 0
    sessions:                    int   = 0
    avg_engagement_time_seconds: float = 0.0


class ContentAnalytics(BaseModel):
    id:                 UUID
    post_id:            UUID
    platform:           str
    measurement_period: MeasurementPeriod
    metrics:            dict[str, Any]
    performance_score:  Optional[float]
    created_at:         datetime


class ContentAnalyticsCreate(BaseModel):
    post_id:            UUID
    platform:           str
    measurement_period: MeasurementPeriod
    metrics:            dict[str, Any]
    performance_score:  Optional[float] = None


# ── email_subscribers ─────────────────────────────────────────────────────────

class EmailSubscriber(BaseModel):
    id:              UUID
    email:           str
    name:            Optional[str]
    subscribed_date: datetime
    source:          SubscriberSource
    active:          bool
    created_at:      datetime


class EmailSubscriberCreate(BaseModel):
    email:  EmailStr
    name:   Optional[str]    = None
    source: SubscriberSource = SubscriberSource.MANUAL


# ── style_guide ───────────────────────────────────────────────────────────────

class StyleGuideInsights(BaseModel):
    """Updated by analytics agent at the 7-day analytics mark."""
    optimal_length_range:  Optional[str]  = None
    top_performing_angles: list[str]      = Field(default_factory=list)
    format_preferences:    list[str]      = Field(default_factory=list)
    engagement_patterns:   list[str]      = Field(default_factory=list)
    last_30_day_summary:   Optional[str]  = None


class StyleGuide(BaseModel):
    id:         UUID
    platform:   str
    insights:   StyleGuideInsights
    updated_at: datetime


# ── topic_performance_model ───────────────────────────────────────────────────

class TopicPerformanceModel(BaseModel):
    id:                UUID
    topic_category:    str
    performance_score: float
    sample_count:      int
    updated_at:        datetime


class TopicPerformanceUpsert(BaseModel):
    topic_category:    str
    performance_score: float
    sample_count:      int


# ── brand_memory  (vector store) ──────────────────────────────────────────────

class BrandMemory(BaseModel):
    """DB row. embedding excluded — vector type handled separately."""
    id:                  UUID
    content:             str
    platform:            Platform
    published_at:        Optional[datetime]
    performance_metrics: dict[str, Any]
    created_at:          datetime


class BrandMemoryCreate(BaseModel):
    content:             str
    platform:            Platform
    published_at:        Optional[datetime] = None
    performance_metrics: dict[str, Any]     = Field(default_factory=dict)
    # embedding set separately after Voyage AI call


# ── knowledge_base  (vector store) ───────────────────────────────────────────

class KnowledgeBaseChunk(BaseModel):
    id:          UUID
    source_file: str
    chunk_index: int
    content:     str
    created_at:  datetime


class KnowledgeBaseChunkCreate(BaseModel):
    source_file: str
    chunk_index: int
    content:     str
    # embedding set separately after Voyage AI call


# ── run_logs ──────────────────────────────────────────────────────────────────

class RunLog(BaseModel):
    id:               UUID
    agent_name:       str
    trigger_type:     TriggerType
    processed_count:  int
    success_count:    int
    failure_count:    int
    duration_seconds: Optional[float]
    reasoning_trace:  Optional[str]
    errors:           list[dict[str, Any]]
    token_cost:       dict[str, Any]
    created_at:       datetime


class RunLogCreate(BaseModel):
    agent_name:       str
    trigger_type:     TriggerType
    processed_count:  int                  = 0
    success_count:    int                  = 0
    failure_count:    int                  = 0
    duration_seconds: Optional[float]      = None
    reasoning_trace:  Optional[str]        = None
    errors:           list[dict[str, Any]] = Field(default_factory=list)
    token_cost:       dict[str, Any]       = Field(default_factory=dict)


# ── site_health_log ───────────────────────────────────────────────────────────

class SiteHealthLog(BaseModel):
    id:            UUID
    site_id:       UUID
    success:       bool
    error_message: Optional[str]
    created_at:    datetime


class SiteHealthLogCreate(BaseModel):
    site_id:       UUID
    success:       bool
    error_message: Optional[str] = None


# ── cost_log ──────────────────────────────────────────────────────────────────

class CostLog(BaseModel):
    id:                 UUID
    agent_name:         str
    date:               date
    token_count:        int
    estimated_cost_usd: float
    created_at:         datetime


class CostLogUpsert(BaseModel):
    """Use with ON CONFLICT (agent_name, date) DO UPDATE."""
    agent_name:         str
    date:               date
    token_count:        int
    estimated_cost_usd: float
