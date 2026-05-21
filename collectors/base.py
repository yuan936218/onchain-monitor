"""Abstract base collector with rate limiting, error handling, and proxy support."""

import time
import logging
from abc import ABC, abstractmethod
import httpx
from utils.rate_limiter import RateLimiter
from config.settings import HTTP_PROXY, HTTPS_PROXY

logger = logging.getLogger(__name__)


def make_client(timeout: int = 30) -> httpx.Client:
    """Create an httpx client with proxy support."""
    proxy = HTTPS_PROXY or HTTP_PROXY
    if proxy:
        return httpx.Client(proxy=proxy, timeout=timeout)
    return httpx.Client(timeout=timeout)


class BaseCollector(ABC):
    def __init__(self, name: str, calls_per_second: float = 5, calls_per_day: int = 100_000):
        self.name = name
        self.rate_limiter = RateLimiter(calls_per_second, calls_per_day)
        self.max_retries = 3
        self.client = make_client()

    def close(self):
        """Release the HTTP client's connection pool."""
        if self.client is not None:
            self.client.close()
            self.client = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    @abstractmethod
    def collect(self):
        """Execute one collection cycle. Must be implemented by subclasses."""

    def safe_collect(self):
        """Collect with error handling and retry logic."""
        for attempt in range(self.max_retries):
            try:
                self.collect()
                return True
            except Exception as e:
                logger.error(f"[{self.name}] Attempt {attempt+1}/{self.max_retries}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # exponential backoff: 1s, 2s, 4s
        return False
