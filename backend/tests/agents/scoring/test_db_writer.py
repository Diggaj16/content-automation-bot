"""Unit tests for app.agents.scoring.db_writer."""
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.agents.scoring.db_writer import (
    write_ideas,
    mark_article_processed,
    upsert_cost_log,
)
from app.db.models import IdeaCreate, Platform


def _make_idea(platform: Platform = Platform.LINKEDIN) -> IdeaCreate:
    return IdeaCreate(
        platform=platform,
        angle="How RBI rate hike affects your home loan EMI",
        agent_reasoning="High engagement topic for retail borrowers.",
        score=8.5,
        recent_coverage_flag=False,
        source_article_id=uuid4(),
        source_article_date=datetime(2025, 5, 15, tzinfo=timezone.utc),
    )


def _make_sb(insert_id: str = "idea-uuid-001") -> MagicMock:
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": insert_id}]
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    return sb


class TestWriteIdeas:
    def test_returns_list_of_ids_on_success(self):
        sb = _make_sb(insert_id="idea-uuid-001")
        ids = write_ideas(sb, [_make_idea()], uuid4(), datetime(2025, 5, 15, tzinfo=timezone.utc))
        assert ids == ["idea-uuid-001"]

    def test_inserts_into_ideas_table(self):
        sb = _make_sb()
        write_ideas(sb, [_make_idea()], uuid4(), None)
        sb.table.assert_any_call("ideas")

    def test_returns_empty_list_for_no_ideas(self):
        sb = _make_sb()
        ids = write_ideas(sb, [], uuid4(), None)
        assert ids == []
        sb.table.return_value.insert.assert_not_called()

    def test_skips_failed_ideas_and_continues(self):
        sb = MagicMock()
        sb.table.return_value.insert.return_value.execute.side_effect = [
            Exception("DB error"),
            MagicMock(data=[{"id": "idea-uuid-002"}]),
        ]
        ideas = [_make_idea(Platform.LINKEDIN), _make_idea(Platform.TWITTER)]
        ids = write_ideas(sb, ideas, uuid4(), None)
        assert ids == ["idea-uuid-002"]

    def test_payload_includes_platform_angle_score(self):
        sb = _make_sb()
        idea = _make_idea(Platform.LINKEDIN)
        write_ideas(sb, [idea], uuid4(), None)
        insert_payload = sb.table.return_value.insert.call_args.args[0]
        assert insert_payload["platform"] == "linkedin"
        assert insert_payload["angle"] == idea.angle
        assert insert_payload["score"] == idea.score


class TestMarkArticleProcessed:
    def test_updates_processed_to_true(self):
        sb = _make_sb()
        article_id = UUID("11111111-1111-1111-1111-111111111111")
        mark_article_processed(sb, article_id)
        sb.table.assert_any_call("raw_content")
        update_payload = sb.table.return_value.update.call_args.args[0]
        assert update_payload["processed"] is True

    def test_does_not_raise_on_exception(self):
        sb = MagicMock()
        sb.table.side_effect = Exception("DB error")
        mark_article_processed(sb, UUID("11111111-1111-1111-1111-111111111111"))


class TestUpsertCostLog:
    def test_inserts_new_row_when_no_existing(self):
        sb = _make_sb()
        upsert_cost_log(sb, "scoring_agent", total_usd=0.03, token_count=800)
        insert_payload = sb.table.return_value.insert.call_args.args[0]
        assert insert_payload["agent_name"] == "scoring_agent"
        assert insert_payload["estimated_cost_usd"] == 0.03

    def test_increments_existing_row(self):
        sb = _make_sb()
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "existing-id", "token_count": 500, "estimated_cost_usd": 0.02}
        ]
        upsert_cost_log(sb, "scoring_agent", total_usd=0.03, token_count=600)
        update_payload = sb.table.return_value.update.call_args.args[0]
        assert update_payload["token_count"] == 1100
        assert abs(update_payload["estimated_cost_usd"] - 0.05) < 1e-6
