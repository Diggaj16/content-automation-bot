"""Unit tests for app.agents.research.db_writer."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, call
from uuid import UUID

import pytest

from app.agents.research.db_writer import (
    upsert_raw_content,
    record_site_success,
    record_site_failure,
    upsert_cost_log,
)
from app.agents.research.extractor import ArticleContent
from app.db.models import StructuredSummary


def _make_article_content() -> ArticleContent:
    return ArticleContent(
        url="https://www.livemint.com/markets/rbi-rate-hike",
        normalized_url="https://www.livemint.com/markets/rbi-rate-hike",
        title="RBI raises repo rate",
        full_text="Long article text " * 50,
        word_count=500,
        paywall_detected=False,
        publication_date=datetime(2025, 5, 15, tzinfo=timezone.utc),
    )


def _make_summary() -> StructuredSummary:
    return StructuredSummary(
        story_narrative="RBI raised rates.",
        key_data_points=["25bps"],
        mechanism="Inflation above target.",
        implications="EMIs will rise.",
        content_angles=["EMI impact", "FD rates"],
    )


def _make_sb(insert_id: str = "abc-123") -> MagicMock:
    sb = MagicMock()
    # upsert_raw_content now uses .upsert() not .insert()
    sb.table.return_value.upsert.return_value.execute.return_value.data = [{"id": insert_id}]
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": insert_id}]
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    return sb


class TestUpsertRawContent:
    def test_returns_id_on_success(self):
        sb = _make_sb(insert_id="uuid-001")
        result = upsert_raw_content(sb, _make_article_content(), _make_summary(), pre_score=7.5)
        assert result == "uuid-001"

    def test_inserts_into_raw_content_table(self):
        sb = _make_sb()
        upsert_raw_content(sb, _make_article_content(), _make_summary(), pre_score=7.5)
        sb.table.assert_any_call("raw_content")

    def test_returns_none_on_exception(self):
        sb = MagicMock()
        sb.table.side_effect = Exception("DB error")
        result = upsert_raw_content(sb, _make_article_content(), _make_summary(), pre_score=7.5)
        assert result is None

    def test_pre_score_included_in_payload(self):
        sb = _make_sb()
        upsert_raw_content(sb, _make_article_content(), _make_summary(), pre_score=8.0)
        upsert_call = sb.table.return_value.upsert.call_args
        payload = upsert_call.args[0]
        assert payload["pre_score"] == 8.0

    def test_publication_date_none_not_in_payload(self):
        """When publication_date is None, it must not appear in the upsert payload."""
        sb = _make_sb()
        content = ArticleContent(
            url="https://www.livemint.com/markets/test",
            normalized_url="https://www.livemint.com/markets/test",
            title="Test article",
            full_text="text " * 100,
            word_count=100,
            paywall_detected=False,
            publication_date=None,
        )
        upsert_raw_content(sb, content, _make_summary(), pre_score=5.0)
        upsert_call = sb.table.return_value.upsert.call_args
        payload = upsert_call.args[0]
        assert "publication_date" not in payload


class TestRecordSiteSuccess:
    def test_resets_consecutive_failures(self):
        sb = _make_sb()
        site_id = UUID("11111111-1111-1111-1111-111111111111")
        record_site_success(sb, site_id)
        # Should call update on curated_sites with consecutive_failures=0
        update_calls = [str(c) for c in sb.table.call_args_list]
        assert any("curated_sites" in c for c in update_calls)

    def test_inserts_health_log_success_row(self):
        sb = _make_sb()
        site_id = UUID("11111111-1111-1111-1111-111111111111")
        record_site_success(sb, site_id)
        insert_calls = sb.table.return_value.insert.call_args_list
        # At least one insert call with success=True
        payloads = [c.args[0] for c in insert_calls if c.args]
        assert any(p.get("success") is True for p in payloads)


class TestRecordSiteFailure:
    def test_inserts_health_log_failure_row(self):
        sb = _make_sb()
        # Make consecutive_failures return 2 (below threshold)
        sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "site-id", "consecutive_failures": 2}
        ]
        site_id = UUID("22222222-2222-2222-2222-222222222222")
        record_site_failure(sb, site_id, "timeout", failure_threshold=5)
        insert_calls = sb.table.return_value.insert.call_args_list
        payloads = [c.args[0] for c in insert_calls if c.args]
        assert any(p.get("success") is False for p in payloads)

    def test_returns_false_when_below_threshold(self):
        sb = _make_sb()
        sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "sid", "consecutive_failures": 2}
        ]
        site_id = UUID("22222222-2222-2222-2222-222222222222")
        deactivated = record_site_failure(sb, site_id, "err", failure_threshold=5)
        assert deactivated is False

    def test_returns_true_and_deactivates_when_at_threshold(self):
        sb = _make_sb()
        sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "sid", "consecutive_failures": 4}
        ]
        site_id = UUID("22222222-2222-2222-2222-222222222222")
        deactivated = record_site_failure(sb, site_id, "err", failure_threshold=5)
        assert deactivated is True

    def test_returns_false_when_site_not_found(self):
        """When the site doesn't exist in the DB, function returns False without crashing."""
        sb = _make_sb()
        sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        site_id = UUID("33333333-3333-3333-3333-333333333333")
        result = record_site_failure(sb, site_id, "some error", failure_threshold=5)
        assert result is False


class TestUpsertCostLog:
    def test_inserts_new_row_when_no_existing(self):
        sb = _make_sb()
        # No existing row for today
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        upsert_cost_log(sb, "research_agent", total_usd=0.05, token_count=1000)
        insert_payload = sb.table.return_value.insert.call_args.args[0]
        assert insert_payload["agent_name"] == "research_agent"
        assert insert_payload["estimated_cost_usd"] == 0.05

    def test_increments_existing_row(self):
        sb = _make_sb()
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "existing-id", "token_count": 500, "estimated_cost_usd": 0.02}
        ]
        upsert_cost_log(sb, "research_agent", total_usd=0.03, token_count=600)
        update_payload = sb.table.return_value.update.call_args.args[0]
        assert update_payload["token_count"] == 1100
        assert abs(update_payload["estimated_cost_usd"] - 0.05) < 1e-6
