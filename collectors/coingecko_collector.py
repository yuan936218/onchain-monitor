"""CoinGecko price data collector — fetches prices and stores history."""

from __future__ import annotations

import logging
from datetime import datetime
from collectors.base import BaseCollector
from utils.cache import TTLCache

logger = logging.getLogger(__name__)

COINGECKO_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"

# Global price cache (shared across all components, 5 min TTL)
price_cache = TTLCache(ttl_seconds=300)

COIN_IDS = {
    "ethereum": "ETH",
    "tether": "USDT",
    "usd-coin": "USDC",
    "wrapped-bitcoin": "WBTC",
}


class CoinGeckoCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="coingecko", calls_per_second=0.5, calls_per_day=43_200)
        self._last_db_snapshot: dict[str, datetime] = {}

    def collect(self):
        try:
            self.rate_limiter.acquire()
            resp = self.client.get(COINGECKO_PRICE_URL, params={
                "ids": "ethereum,tether,usd-coin,wrapped-bitcoin",
                "vs_currencies": "usd",
            })
            data = resp.json()

            now = datetime.utcnow()
            for coin_id, prices in data.items():
                if "usd" in prices:
                    price_cache.set(f"price_{coin_id}", prices["usd"])

            # Save to database every 15 minutes
            last_snap = self._last_db_snapshot.get("prices")
            if not last_snap or (now - last_snap).total_seconds() >= 900:
                self._save_price_snapshots(data, now)
                self._last_db_snapshot["prices"] = now

            logger.debug(f"[coingecko] Prices updated: {data}")
        except Exception as e:
            logger.warning(f"[coingecko] Price fetch failed: {e}")

    def _save_price_snapshots(self, data: dict, now: datetime):
        from database.connection import get_session
        from database.models import PriceSnapshot

        session = get_session()
        saved = 0
        for coin_id, prices in data.items():
            if "usd" not in prices:
                continue
            symbol = COIN_IDS.get(coin_id, coin_id)
            session.add(PriceSnapshot(
                token_id=symbol,
                price_usd=prices["usd"],
                snapshot_at=now,
            ))
            saved += 1
        if saved:
            session.commit()
            logger.info(f"[coingecko] Saved {saved} price snapshots")


def get_eth_price() -> float | None:
    return price_cache.get("price_ethereum")


def get_usdt_price() -> float | None:
    return price_cache.get("price_tether")


def get_usdc_price() -> float | None:
    return price_cache.get("price_usd-coin")


def get_wbtc_price() -> float | None:
    return price_cache.get("price_wrapped-bitcoin")
