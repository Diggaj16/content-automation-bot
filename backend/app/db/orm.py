"""
SQLAlchemy ORM models — the single source of truth for the Postgres schema.

Mirrors migrations 001–005 in their final state:
  - vector(768) embeddings (Gemini / fastembed bge-base)
  - all 7 platform values (incl. whatsapp, carousel, advisor_talking_points)
  - target_persona / compliance_status on drafts, target_persona on ideas,
    affected_segments on raw_content

updated_at columns are maintained at the ORM layer (server_default + onupdate),
so the DB-side update_updated_at trigger from the old Supabase schema is not needed.

Vector similarity (formerly the match_brand_memory / match_knowledge_base /
check_recent_brand_coverage RPC functions) is expressed as SQLAlchemy queries in
app.db.vector_search — there are no Postgres stored procedures.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

EMBEDDING_DIM = 768
_ALL_PLATFORMS = ("linkedin", "twitter", "blog", "email", "whatsapp", "carousel", "advisor_talking_points")
_PLATFORM_LIST_SQL = ", ".join(f"'{p}'" for p in _ALL_PLATFORMS)


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def _updated_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CuratedSite(Base):
    __tablename__ = "curated_sites"

    id: Mapped[uuid.UUID] = _uuid_pk()
    site_name: Mapped[str] = mapped_column(Text, nullable=False)
    section_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    pre_score_threshold: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("4.0"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class RawContent(Base):
    __tablename__ = "raw_content"

    id: Mapped[uuid.UUID] = _uuid_pk()
    url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetch_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_summary: Mapped[dict | None] = mapped_column(JSONB)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    pre_score: Mapped[float | None] = mapped_column(Float)
    vision_fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    paywall_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    affected_segments: Mapped[list | None] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        Index("idx_raw_content_normalized_url", "normalized_url"),
        Index("idx_raw_content_fetch_date", text("fetch_date DESC")),
    )


class Idea(Base):
    __tablename__ = "ideas"

    id: Mapped[uuid.UUID] = _uuid_pk()
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    angle: Mapped[str] = mapped_column(Text, nullable=False)
    edited_angle: Mapped[str | None] = mapped_column(Text)
    target_persona: Mapped[str | None] = mapped_column(Text)
    source_article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_content.id", ondelete="SET NULL")
    )
    agent_reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    source_article_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending_approval'"))
    draft_status: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)
    recent_coverage_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    __table_args__ = (
        CheckConstraint(f"platform IN ({_PLATFORM_LIST_SQL})", name="ideas_platform_check"),
        CheckConstraint(
            "approval_status IN ('pending_approval','approved','rejected')",
            name="ideas_approval_status_check",
        ),
        Index("idx_ideas_approval_status", "approval_status"),
        Index("idx_ideas_created_at", text("created_at DESC")),
    )


class UserDecisionSummary(Base):
    __tablename__ = "user_decision_summaries"

    id: Mapped[uuid.UUID] = _uuid_pk()
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    rejection_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = _created_at()


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    target_persona: Mapped[str | None] = mapped_column(Text)
    compliance_status: Mapped[str | None] = mapped_column(Text, server_default=text("'pending'"))
    agent_reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    source_idea_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ideas.id", ondelete="SET NULL")
    )
    finance_flags: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    suggested_publish_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending_approval'"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    __table_args__ = (
        CheckConstraint(f"platform IN ({_PLATFORM_LIST_SQL})", name="drafts_platform_check"),
        CheckConstraint(
            "approval_status IN ('pending_approval','approved','rejected','published','failed')",
            name="drafts_approval_status_check",
        ),
        Index("idx_drafts_due", "scheduled_at", postgresql_where=text("approval_status = 'approved'")),
    )


class PublishedPost(Base):
    __tablename__ = "published_posts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    post_identifier: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drafts.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (Index("idx_published_posts_draft_id", "draft_id"),)


class ContentAnalytics(Base):
    __tablename__ = "content_analytics"

    id: Mapped[uuid.UUID] = _uuid_pk()
    post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("published_posts.id", ondelete="CASCADE")
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    measurement_period: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    performance_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        CheckConstraint("measurement_period IN ('24h','72h','7d')", name="content_analytics_period_check"),
        UniqueConstraint("post_id", "measurement_period", name="content_analytics_post_period_uq"),
        Index("idx_content_analytics_post_id", "post_id"),
    )


class EmailSubscriber(Base):
    __tablename__ = "email_subscribers"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(Text)
    subscribed_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'manual'"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    unsubscribe_token: Mapped[str | None] = mapped_column(
        Text, unique=True, server_default=text("gen_random_uuid()::text")
    )
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        CheckConstraint("source IN ('manual','website_form')", name="email_subscribers_source_check"),
    )


class StyleGuide(Base):
    __tablename__ = "style_guide"

    id: Mapped[uuid.UUID] = _uuid_pk()
    platform: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    insights: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    updated_at: Mapped[datetime] = _updated_at()

    __table_args__ = (
        CheckConstraint(
            "platform IN ('linkedin','twitter','blog','email','general')",
            name="style_guide_platform_check",
        ),
    )


class TopicPerformanceModel(Base):
    __tablename__ = "topic_performance_model"

    id: Mapped[uuid.UUID] = _uuid_pk()
    topic_category: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    performance_score: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0.5"))
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    updated_at: Mapped[datetime] = _updated_at()


class BrandMemory(Base):
    __tablename__ = "brand_memory"

    id: Mapped[uuid.UUID] = _uuid_pk()
    content: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    performance_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        CheckConstraint(f"platform IN ({_PLATFORM_LIST_SQL})", name="brand_memory_platform_check"),
        Index("idx_brand_memory_platform", "platform"),
        Index("idx_brand_memory_published_at", text("published_at DESC")),
        Index(
            "idx_brand_memory_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id: Mapped[uuid.UUID] = _uuid_pk()
    source_file: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        UniqueConstraint("source_file", "chunk_index", name="knowledge_base_file_chunk_uq"),
        Index(
            "idx_knowledge_base_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class RunLog(Base):
    __tablename__ = "run_logs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    reasoning_trace: Mapped[str | None] = mapped_column(Text)
    errors: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    token_cost: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('cron','event','manual','orchestrator')",
            name="run_logs_trigger_type_check",
        ),
        Index("idx_run_logs_agent_created", "agent_name", text("created_at DESC")),
    )


class SiteHealthLog(Base):
    __tablename__ = "site_health_log"

    id: Mapped[uuid.UUID] = _uuid_pk()
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("curated_sites.id", ondelete="CASCADE")
    )
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (Index("idx_site_health_site_created", "site_id", text("created_at DESC")),)


class CostLog(Base):
    __tablename__ = "cost_log"

    id: Mapped[uuid.UUID] = _uuid_pk()
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0.0"))
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        UniqueConstraint("agent_name", "date", name="cost_log_agent_date_uq"),
        Index("idx_cost_log_date", text("date DESC")),
    )
