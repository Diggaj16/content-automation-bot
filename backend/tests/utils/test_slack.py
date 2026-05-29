"""Unit tests for app.utils.slack."""
from unittest.mock import MagicMock, patch

from app.utils.slack import send_slack_alert


class TestSendSlackAlert:
    def test_returns_true_on_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("app.utils.slack.httpx.post", return_value=mock_response):
            assert send_slack_alert("https://hooks.slack.com/test", "hello") is True

    def test_returns_false_on_non_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch("app.utils.slack.httpx.post", return_value=mock_response):
            assert send_slack_alert("https://hooks.slack.com/test", "hello") is False

    def test_returns_false_on_exception(self):
        with patch("app.utils.slack.httpx.post", side_effect=Exception("timeout")):
            assert send_slack_alert("https://hooks.slack.com/test", "hello") is False

    def test_posts_to_correct_url(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("app.utils.slack.httpx.post", return_value=mock_response) as mock_post:
            send_slack_alert("https://hooks.slack.com/test-url", "msg")
            mock_post.assert_called_once()
            assert mock_post.call_args.args[0] == "https://hooks.slack.com/test-url"

    def test_message_sent_in_text_field(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("app.utils.slack.httpx.post", return_value=mock_response) as mock_post:
            send_slack_alert("https://hooks.slack.com/x", "Cost alert fired")
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["text"] == "Cost alert fired"
