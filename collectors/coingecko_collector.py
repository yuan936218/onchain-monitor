"""CoinGecko price data collector."""

import logging
from collectors.base import BaseCollector
from utils.cache import TTLCache

logger = logging.getLogger(__name__)

COINGECKO_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"

# Global price cache (shared across all components)
price_cache = TTLCache(ttl_seconds=300)  # 5 minute TTL


class CoinGeckoCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="coingecko", calls_per_second=0.5, calls_per_day=43_200)
        pass

    def collect(self):
        try:
            self.rate_limiter.acquire()
            resp = self.client.get(COINGECKO_PRICE_URL, params={
                "ids": "ethereum,tether,usd-coin",
                "vs_currencies": "usd",
            })
            data = resp.json()

            for coin_id, prices in data.items():
                if "usd" in prices:
                    price_cache.set(f"price_{coin_id}", prices["usd"])

            logger.debug(f"[coingecko] Prices updated: {data}")
        except Exception as e:
            logger.warning(f"[coingecko] Price fetch failed: {e}")


def get_eth_price() -> float | None:
    return price_cache.get("price_ethereum")


def get_usdt_price() -> float | None:
    return price_cache.get("price_tether")


def get_usdc_price() -> float | None:
    return price_cache.get("price_usd-coin")
