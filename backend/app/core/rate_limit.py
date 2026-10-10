"""Per-client rate limits for expensive endpoints (AI, reports, simulations).

In memory, sliding one-minute window. The API runs as a single instance on the
free tier, so this is enough; a second instance would need a shared store.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import Depends, Request

from app.core.errors import AppError

WINDOW_SECONDS = 60.0
_MAX_KEYS = 10_000


class _Limiter:
    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, bucket: str, key: str, limit: int, now: float | None = None) -> float | None:
        """Record a hit. Returns seconds to wait if over the limit, else None."""
        now = time.monotonic() if now is None else now
        with self._lock:
            if len(self._hits) > _MAX_KEYS:
                self._hits.clear()
            q = self._hits[(bucket, key)]
            while q and now - q[0] >= WINDOW_SECONDS:
                q.popleft()
            if len(q) >= limit:
                return WINDOW_SECONDS - (now - q[0])
            q.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = _Limiter()


def client_key(request: Request) -> str:
    # Render and Vercel put the caller first in X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else ""
    return ip or (request.client.host if request.client else "unknown")


def rate_limit(bucket: str, per_minute: int) -> Any:
    def check(request: Request) -> None:
        wait = limiter.hit(bucket, client_key(request), per_minute)
        if wait is not None:
            raise AppError(
                "rate_limited",
                "Too many requests in a short time. Please wait a moment and try again.",
                429,
                headers={"Retry-After": str(max(1, round(wait)))},
            )

    return Depends(check)
