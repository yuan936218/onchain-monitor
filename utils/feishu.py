"""Feishu (Lark) bot notification sender."""

import os
import logging
from collectors.base import make_client

logger = logging.getLogger(__name__)

SEVERITY_COLORS = {
    "critical": "red",
    "warning": "yellow",
    "info": "blue",
}


def send_alert(alert):
    """Send an alert to Feishu group via webhook bot."""
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL", "")
    if not webhook_url:
        return

    color = SEVERITY_COLORS.get(alert.severity, "grey")
    severity_labels = {"critical": "严重", "warning": "警告", "info": "提示"}

    etherscan_link = ""
    if alert.related_tx_hash:
        etherscan_link = f"\n[查看交易](https://etherscan.io/tx/{alert.related_tx_hash})"

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"[{severity_labels.get(alert.severity, alert.severity)}] {alert.title}"},
                "template": color,
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": alert.description + etherscan_link,
                },
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": f"链上监控 · {alert.created_at.strftime('%Y-%m-%d %H:%M UTC')}"}
                    ],
                },
            ],
        },
    }

    try:
        client = make_client(timeout=15)
        resp = client.post(webhook_url, json=card)
        if resp.status_code == 200:
            result = resp.json()
            if result.get("code") == 0:
                logger.info(f"[feishu] Alert sent: {alert.title}")
            else:
                logger.warning(f"[feishu] Send failed: {result}")
        else:
            logger.warning(f"[feishu] HTTP {resp.status_code}")
    except Exception as e:
        logger.error(f"[feishu] Error sending alert: {e}")
