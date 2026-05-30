from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

import pytest


# ── count_unsummarized_rejections ────────────────────────────────

def test_count_no_previous_summary():
    """When no summary exists, counts ALL rejected ideas."""
    sb = MagicMock()
    # Last summary query returns empty
    sb.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = []
    # Rejection count query
    count_resp = MagicMock()
    count_resp.count = 7
    (
        sb.table.return_value.select.return_value
        .eq.return_value
        .execute.return_value
    ) = count_resp

    from app.agents.scoring.decision_summary import count_unsummarized_rejections
    count, since_ts = count_unsummarized_rejections(sb)
    assert count == 7
    assert since_ts is None


def test_count_with_previous_summary():
    """With an existing summary, only counts rejections after its created_at."""
    sb = MagicMock()
    ts = "2026-05-30T10:00:00+00:00"
    sb.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"created_at": ts}
    ]
    count_resp = MagicMock()
    count_resp.count = 3
    (
        sb.table.return_value.select.return_value
        .eq.return_value
        .gt.return_value
        .execute.return_value
    ) = count_resp

    from app.agents.scoring.decision_summary import count_unsummarized_rejections
    count, since_ts = count_unsummarized_rejections(sb)
    assert count == 3
    assert since_ts is not None


def test_count_returns_zero_on_exception():
    """Never raises — returns (0, None) on DB error."""
    sb = MagicMock()
    sb.table.side_effect = Exception("DB down")
    from app.agents.scoring.decision_summary import count_unsummarized_rejections
    count, since_ts = count_unsummarized_rejections(sb)
    assert count == 0
    assert since_ts is None


# ── fetch_recent_rejections ──────────────────────────────────────

def test_fetch_recent_rejections_returns_list():
    sb = MagicMock()
    ideas = [
        {"angle": "Why SEBI rules hurt retail", "platform": "linkedin", "agent_reasoning": "reason A"},
        {"angle": "Loan EMI tips", "platform": "twitter", "agent_reasoning": "reason B"},
    ]
    (
        sb.table.return_value.select.return_value
        .eq.return_value
        .order.return_value
        .limit.return_value
        .execute.return_value.data
    ) = ideas

    from app.agents.scoring.decision_summary import fetch_recent_rejections
    result = fetch_recent_rejections(sb, None, 10)
    assert len(result) == 2
    assert result[0]["angle"] == "Why SEBI rules hurt retail"


def test_fetch_recent_rejections_empty_on_exception():
    sb = MagicMock()
    sb.table.side_effect = Exception("timeout")
    from app.agents.scoring.decision_summary import fetch_recent_rejections
    result = fetch_recent_rejections(sb, None, 10)
    assert result == []


# ── generate_decision_summary ────────────────────────────────────

def test_generate_summary_calls_claude():
    """Calls Claude Haiku and returns the text content."""
    from unittest.mock import MagicMock, patch
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text="Too many generic EMI explainers rejected. Twitter ideas without hooks rejected.")]
    client.messages.create.return_value = msg

    from app.agents.scoring.decision_summary import generate_decision_summary
    rejected = [
        {"angle": "Generic EMI post", "platform": "linkedin"},
        {"angle": "No hook twitter", "platform": "twitter"},
    ]
    result = generate_decision_summary(rejected, client, "claude-haiku-4-5")
    assert "rejected" in result.lower()
    client.messages.create.assert_called_once()


def test_generate_summary_empty_input():
    """Returns empty string for empty input without calling Claude."""
    client = MagicMock()
    from app.agents.scoring.decision_summary import generate_decision_summary
    result = generate_decision_summary([], client, "claude-haiku-4-5")
    assert result == ""
    client.messages.create.assert_not_called()


def test_generate_summary_returns_empty_on_exception():
    client = MagicMock()
    client.messages.create.side_effect = Exception("API error")
    from app.agents.scoring.decision_summary import generate_decision_summary
    rejected = [{"angle": "something", "platform": "linkedin"}]
    result = generate_decision_summary(rejected, client, "claude-haiku-4-5")
    assert result == ""


# ── write_summary ────────────────────────────────────────────────

def test_write_summary_inserts_row():
    sb = MagicMock()
    from app.agents.scoring.decision_summary import write_summary
    write_summary(sb, "Pattern found.", 5)
    sb.table.assert_called_with("user_decision_summaries")
    call_args = sb.table.return_value.insert.call_args[0][0]
    assert call_args["summary_text"] == "Pattern found."
    assert call_args["rejection_count"] == 5


def test_write_summary_skips_empty_text():
    sb = MagicMock()
    from app.agents.scoring.decision_summary import write_summary
    write_summary(sb, "", 3)
    sb.table.return_value.insert.assert_not_called()


def test_write_summary_never_raises():
    sb = MagicMock()
    sb.table.side_effect = Exception("DB error")
    from app.agents.scoring.decision_summary import write_summary
    write_summary(sb, "Some text.", 5)  # Must not raise
