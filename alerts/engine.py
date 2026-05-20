"""Alert evaluation engine — runs all rules after each collection cycle."""

import logging
from alerts.rules import rule_large_exchange_inflow, rule_large_transfer, rule_exchange_flow_surge
from alerts.anomaly import detect_flow_anomaly
from utils.feishu import send_alert

logger = logging.getLogger(__name__)

ALL_RULES = [
    ("large_exchange_inflow", rule_large_exchange_inflow),
    ("large_transfer", rule_large_transfer),
    ("exchange_flow_surge", rule_exchange_flow_surge),
    ("flow_anomaly", detect_flow_anomaly),
]


def evaluate_all_rules():
    """Run all alert rules. Send Feishu notifications for new alerts."""
    from database.connection import get_session
    from database.models import Alert

    # Track IDs before to find new ones
    session = get_session()
    before_ids = {a.id for a in session.query(Alert.id).all()}

    total = 0
    for name, rule_fn in ALL_RULES:
        try:
            count = rule_fn()
            if count > 0:
                logger.info(f"[alerts] Rule '{name}' created {count} new alert(s)")
            total += count
        except Exception as e:
            logger.error(f"[alerts] Rule '{name}' failed: {e}")

    # Send newly created alerts to Feishu
    new_alerts = session.query(Alert).filter(Alert.id.notin_(before_ids)).all()
    for alert in new_alerts:
        send_alert(alert)

    return total
