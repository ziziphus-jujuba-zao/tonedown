"""In-memory sliding-window limiter, per tenant. Enough for one process; put a gateway in front for more."""

from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import HTTPException


class RateLimiter:
    def __init__(self, default_per_minute: int) -> None:
        self.default = default_per_minute
        self._windows: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, per_minute: int | None = None) -> None:
        limit = per_minute or self.default
        if limit <= 0:
            return
        now = time.monotonic()
        with self._lock:
            window = self._windows.setdefault(key, deque())
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= limit:
                raise HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": "60"})
            window.append(now)
