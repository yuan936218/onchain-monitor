"""Simple TTL cache for API responses."""

import time
from threading import Lock


class TTLCache:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._data: dict = {}
        self._timestamps: dict = {}
        self._lock = Lock()

    def get(self, key: str):
        with self._lock:
            if key in self._data:
                if time.time() - self._timestamps[key] < self.ttl:
                    return self._data[key]
                del self._data[key]
                del self._timestamps[key]
        return None

    def set(self, key: str, value):
        with self._lock:
            self._data[key] = value
            self._timestamps[key] = time.time()

    def clear(self):
        with self._lock:
            self._data.clear()
            self._timestamps.clear()
