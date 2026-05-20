"""DeFiLlama stablecoin API collector."""

import logging
from datetime import datetime
from collectors.base import BaseCollector
from database.connection import get_session
from database.models import MintBurnEvent
from config.settings import STABLECOIN_TOKENS

logger = logging.getLogger(__name__)

DEFILLAMA_STABLECOINS_URL = "https://stablecoins.llama.fi/stablecoins?includePrices=true"


class DefiLlamaCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="defillama", calls_per_second=1, calls_per_day=86_400)
        self._last_supplies = {}  # track supply changes for mint/burn detection

    def collect(self):
        resp = self.client.get(DEFILLAMA_STABLECOINS_URL)
        data = resp.json()

        session = get_session()
        new_events = 0

        for token_name, token_data in data.get("peggedAssets", {}).items():
            # Only process USDT and USDC on Ethereum
            if token_name.upper() not in ("USDT", "USDC"):
                continue

            chains = token_data.get("chainBalances", {})
            ethereum_data = chains.get("Ethereum")
            if not ethereum_data:
                continue

            current_supply = ethereum_data.get("currentPegged", 0)
            prev_supply = self._last_supplies.get(token_name, current_supply)

            if prev_supply != current_supply and prev_supply > 0:
                delta = current_supply - prev_supply
                event_type = "mint" if delta > 0 else "burn"
                abs_delta = abs(delta)

                # Only record events > $1M
                if abs_delta >= 1_000_000:
                    token_addr = STABLECOIN_TOKENS.get(token_name.upper(), "")
                    event = MintBurnEvent(
                        tx_hash=f"defillama_{token_name}_{datetime.utcnow().timestamp()}",
                        chain="ethereum",
                        token_symbol=token_name.upper(),
                        token_address=token_addr.lower(),
                        event_type=event_type,
                        value=abs_delta,
                        value_usd=abs_delta,
                        block_number=0,
                        block_timestamp=datetime.utcnow(),
                    )
                    session.add(event)
                    new_events += 1
                    logger.info(f"[defillama] {token_name} {event_type}: ${abs_delta:,.0f}")

            self._last_supplies[token_name] = current_supply

        session.commit()
        if new_events:
            logger.info(f"[defillama] Recorded {new_events} mint/burn events")
