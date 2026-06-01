from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional
from functools import lru_cache

# Resolves to backend/ regardless of where the process is started from
_HERE = Path(__file__).parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_HERE / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        env_ignore_empty=True,   # empty system env-vars fall through to .env values
    )

    # Supabase
    supabase_url: str = Field(..., alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(..., alias="SUPABASE_SERVICE_ROLE_KEY")

    # Anthropic
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")

    # Embeddings — Gemini primary, local fastembed fallback
    google_api_key: Optional[str] = Field(None, alias="GOOGLE_API_KEY")
    local_embedding_model: str = Field("BAAI/bge-base-en-v1.5", alias="LOCAL_EMBEDDING_MODEL")

    # Legacy Voyage AI (kept so existing .env files don't break on load)
    voyage_api_key: Optional[str] = Field(None, alias="VOYAGE_API_KEY")

    # Redis
    redis_url: str = Field("redis://localhost:6379", alias="REDIS_URL")

    # Slack
    slack_webhook_url: Optional[str] = Field(None, alias="SLACK_WEBHOOK_URL")

    # Cost alerts
    daily_cost_alert_usd: float = Field(5.0, gt=0, alias="DAILY_COST_ALERT_USD") #gt=0

    # Models
    claude_model_heavy: str = Field("claude-sonnet-4-5", alias="CLAUDE_MODEL_HEAVY")
    claude_model_light: str = Field("claude-haiku-4-5", alias="CLAUDE_MODEL_LIGHT")

    # Orchestrator
    orchestrator_model: str = Field("claude-sonnet-4-5", alias="ORCHESTRATOR_MODEL")

    # Research agent
    article_min_words: int = Field(400, gt=0, alias="ARTICLE_MIN_WORDS") #gt=0
    article_max_age_days: int = Field(7, gt=0, alias="ARTICLE_MAX_AGE_DAYS") #gt=0
    default_pre_score_threshold: float = Field(4.0, alias="DEFAULT_PRE_SCORE_THRESHOLD")

    # Scoring
    max_ideas_per_site: int = Field(5, gt=0, alias="MAX_IDEAS_PER_SITE")

    # Research — cap articles fetched per site per run to avoid timeout
    articles_per_site: int = Field(5, gt=0, alias="ARTICLES_PER_SITE")

    # Decision summaries
    rejection_batch_size: int = Field(5, gt=0, alias="REJECTION_BATCH_SIZE")

    # Browser sessions — persistent login profiles for paywalled sites.
    # Login once via the orchestrator; cookies are saved here and reused on every scrape.
    browser_sessions_dir: str = Field(
        "~/.config/contentautomation/browser_sessions",
        alias="BROWSER_SESSIONS_DIR",
    )

    # Site health
    site_failure_pause_threshold: int = Field(5,gt=0, alias="SITE_FAILURE_PAUSE_THRESHOLD") #gt=0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # pydantic-settings populates fields from env, not constructor args
