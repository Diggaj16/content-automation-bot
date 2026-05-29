"""
Slack alert utility — used by all agents to send cost and error notifications.

Usage:
    from app.utils.slack import send_slack_alert
    send_slack_alert(settings.slack_webhook_url, "Cost threshold exceeded")
"""
import httpx

from app.utils.logging import get_logger

logger = get_logger(__name__)


def send_slack_alert(webhook_url: str, message: str) -> bool:
    """
    POST a message to a Slack incoming webhook.

    Returns True on HTTP 200, False on any error (network, non-200 status).
    Never raises.
    """
    try:
        response = httpx.post(
            webhook_url,
            json={"text": message},
            timeout=5.0,
        )
        if response.status_code != 200:
            logger.warning(
                "send_slack_alert: non-200 response",
                extra={"status": response.status_code},
            )
            return False
        return True
    except Exception as exc:
        logger.warning("send_slack_alert failed", extra={"error": str(exc)})
        return False
