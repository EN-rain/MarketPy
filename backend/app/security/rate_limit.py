"""HTTP token-bucket rate limiting middleware."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


@dataclass(slots=True)
class TokenBucket:
    capacity: float
    refill_rate_per_sec: float
    tokens: float
    last_refill_ts: float

    def consume(self, amount: float = 1.0) -> bool:
        now = time.time()
        elapsed = max(0.0, now - self.last_refill_ts)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate_per_sec)
        self.last_refill_ts = now
        if self.tokens < amount:
            return False
        self.tokens -= amount
        return True


class HttpRateLimiter:
    def __init__(self, rate_per_sec: float, burst_size: int) -> None:
        self.rate_per_sec = max(rate_per_sec, 0.1)
        self.burst_size = max(1, burst_size)
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = Lock()

    def _bucket(self, key: str) -> TokenBucket:
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = TokenBucket(
                capacity=float(self.burst_size),
                refill_rate_per_sec=self.rate_per_sec,
                tokens=float(self.burst_size),
                last_refill_ts=time.time(),
            )
            self._buckets[key] = bucket
        return bucket

    def allow(self, key: str) -> bool:
        with self._lock:
            return self._bucket(key).consume()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: HttpRateLimiter) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._limiter = limiter

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path
        if not path.startswith("/api"):
            return await call_next(request)

        user_id = request.headers.get("x-user-id")
        ip = request.client.host if request.client else "unknown"
        endpoint_key = f"{ip}:{request.method}:{path}"
        user_key = f"user:{user_id}" if user_id else f"ip:{ip}"

        if not self._limiter.allow(endpoint_key) or not self._limiter.allow(user_key):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": "1"},
            )

        return await call_next(request)
