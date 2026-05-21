"""Etherscan API collector for on-chain transfers — multi-chain, multi-token support."""

import os
import logging
from datetime import datetime, timedelta
from collectors.base import BaseCollector
from database.connection import get_session
from database.models import StablecoinTransfer, MonitoredAddress, WhaleMovement, MintBurnEvent, ExchangeBalanceSnapshot
from database.queries import get_poll_state, update_poll_state
from config.settings import ETHERSCAN_API_KEY, ETHERSCAN_BASE_URL, CHAIN_CONFIG, MONITORED_TOKENS
from utils.address_labeler import resolve_label
from collectors.coingecko_collector import get_eth_price, get_wbtc_price

logger = logging.getLogger(__name__)

SUPPORTED_CHAINS = ["ethereum", "arbitrum", "bsc"]


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

    def _api_params(self, chain_id: str, extra: dict = None) -> dict:
        """Build API params with V2 chainid support."""
        params = {"chainid": chain_id, "apikey": _get_api_key()}
        if extra:
            params.update(extra)
        return params

    def _api_call(self, params: dict):
        """Make an Etherscan API call."""
        self.rate_limiter.acquire()
        resp = self.client.get(ETHERSCAN_BASE_URL, params=params)
        data = resp.json()
        if data.get("status") == "1":
            return data
        elif data.get("status") == "0":
            msg = str(data.get("message", ""))
            if "No transactions" in msg or "No records" in msg:
                return data
            if "deprecated" in msg.lower():
                logger.warning(f"[etherscan] V1 deprecated, using V2 params: {msg}")
                return data
            return data
        return data

    _CHAIN_SAMPLE_ADDRESSES = {
        "1": "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8",      # Binance 7 (Ethereum)
        "42161": "0xB38e8c17e38363aF6EbdCb3dAE12e0243582891D",   # Binance 1 (Arbitrum)
        "56": "0x8894E0a0c962CB723c1976a4421c95949bE2D4E3",      # Binance 1 (BSC)
    }

    def _get_latest_block(self, chain_id: str) -> int:
        """Get latest block number for a chain."""
        sample_addr = self._CHAIN_SAMPLE_ADDRESSES.get(chain_id, "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8")
        data = self._api_call(self._api_params(chain_id, {
            "module": "account",
            "action": "txlist",
            "address": sample_addr,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": 1,
            "sort": "desc",
        }))
        if data.get("status") == "1" and isinstance(data.get("result"), list) and data["result"]:
            return int(data["result"][0]["blockNumber"])
        raise Exception(f"Cannot get latest block: {data}")

    def _fetch_token_transfers(self, address: str, token_address: str, from_block: int, to_block: int, chain_id: str):
        """Fetch ERC-20 token transfers for a specific address."""
        data = self._api_call(self._api_params(chain_id, {
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

    def _fetch_native_transfers(self, address: str, from_block: int, to_block: int, chain_id: str):
        """Fetch native coin transfers (ETH) for an address via txlist."""
        data = self._api_call(self._api_params(chain_id, {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": from_block,
            "endblock": to_block,
            "sort": "desc",
        }))
        if data.get("status") == "1" and isinstance(data.get("result"), list):
            return [tx for tx in data["result"] if float(tx.get("value", 0)) > 0]
        elif "No transactions" in str(data.get("message", "")):
            return []
        elif data.get("status") == "0":
            result = data.get("result")
            if isinstance(result, list):
                return [tx for tx in result if float(tx.get("value", 0)) > 0]
            return []
        else:
            logger.warning(f"[etherscan] API error for {address} native: {data.get('message', data)}")
            return []

    def _collect_chain(self, chain: str, session):
        """Collect transfers for a single chain. Returns stats dict."""
        chain_id = CHAIN_CONFIG[chain]["chain_id"]
        tokens = MONITORED_TOKENS.get(chain, {})
        if not tokens:
            logger.info(f"[etherscan] No tokens configured for {chain}, skipping")
            return {"chain": chain, "addresses": 0, "new_transfers": 0, "new_whale_moves": 0, "api_responses": 0, "api_errors": 0, "block_range": "N/A"}

        addresses = session.query(MonitoredAddress).filter(
            MonitoredAddress.is_active == True,
            MonitoredAddress.category == "exchange",
            MonitoredAddress.chain == chain,
        ).all()

        whale_addresses = session.query(MonitoredAddress).filter(
            MonitoredAddress.is_active == True,
            MonitoredAddress.category == "whale",
            MonitoredAddress.chain == chain,
        ).all()
        whale_addr_set = {w.address.lower() for w in whale_addresses} if whale_addresses else set()

        if not addresses:
            logger.info(f"[etherscan] No exchange addresses for {chain}, skipping")
            return {"chain": chain, "addresses": 0, "new_transfers": 0, "new_whale_moves": 0, "api_responses": 0, "api_errors": 0, "block_range": "N/A"}

        try:
            latest_block = self._get_latest_block(chain_id)
            logger.info(f"[etherscan] {chain} latest block: {latest_block}")
        except Exception as e:
            logger.error(f"[etherscan] Failed to get latest block for {chain}: {e}")
            return {"chain": chain, "addresses": len(addresses), "new_transfers": 0, "new_whale_moves": 0, "api_responses": 0, "api_errors": 1, "block_range": "error", "error": str(e)[:200]}

        poll_state = get_poll_state(f"etherscan_{chain}")
        if poll_state:
            from_block = poll_state.last_block + 1
            if from_block < latest_block - 10_000:
                from_block = latest_block - 10_000
        else:
            from_block = latest_block - 10_000

        token_count = len(tokens)
        logger.info(f"[etherscan] {chain} scanning blocks {from_block}-{latest_block} for {len(addresses)} addresses x {token_count} tokens")

        new_transfers = 0
        new_whale_moves = 0
        api_errors = 0
        api_responses = 0

        # Pre-load prices for ETH and WBTC
        eth_price = get_eth_price()
        wbtc_price = get_wbtc_price()

        for addr in addresses:
            for symbol, token_info in tokens.items():
                try:
                    token_type = token_info.get("type", "erc20")
                    token_addr = token_info.get("address", "0x0000000000000000000000000000000000000000")

                    if token_type == "native":
                        transfers = self._fetch_native_transfers(
                            address=addr.address,
                            from_block=from_block,
                            to_block=latest_block,
                            chain_id=chain_id,
                        )
                    elif token_type == "erc20":
                        transfers = self._fetch_token_transfers(
                            address=addr.address,
                            token_address=token_addr,
                            from_block=from_block,
                            to_block=latest_block,
                            chain_id=chain_id,
                        )
                    else:
                        continue

                    api_responses += 1
                    for tx in transfers:
                        tx_hash = tx["hash"]
                        exists = session.query(StablecoinTransfer).filter(
                            StablecoinTransfer.tx_hash == tx_hash,
                            StablecoinTransfer.token_symbol == symbol,
                        ).first()
                        if exists:
                            continue

                        from_addr = tx["from"].lower()
                        to_addr = tx["to"].lower()

                        # Compute value and USD equivalent
                        if token_type == "native":
                            value = float(tx["value"]) / 1e18  # wei → ETH
                            value_usd = value * (eth_price or 0)
                        elif symbol == "ETH":
                            value = float(tx["value"]) / (10 ** int(tx["tokenDecimal"]))
                            value_usd = value * (eth_price or 0)
                        elif symbol == "WBTC":
                            value = float(tx["value"]) / (10 ** int(tx["tokenDecimal"]))
                            value_usd = value * (wbtc_price or 0)
                        else:
                            value = float(tx["value"]) / (10 ** int(tx["tokenDecimal"]))
                            value_usd = value  # stablecoin ≈ $1

                        transfer = StablecoinTransfer(
                            tx_hash=tx_hash,
                            chain=chain,
                            token_symbol=symbol,
                            token_address=token_addr.lower(),
                            from_address=from_addr,
                            to_address=to_addr,
                            from_label=resolve_label(from_addr, chain=chain),
                            to_label=resolve_label(to_addr, chain=chain),
                            value=value,
                            value_usd=value_usd,
                            block_number=int(tx["blockNumber"]),
                            block_timestamp=datetime.utcfromtimestamp(int(tx["timeStamp"])),
                            gas_used=int(tx.get("gasUsed", 0)),
                            gas_price_gwei=float(tx.get("gasPrice", 0)) / 1e9 if tx.get("gasPrice") else None,
                        )
                        session.add(transfer)
                        new_transfers += 1

                        # Whale detection
                        if whale_addr_set and (from_addr in whale_addr_set or to_addr in whale_addr_set):
                            whale_exists = session.query(WhaleMovement).filter(
                                WhaleMovement.tx_hash == tx_hash
                            ).first()
                            if not whale_exists:
                                whale = WhaleMovement(
                                    tx_hash=tx_hash,
                                    chain=chain,
                                    from_address=from_addr,
                                    to_address=to_addr,
                                    from_label=resolve_label(from_addr, chain=chain),
                                    to_label=resolve_label(to_addr, chain=chain),
                                    asset=symbol,
                                    value=value,
                                    value_usd=value_usd,
                                    block_number=int(tx["blockNumber"]),
                                    block_timestamp=datetime.utcfromtimestamp(int(tx["timeStamp"])),
                                )
                                session.add(whale)
                                new_whale_moves += 1

                        # Mint/burn detection (ERC-20 tokens only, skip native)
                        if token_type != "native":
                            zero_addr = "0x0000000000000000000000000000000000000000"
                            if from_addr == zero_addr or to_addr == zero_addr:
                                mint_exists = session.query(MintBurnEvent).filter(
                                    MintBurnEvent.tx_hash == tx_hash
                                ).first()
                                if not mint_exists:
                                    event_type = "mint" if from_addr == zero_addr else "burn"
                                    mint_event = MintBurnEvent(
                                        tx_hash=tx_hash,
                                        chain=chain,
                                        token_symbol=symbol,
                                        token_address=token_addr.lower(),
                                        event_type=event_type,
                                        value=value,
                                        value_usd=value_usd,
                                        block_number=int(tx["blockNumber"]),
                                        block_timestamp=datetime.utcfromtimestamp(int(tx["timeStamp"])),
                                    )
                                    session.add(mint_event)
                except Exception as e:
                    api_errors += 1
                    logger.warning(f"[etherscan] Error fetching {symbol} for {addr.label} on {chain}: {e}")
                    continue

        # Snapshot exchange balances (time-gated every 15 min)
        self._snapshot_balances(chain, session)

        # Persist transfers (balance snapshot may have already committed)
        session.commit()

        update_poll_state(f"etherscan_{chain}", latest_block, datetime.utcnow())

        return {
            "chain": chain,
            "addresses": len(addresses),
            "tokens": len(tokens),
            "block_range": f"{from_block}-{latest_block}",
            "latest_block": latest_block,
            "new_transfers": new_transfers,
            "new_whale_moves": new_whale_moves,
            "api_responses": api_responses,
            "api_errors": api_errors,
        }

    # Time gate: snapshot balances at most every 15 minutes per chain
    _last_balance_snapshot = {}

    def _snapshot_balances(self, chain: str, session):
        """Snapshot exchange wallet balances for a single chain."""
        now = datetime.utcnow()
        last = self._last_balance_snapshot.get(chain)
        if last and (now - last).total_seconds() < 900:
            return

        chain_id = CHAIN_CONFIG[chain]["chain_id"]
        tokens = MONITORED_TOKENS.get(chain, {})
        if not tokens:
            return

        addresses = session.query(MonitoredAddress).filter(
            MonitoredAddress.is_active == True,
            MonitoredAddress.category == "exchange",
            MonitoredAddress.chain == chain,
        ).all()

        if not addresses:
            return

        eth_price = get_eth_price()
        wbtc_price = get_wbtc_price()

        snapshots_saved = 0
        for addr in addresses:
            label = addr.label or addr.address[:10]
            for symbol, token_info in tokens.items():
                try:
                    token_type = token_info.get("type", "erc20")
                    decimals = int(token_info.get("decimals", 18))

                    if token_type == "native":
                        data = self._api_call(self._api_params(chain_id, {
                            "module": "account",
                            "action": "balance",
                            "address": addr.address,
                            "tag": "latest",
                        }))
                        if data.get("status") != "1" or not isinstance(data.get("result"), str):
                            continue
                        balance_raw = float(data["result"]) / (10 ** decimals)
                        if symbol == "ETH":
                            balance_usd = balance_raw * (eth_price or 0)
                        else:
                            balance_usd = balance_raw  # native token priced as $1 (unlikely path)
                    else:
                        data = self._api_call(self._api_params(chain_id, {
                            "module": "account",
                            "action": "tokenbalance",
                            "contractaddress": token_info["address"],
                            "address": addr.address,
                            "tag": "latest",
                        }))
                        if data.get("status") != "1" or not isinstance(data.get("result"), str):
                            continue
                        balance_raw = float(data["result"]) / (10 ** decimals)
                        if symbol == "ETH":
                            balance_usd = balance_raw * (eth_price or 0)
                        elif symbol == "WBTC":
                            balance_usd = balance_raw * (wbtc_price or 0)
                        else:
                            balance_usd = balance_raw  # stablecoin ≈ $1

                    if balance_raw <= 0:
                        continue

                    snapshot = ExchangeBalanceSnapshot(
                        chain=chain,
                        exchange_name=label,
                        exchange_address=addr.address,
                        token_symbol=symbol,
                        token_address=token_info.get("address", "0x0000000000000000000000000000000000000000").lower(),
                        balance_raw=balance_raw,
                        balance_usd=balance_usd,
                        snapshot_at=now,
                    )
                    session.add(snapshot)
                    snapshots_saved += 1
                except Exception as e:
                    logger.debug(f"[etherscan] Balance snapshot error {symbol} {addr.label} {chain}: {e}")
                    continue

        if snapshots_saved:
            session.commit()
            self._last_balance_snapshot[chain] = now
            logger.info(f"[etherscan] {chain} balance snapshot: {snapshots_saved} records")

    def collect(self, chains=None):
        if not _get_api_key():
            logger.warning("[etherscan] No API key configured, skipping")
            self.last_error = "No API key configured"
            return

        if chains is None:
            chains = SUPPORTED_CHAINS

        session = get_session()

        all_chain_stats = []
        total_transfers = 0
        total_whale_moves = 0
        total_api_responses = 0
        total_api_errors = 0
        failed_chains = []

        for chain in chains:
            try:
                stats = self._collect_chain(chain, session)
                all_chain_stats.append(stats)
                total_transfers += stats["new_transfers"]
                total_whale_moves += stats["new_whale_moves"]
                total_api_responses += stats["api_responses"]
                total_api_errors += stats["api_errors"]
                if stats.get("error"):
                    failed_chains.append(f"{chain}: {stats['error']}")
            except Exception as e:
                logger.error(f"[etherscan] Failed collecting {chain}: {e}")
                failed_chains.append(f"{chain}: {str(e)[:200]}")

        session.commit()

        self.last_stats = {
            "chains": len(chains),
            "total_addresses": sum(s["addresses"] for s in all_chain_stats),
            "chain_details": all_chain_stats,
            "total_new_transfers": total_transfers,
            "total_new_whale_moves": total_whale_moves,
            "total_api_responses": total_api_responses,
            "total_api_errors": total_api_errors,
        }
        self.last_error = "; ".join(failed_chains) if failed_chains else None
        logger.info(f"[etherscan] Collected {total_transfers} transfers + {total_whale_moves} whale moves across {len(chains)} chains")
