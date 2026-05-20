"""Alert evaluation engine — runs all rules after each collection cycle."""

import logging
from alerts.rules import rule_large_exchange_inflow, rule_large_transfer, rule_exchange_flow_surge

logger = logging.getLogger(__name__)

ALL_RULES = [
    ("large_exchange_inflow", rule_large_exchange_inflow),
    ("large_transfer", rule_large_transfer),
    ("exchange_flow_surge", rule_exchange_flow_surge),
]


def evaluate_all_rules():
    """Run all alert rules. Returns total number of new alerts created."""
    total = 0
    for name, rule_fn in ALL_RULES:
        try:
            count = rule_fn()
            if count > 0:
                logger.info(f"[alerts] Rule '{name}' created {count} new alert(s)")
            total += count
        except Exception as e:
            logger.error(f"[alerts] Rule '{name}' failed: {e}")
    return total
