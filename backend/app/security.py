"""Small in-process abuse controls used by the FastAPI application."""

from __future__ import annotations

import threading
import time
from collections import deque


class RequestBodyTooLarge(Exception):
    """Raised when a request body exceeds the configured byte limit."""

    def __init__(self, limit: int):
        self.limit = limit
        super().__init__(f"request body exceeds {limit} bytes")


class InMemoryRateLimiter:
    """A bounded-window, per-key limiter suitable for one API worker.

    The key is held only in process memory and is never written to logs or
    the database.  Deployments with multiple workers should place a shared
    rate limiter at the edge as well; this local limiter still protects each
    worker from an accidental request burst.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, *, limit: int, window_seconds: int, now: float | None = None) -> tuple[bool, int]:
        current = time.monotonic() if now is None else now
        window_start = current - window_seconds
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= window_start:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = max(1, int(hits[0] + window_seconds - current + 0.999))
                return False, retry_after
            hits.append(current)
            return True, 0

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()
