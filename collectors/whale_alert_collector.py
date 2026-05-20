"""Whale Alert API collector."""

import logging
from datetime import datetime
from collectors.base import BaseCollector
from database.connection import get_session
from database.models import WhaleMovement
from database.queries import get_poll_state, update_poll_state
from config.settings import WHALE_ALERT_API_KEY
from utils.address_labeler import resolve_label

logger = logging.getLogger(__name__)

WHALE_ALERT_BASE = "https://api.whale-alert.io/v1/transactions"


class WhaleAlertCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="whale_alert", calls_per_second=0.15, calls_per_day=8_640)
        self.api_key = WHALE_ALERT_API_KEY

    def collect(self):
        if not self.api_key:
            return

        # Get last poll cursor
        poll_state = get_poll_state("whale_alert")
        min_value = 500_000  # $500k minimum

        params = {
            "api_key": self.api_key,
            "min_value": min_value,
            "start": poll_state.last_timestamp.timestamp() if poll_state else int(datetime.utcnow().timestamp()) - 3600,
        }

        self.rate_limiter.acquire()
        resp = self.client.get(WHALE_ALERT_BASE, params=params)
        data = resp.json()

        if data.get("result") != "success":
            logger.warning(f"[whale_alert] API error: {data.get('message')}")
            return

        session = get_session()
        new_moves = 0
        latest_ts = datetime.utcnow()

        for tx in data.get("transactions", []):
            tx_hash = tx.get("hash")
            if not tx_hash:
                continue

            exists = session.query(WhaleMovement).filter(
                WhaleMovement.tx_hash == tx_hash
            ).first()
            if exists:
                continue

            from_addr = (tx.get("from") or {}).get("address", "unknown")
            to_addr = (tx.get("to") or {}).get("address", "unknown")

            movement = WhaleMovement(
                tx_hash=tx_hash,
                chain="ethereum",
                from_address=from_addr.lower() if from_addr != "unknown" else from_addr,
                to_address=to_addr.lower() if to_addr != "unknown" else to_addr,
                from_label=resolve_label(from_addr) if from_addr != "unknown" else None,
                to_label=resolve_label(to_addr) if to_addr != "unknown" else None,
                asset=tx.get("symbol", "UNKNOWN"),
                value=float(tx.get("amount", 0)),
                value_usd=float(tx.get("amount_usd", 0)) if tx.get("amount_usd") else None,
                block_number=tx.get("blockchain_id", 0),
                block_timestamp=datetime.utcfromtimestamp(tx.get("timestamp", 0)),
            )
            session.add(movement)
            new_moves += 1

            ts = tx.get("timestamp")
            if ts and ts > latest_ts.timestamp():
                latest_ts = datetime.utcfromtimestamp(ts)

        session.commit()
        update_poll_state("whale_alert", 0, latest_ts)
        logger.info(f"[whale_alert] Collected {new_moves} whale movements")
