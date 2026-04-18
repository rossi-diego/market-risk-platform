"""Path-prefix rate limiter for expensive endpoints (currently `/risk/*`).

Implementation is in-process (per-worker in-memory sliding window). Production
scale with multiple workers needs a shared backend — swap `_COUNTERS` for
Redis in that case.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.config import settings

logger = structlog.get_logger(__name__)

_PROTECTED_PREFIXES: tuple[str, ...] = ("/api/v1/risk",)


def _parse_rate(rate: str) -> tuple[int, float]:
    """Parse `"60/minute"` / `"10/second"` into (max_calls, window_seconds)."""
    count, _, unit = rate.partition("/")
    window = {"second": 1.0, "minute": 60.0, "hour": 3600.0}.get(unit.strip().lower(), 60.0)
    return int(count), window


@dataclass(slots=True)
class _Bucket:
    hits: deque[float]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-user (JWT) or per-IP sliding-window limiter for protected paths."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._max_calls, self._window = _parse_rate(settings.RATE_LIMIT_RISK)
        self._buckets: dict[str, _Bucket] = {}

    def _key(self, request: Request) -> str:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1]
            return f"user:{token[-24:]}"
        client = request.client.host if request.client else "unknown"
        return f"ip:{client}"

    def _is_protected(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in _PROTECTED_PREFIXES)

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if not self._is_protected(request.url.path):
            response: Response = await call_next(request)
            return response

        key = self._key(request)
        now = time.monotonic()
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(hits=deque())
            self._buckets[key] = bucket

        cutoff = now - self._window
        while bucket.hits and bucket.hits[0] < cutoff:
            bucket.hits.popleft()

        if len(bucket.hits) >= self._max_calls:
            retry_after = max(1, int(bucket.hits[0] + self._window - now))
            logger.warning(
                "rate_limit.exceeded",
                path=request.url.path,
                key=key,
                retry_after=retry_after,
                limit=settings.RATE_LIMIT_RISK,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "type": "about:blank",
                    "title": "rate limit exceeded",
                    "detail": f"Limit of {settings.RATE_LIMIT_RISK} per client on /risk/*",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        bucket.hits.append(now)
        allowed_response: Response = await call_next(request)
        return allowed_response
