"""Etherscan API collector for stablecoin transfers."""

import os
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
    """Read API key at runtime — supports Streamlit Cloud secrets and sidebar input."""
    # Check os.environ first (set by sidebar or Streamlit Cloud)
    key = os.getenv("ETHERSCAN_API_KEY", "")
    if key:
        return key
    # Check the module-level constant (set at import from st.secrets or env)
    return ETHERSCAN_API_KEY


class EtherscanCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="etherscan", calls_per_second=5, calls_per_day=100_000)

    def _get_latest_block(self):
        self.rate_limiter.acquire()
        resp = self.client.get(ETHERSCAN_BASE_URL, params={
            "module": "proxy",
            "action": "eth_blockNumber",
            "apikey": _get_api_key(),
        })
        data = resp.json()
        return int(data["result"], 16)

    def _fetch_token_transfers(self, address: str, token_address: str, from_block: int, to_block: int):
        """Fetch ERC-20 token transfers for a specific address."""
        self.rate_limiter.acquire()
        resp = self.client.get(ETHERSCAN_BASE_URL, params={
            "module": "account",
            "action": "tokentx",
            "contractaddress": token_address,
            "address": address,
            "startblock": from_block,
            "endblock": to_block,
            "sort": "desc",
            "apikey": _get_api_key(),
        })
        data = resp.json()
        if data["status"] == "1":
            return data["result"]
        elif "No transactions found" in str(data.get("message", "")):
            return []
        else:
            logger.warning(f"[etherscan] API error for {address}: {data.get('message')}")
            return []

    def collect(self):
        if not _get_api_key():
            logger.warning("[etherscan] No API key configured, skipping")
            return

        session = get_session()

        # Get active exchange addresses
        addresses = session.query(MonitoredAddress).filter(
            MonitoredAddress.is_active == True,
            MonitoredAddress.category == "exchange",
        ).all()

        if not addresses:
            logger.warning("[etherscan] No monitored addresses found")
            return

        # Get latest block
        latest_block = self._get_latest_block()
        logger.info(f"[etherscan] Latest block: {latest_block}")

        # Get poll state for resuming
        poll_state = get_poll_state("etherscan_exchange_flows")
        from_block = (poll_state.last_block + 1) if poll_state else latest_block - 500
        # Don't go too far back on first run
        if from_block < latest_block - 2000:
            from_block = latest_block - 500

        new_transfers = 0
        for addr in addresses:
            # Check USDT and USDC transfers for each address
            for symbol, token_addr in STABLECOIN_TOKENS.items():
                transfers = self._fetch_token_transfers(
                    address=addr.address,
                    token_address=token_addr,
                    from_block=from_block,
                    to_block=latest_block,
                )
                for tx in transfers:
                    tx_hash = tx["hash"]
                    # Skip if already in DB
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
                        value_usd=value,  # approx 1:1 for stablecoins
                        block_number=int(tx["blockNumber"]),
                        block_timestamp=datetime.utcfromtimestamp(int(tx["timeStamp"])),
                        gas_used=int(tx.get("gasUsed", 0)),
                        gas_price_gwei=float(tx.get("gasPrice", 0)) / 1e9 if tx.get("gasPrice") else None,
                    )
                    session.add(transfer)
                    new_transfers += 1

        session.commit()
        update_poll_state("etherscan_exchange_flows", latest_block, datetime.utcnow())
        logger.info(f"[etherscan] Collected {new_transfers} new transfers from {len(addresses)} addresses")
