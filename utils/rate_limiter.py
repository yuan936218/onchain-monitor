"""Token bucket rate limiter for API calls."""

import time
from collections import deque
from threading import Lock


class RateLimiter:
    def __init__(self, calls_per_second: float = 5, calls_per_day: int = 100_000):
        self.calls_per_second = calls_per_second
        self.calls_per_day = calls_per_day
        self.timestamps: deque = deque()
        self.daily_count = 0
        self.daily_reset = time.time()
        self.lock = Lock()

    def acquire(self):
        with self.lock:
            now = time.time()

            # Reset daily counter if 24h passed
            if now - self.daily_reset > 86400:
                self.daily_count = 0
                self.daily_reset = now

            # Check daily limit
            if self.daily_count >= self.calls_per_day:
                wait = self.daily_reset + 86400 - now
                raise Exception(f"Daily rate limit reached. Resets in {wait:.0f}s")

            # Remove timestamps older than 1 second (>= to avoid boundary overlap)
            while self.timestamps and now - self.timestamps[0] >= 1.0:
                self.timestamps.popleft()

            # Check per-second limit
            if len(self.timestamps) >= self.calls_per_second:
                sleep_time = 1.0 - (now - self.timestamps[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)
                # Clean up after sleep (<= to match the >= boundary above)
                now_after = time.time()
                while self.timestamps and now_after - self.timestamps[0] >= 1.0:
                    self.timestamps.popleft()

            self.timestamps.append(time.time())
            self.daily_count += 1

    @property
    def remaining_today(self):
        return self.calls_per_day - self.daily_count
