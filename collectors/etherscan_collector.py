"""Etherscan API collector for stablecoin transfers."""

import os
import time
import logging
from datetime import datetime
from collectors.base import BaseCollector
from database.connection import get_session
from database.models import StablecoinTransfer, MonitoredAddress
from database.queries import get_poll_state, update_poll_state
from config.settings import ETHERSCAN_API_KEY, ETHERSCAN_BASE_URL, STABLECOIN_TOKENS
from utils.address_labeler import resolve_label

logger = logging.getLogger(__name__)


def _get_api_key():
    key = os.getenv("ETHERSCAN_API_KEY", "")
    if key:
        return key
    return ETHERSCAN_API_KEY


class EtherscanCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="etherscan", calls_per_second=5, calls_per_day=100_000)

    def _api_call(self, params: dict):
        """Make an Etherscan API call with V2 compatibility."""
        self.rate_limiter.acquire()
        resp = self.client.get(ETHERSCAN_BASE_URL, params=params)
        data = resp.json()

        # V1 requires status=1, V2 requires status=0 for error
        if data.get("status") == "1" or data.get("status") == "0":
            return data
        else:
            logger.warning(f"[etherscan] API returned: {data}")
            return data

    def _get_latest_block(self):
        """Get latest block using Etherscan block module (works with free keys)."""
        # Use block/getblocknobytime with current timestamp to get latest block
        now_ts = int(time.time())
        self.rate_limiter.acquire()
        resp = self.client.get(ETHERSCAN_BASE_URL, params={
            "module": "block",
            "action": "getblocknobytime",
            "timestamp": now_ts,
            "closest": "before",
            "apikey": _get_api_key(),
        })
        data = resp.json()
        if data.get("status") == "1" and data.get("result"):
            return int(data["result"])
        # Fallback: try proxy module (requires PRO key, might fail)
        logger.warning(f"[etherscan] block module failed: {data}, trying proxy...")
        self.rate_limiter.acquire()
        resp2 = self.client.get(ETHERSCAN_BASE_URL, params={
            "module": "proxy",
            "action": "eth_blockNumber",
            "apikey": _get_api_key(),
        })
        data2 = resp2.json()
        if data2.get("result") and isinstance(data2["result"], str):
            return int(data2["result"], 16)
        raise Exception(f"Cannot get latest block: {data2}")

    def _fetch_token_transfers(self, address: str, token_address: str, from_block: int, to_block: int):
        """Fetch ERC-20 token transfers for a specific address."""
        params = {
            "module": "account",
            "action": "tokentx",
            "contractaddress": token_address,
            "address": address,
            "startblock": from_block,
            "endblock": to_block,
            "sort": "desc",
            "apikey": _get_api_key(),
        }
        data = self._api_call(params)
        if data.get("status") == "1":
            return data["result"]
        elif "No transactions found" in str(data.get("message", "")):
            return []
        elif data.get("status") == "0" and data.get("result"):
            # V2 API: status=0 with result might still mean no data
            if isinstance(data["result"], list):
                return data["result"]
            return []
        else:
            logger.warning(f"[etherscan] API error for {address}: {data.get('message', data)}")
            return []

    def collect(self):
        if not _get_api_key():
            logger.warning("[etherscan] No API key configured, skipping")
            return

        session = get_session()

        addresses = session.query(MonitoredAddress).filter(
            MonitoredAddress.is_active == True,
            MonitoredAddress.category == "exchange",
        ).all()

        if not addresses:
            logger.warning("[etherscan] No monitored addresses found")
            return

        # Get latest block
        try:
            latest_block = self._get_latest_block()
            logger.info(f"[etherscan] Latest block: {latest_block}")
        except Exception as e:
            logger.error(f"[etherscan] Failed to get latest block: {e}")
            # Use a recent known block as fallback
            latest_block = 22000000  # ~May 2026
            logger.info(f"[etherscan] Using fallback block: {latest_block}")

        # Get poll state for resuming
        poll_state = get_poll_state("etherscan_exchange_flows")
        from_block = (poll_state.last_block + 1) if poll_state else latest_block - 500
        if from_block < latest_block - 2000:
            from_block = latest_block - 500

        new_transfers = 0
        for addr in addresses:
            for symbol, token_addr in STABLECOIN_TOKENS.items():
                try:
                    transfers = self._fetch_token_transfers(
                        address=addr.address,
                        token_address=token_addr,
                        from_block=from_block,
                        to_block=latest_block,
                    )
                    for tx in transfers:
                        tx_hash = tx["hash"]
                        exists = session.query(StablecoinTransfer).filter(
                            StablecoinTransfer.tx_hash == tx_hash
                        ).first()
                        if exists:
                            continue

                        value = float(tx["value"]) / (10 ** int(tx["tokenDecimal"]))
                        from_addr = tx["from"].lower()
                        to_addr = tx["to"].lower()

                        transfer = StablecoinTransfer(
                            tx_hash=tx_hash,
                            chain="ethereum",
                            token_symbol=symbol,
                            token_address=token_addr.lower(),
                            from_address=from_addr,
                            to_address=to_addr,
                            from_label=resolve_label(from_addr),
                            to_label=resolve_label(to_addr),
                            value=value,
                            value_usd=value,
                            block_number=int(tx["blockNumber"]),
                            block_timestamp=datetime.utcfromtimestamp(int(tx["timeStamp"])),
                            gas_used=int(tx.get("gasUsed", 0)),
                            gas_price_gwei=float(tx.get("gasPrice", 0)) / 1e9 if tx.get("gasPrice") else None,
                        )
                        session.add(transfer)
                        new_transfers += 1
                except Exception as e:
                    logger.warning(f"[etherscan] Error fetching {symbol} for {addr.label}: {e}")
                    continue

        session.commit()
        update_poll_state("etherscan_exchange_flows", latest_block, datetime.utcnow())
        logger.info(f"[etherscan] Collected {new_transfers} new transfers from {len(addresses)} addresses")
