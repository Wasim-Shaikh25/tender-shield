"""Pluggable per-IP rate limiting.

Memory storage is used by default; Redis is selected when ``TS_REDIS_URL`` is set.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any, Protocol

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


class RateLimitStorage(Protocol):
    async def is_allowed(self, key: str, limit: int, window: float) -> bool:
        ...

    async def count(self, key: str, window: float) -> int:
        """Count attempts in the current window without adding a new one."""
        ...

    async def reset(self, key: str) -> None:
        """Clear all attempts for a key (e.g. on successful login)."""
        ...


class MemoryRateLimitStorage:
    """In-memory sliding-window rate limiter. Single-process only."""

    def __init__(self) -> None:
        self._windows: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    def _trim(self, key: str, now: float, window: float) -> deque[float]:
        ts = self._windows.get(key)
        if ts is None:
            ts = deque()
            self._windows[key] = ts
        while ts and ts[0] <= now - window:
            ts.popleft()
        return ts

    async def is_allowed(self, key: str, limit: int, window: float) -> bool:
        now = time.monotonic()
        async with self._lock:
            ts = self._trim(key, now, window)
            if len(ts) >= limit:
                return False
            ts.append(now)
            return True

    async def count(self, key: str, window: float) -> int:
        now = time.monotonic()
        async with self._lock:
            ts = self._trim(key, now, window)
            return len(ts)

    async def reset(self, key: str) -> None:
        async with self._lock:
            self._windows.pop(key, None)


class RedisRateLimitStorage:
    """Redis-backed sliding-window rate limiter using sorted sets.

    Requires the ``redis`` package and a ``TS_REDIS_URL``.
    """

    def __init__(self, url: str) -> None:
        import redis.asyncio as redis

        self._client = redis.from_url(url)

    async def is_allowed(self, key: str, limit: int, window: float) -> bool:
        now = time.monotonic()
        pipe = self._client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zrange(key, 0, -1)
        pipe.zadd(key, {str(now): now})
        pipe.pexpire(key, int(window * 1000))
        _, members, _, _ = await pipe.execute()
        return len(members) < limit

    async def count(self, key: str, window: float) -> int:
        now = time.monotonic()
        await self._client.zremrangebyscore(key, 0, now - window)
        return await self._client.zcard(key)

    async def reset(self, key: str) -> None:
        await self._client.delete(key)


class RateLimiter:
    def __init__(self, storage: RateLimitStorage | None = None) -> None:
        self.storage = storage or MemoryRateLimitStorage()

    async def is_allowed(self, key: str, limit: int, window: float) -> bool:
        return await self.storage.is_allowed(key, limit, window)

    async def peek(self, key: str, limit: int, window: float) -> bool:
        """Return True if the next attempt would be allowed, without counting it."""
        count = await self.storage.count(key, window)
        return count < limit

    async def reset(self, key: str) -> None:
        await self.storage.reset(key)


class RateLimitDep:
    """FastAPI dependency factory for per-route rate limiting.

    Usage:
        @router.post("/login", dependencies=[Depends(RateLimitDep(5, 60))])
    """

    def __init__(self, limit: int, window: float) -> None:
        self.limit = limit
        self.window = window

    async def __call__(self, request: Request) -> None:
        limiter = request.app.state.ctx.registry.get("core.rate_limiter")
        if limiter is None:
            return
        client = request.client
        host = client.host if client else "unknown"
        # include the path so each endpoint has its own bucket
        key = f"{host}:{request.url.path}"
        if not await limiter.is_allowed(key, self.limit, self.window):
            raise HTTPException(
                status_code=429,
                detail="rate_limit",
                headers={"Retry-After": str(int(self.window))},
            )


def default_rate_limiter(settings: Any) -> RateLimiter:
    """Build the default rate limiter for the app.

    Uses Redis when ``TS_REDIS_URL`` is set and the ``redis`` package is installed;
    otherwise falls back to in-memory storage.
    """
    if settings.redis_url:
        try:
            storage: RateLimitStorage = RedisRateLimitStorage(settings.redis_url)
            logger.info("rate limiting: redis")
            return RateLimiter(storage)
        except Exception as exc:  # pragma: no cover - dependency not installed in tests
            logger.warning("TS_REDIS_URL set but redis unavailable: %s; using memory", exc)
    return RateLimiter(MemoryRateLimitStorage())
