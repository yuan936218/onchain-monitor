"""Etherscan API collector for stablecoin transfers."""

import os
import logging
from datetime import datetime
from collectors.base import BaseCollector
from database.connection import get_session
from database.models import StablecoinTransfer, MonitoredAddress, WhaleMovement, MintBurnEvent
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
        self.last_stats = {}
        self.last_error = None

    def _api_params(self, extra: dict = None) -> dict:
        """Build API params with V2 chainid support."""
        params = {"chainid": "1", "apikey": _get_api_key()}
        if extra:
            params.update(extra)
        return params

    def _api_call(self, params: dict):
        """Make an Etherscan API call."""
        self.rate_limiter.acquire()
        resp = self.client.get(ETHERSCAN_BASE_URL, params=params)
        data = resp.json()
        # status=1 means success, status=0 with result might be OK or error
        if data.get("status") == "1":
            return data
        elif data.get("status") == "0":
            msg = str(data.get("message", ""))
            if "No transactions" in msg or "No records" in msg:
                return data
            if "deprecated" in msg.lower():
                logger.warning(f"[etherscan] V1 deprecated, using V2 params: {msg}")
                return data
            return data  # could be legitimate empty result
        return data

    def _get_latest_block(self):
        """Get latest block by checking a known active address's latest tx."""
        # Use a Binance hot wallet which has frequent transactions
        data = self._api_call(self._api_params({
            "module": "account",
            "action": "txlist",
            "address": "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8",
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": 1,
            "sort": "desc",
        }))
        if data.get("status") == "1" and isinstance(data.get("result"), list) and data["result"]:
            return int(data["result"][0]["blockNumber"])
        raise Exception(f"Cannot get latest block: {data}")

    def _fetch_token_transfers(self, address: str, token_address: str, from_block: int, to_block: int):
        """Fetch ERC-20 token transfers for a specific address."""
        data = self._api_call(self._api_params({
            "module": "account",
            "action": "tokentx",
            "contractaddress": token_address,
            "address": address,
            "startblock": from_block,
            "endblock": to_block,
            "sort": "desc",
        }))
        if data.get("status") == "1" and isinstance(data.get("result"), list):
            return data["result"]
        elif "No transactions" in str(data.get("message", "")):
            return []
        elif data.get("status") == "0":
            result = data.get("result")
            if isinstance(result, list):
                return result
            return []
        else:
            logger.warning(f"[etherscan] API error for {address}: {data.get('message', data)}")
            return []

    def collect(self):
        if not _get_api_key():
            logger.warning("[etherscan] No API key configured, skipping")
            self.last_error = "No API key configured"
            return

        session = get_session()

        addresses = session.query(MonitoredAddress).filter(
            MonitoredAddress.is_active == True,
            MonitoredAddress.category == "exchange",
        ).all()

        # Also load whale addresses for whale movement detection
        whale_addresses = session.query(MonitoredAddress).filter(
            MonitoredAddress.is_active == True,
            MonitoredAddress.category == "whale",
        ).all()
        whale_addr_set = {w.address.lower() for w in whale_addresses} if whale_addresses else set()

        if not addresses:
            logger.warning("[etherscan] No monitored addresses found")
            self.last_error = "No monitored addresses in database"
            return

        # Get latest block
        try:
            latest_block = self._get_latest_block()
            logger.info(f"[etherscan] Latest block: {latest_block}")
        except Exception as e:
            logger.error(f"[etherscan] Failed to get latest block: {e}")
            self.last_error = f"Failed to get latest block: {str(e)[:200]}"
            # Use a recent known block as fallback
            latest_block = 22000000  # ~May 2026
            logger.info(f"[etherscan] Using fallback block: {latest_block}")

        # Get poll state for resuming
        poll_state = get_poll_state("etherscan_exchange_flows")
        if poll_state:
            from_block = poll_state.last_block + 1
            # Cap at 10,000 blocks behind to avoid excessive scanning
            if from_block < latest_block - 10_000:
                from_block = latest_block - 10_000
        else:
            # First run: scan a wide range (10,000 blocks ≈ 1.5 days)
            from_block = latest_block - 10_000

        logger.info(f"[etherscan] Scanning blocks {from_block}-{latest_block} for {len(addresses)} addresses x {len(STABLECOIN_TOKENS)} tokens")

        new_transfers = 0
        new_whale_moves = 0
        api_errors = 0
        total_api_responses = 0
        for addr in addresses:
            for symbol, token_addr in STABLECOIN_TOKENS.items():
                try:
                    transfers = self._fetch_token_transfers(
                        address=addr.address,
                        token_address=token_addr,
                        from_block=from_block,
                        to_block=latest_block,
                    )
                    total_api_responses += 1
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

                        # Check if this transfer involves a whale address → record as whale movement
                        if whale_addr_set and (from_addr in whale_addr_set or to_addr in whale_addr_set):
                            whale_exists = session.query(WhaleMovement).filter(
                                WhaleMovement.tx_hash == tx_hash
                            ).first()
                            if not whale_exists:
                                whale = WhaleMovement(
                                    tx_hash=tx_hash,
                                    chain="ethereum",
                                    from_address=from_addr,
                                    to_address=to_addr,
                                    from_label=resolve_label(from_addr),
                                    to_label=resolve_label(to_addr),
                                    asset=symbol,
                                    value=value,
                                    value_usd=value,
                                    block_number=int(tx["blockNumber"]),
                                    block_timestamp=datetime.utcfromtimestamp(int(tx["timeStamp"])),
                                )
                                session.add(whale)
                                new_whale_moves += 1

                        # Detect mint (from 0x0) or burn (to 0x0)
                        zero_addr = "0x0000000000000000000000000000000000000000"
                        if from_addr == zero_addr or to_addr == zero_addr:
                            mint_exists = session.query(MintBurnEvent).filter(
                                MintBurnEvent.tx_hash == tx_hash
                            ).first()
                            if not mint_exists:
                                event_type = "mint" if from_addr == zero_addr else "burn"
                                mint_event = MintBurnEvent(
                                    tx_hash=tx_hash,
                                    chain="ethereum",
                                    token_symbol=symbol,
                                    token_address=token_addr.lower(),
                                    event_type=event_type,
                                    value=value,
                                    value_usd=value,
                                    block_number=int(tx["blockNumber"]),
                                    block_timestamp=datetime.utcfromtimestamp(int(tx["timeStamp"])),
                                )
                                session.add(mint_event)
                except Exception as e:
                    api_errors += 1
                    logger.warning(f"[etherscan] Error fetching {symbol} for {addr.label}: {e}")
                    continue

        session.commit()
        update_poll_state("etherscan_exchange_flows", latest_block, datetime.utcnow())

        self.last_stats = {
            "addresses": len(addresses),
            "whale_addresses": len(whale_addr_set),
            "tokens_per_addr": len(STABLECOIN_TOKENS),
            "block_range": f"{from_block}-{latest_block}",
            "latest_block": latest_block,
            "new_transfers": new_transfers,
            "new_whale_moves": new_whale_moves,
            "api_responses": total_api_responses,
            "api_errors": api_errors,
        }
        self.last_error = None
        logger.info(f"[etherscan] Collected {new_transfers} transfers + {new_whale_moves} whale moves from {len(addresses)} addresses")
