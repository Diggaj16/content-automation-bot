"""Tests for analytics db_writer."""
from unittest.mock import MagicMock

from app.agents.analytics.db_writer import write_analytics, update_style_guide


_POST_ID = "post-uuid-001"


def test_write_analytics_returns_id_on_success():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "analytics-001"}]
    result = write_analytics(sb, _POST_ID, "linkedin", "24h", {"impressions": 100}, 5.5)
    assert result == "analytics-001"


def test_write_analytics_returns_none_on_empty_data():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = []
    result = write_analytics(sb, _POST_ID, "twitter", "72h", {}, 3.0)
    assert result is None


def test_write_analytics_returns_none_on_exception():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.side_effect = RuntimeError("DB error")
    result = write_analytics(sb, _POST_ID, "blog", "7d", {}, 0.0)
    assert result is None


def test_write_analytics_payload_has_required_fields():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "x"}]
    write_analytics(sb, _POST_ID, "linkedin", "24h", {"impressions": 200}, 6.0)
    payload = sb.table.return_value.insert.call_args[0][0]
    assert payload["post_id"] == _POST_ID
    assert payload["platform"] == "linkedin"
    assert payload["measurement_period"] == "24h"
    assert isinstance(payload["metrics"], dict)
    assert payload["performance_score"] == 6.0


def test_update_style_guide_calls_upsert():
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "sg-1", "platform": "linkedin", "insights": {}}
    ]
    update_style_guide(sb, "linkedin", 7.5)
    # Should call update (existing record)
    sb.table.return_value.update.assert_called()


def test_update_style_guide_inserts_when_not_exists():
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    update_style_guide(sb, "twitter", 4.0)
    # Should call insert (new record)
    sb.table.return_value.insert.assert_called()


def test_update_style_guide_never_raises():
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.side_effect = RuntimeError("DB error")
    update_style_guide(sb, "blog", 5.0)  # should not raise
