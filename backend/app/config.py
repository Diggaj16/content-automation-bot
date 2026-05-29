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
    )

    # Supabase
    supabase_url: str = Field(..., alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(..., alias="SUPABASE_SERVICE_ROLE_KEY")

    # Anthropic
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")

    # Voyage AI
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

    # Research agent
    article_min_words: int = Field(400, gt=0, alias="ARTICLE_MIN_WORDS") #gt=0
    article_max_age_days: int = Field(7, gt=0, alias="ARTICLE_MAX_AGE_DAYS") #gt=0
    default_pre_score_threshold: float = Field(4.0, alias="DEFAULT_PRE_SCORE_THRESHOLD")

    # Site health
    site_failure_pause_threshold: int = Field(5,gt=0, alias="SITE_FAILURE_PAUSE_THRESHOLD") #gt=0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # pydantic-settings populates fields from env, not constructor args
