import pytest
import os


def test_settings_load():
    from app.config import get_settings
    settings = get_settings()
    assert settings.supabase_url.startswith("https://")
    assert len(settings.supabase_service_role_key) > 50
    assert settings.redis_url == "redis://localhost:6379"
    assert settings.article_min_words == 400
    assert settings.article_max_age_days == 7
    assert settings.default_pre_score_threshold == 4.0
    assert settings.site_failure_pause_threshold == 5
    assert settings.claude_model_heavy == "claude-sonnet-4-5"
    assert settings.claude_model_light == "claude-haiku-4-5"


def test_settings_is_cached():
    from app.config import get_settings
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_voyage_api_key_optional():
    from app.config import get_settings
    settings = get_settings()
    assert settings.voyage_api_key is None or isinstance(settings.voyage_api_key, str)
