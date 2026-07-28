"""Fixed-window rate limiting (R-002 §C, TS-094). Core infrastructure, not an
auth feature — any module can declare a limit on its own routes without
importing auth. In-memory by default (correct for a single-process deployment);
a Redis-backed implementation behind the same protocol is a later swap (R-016)
that needs no change at the call sites below.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Protocol

from fastapi import HTTPException, Request


@dataclass(frozen=True)
class Limit:
    times: int
    seconds: int


class Limiter(Protocol):
    def hit(self, bucket: str, identity: str, limit: Limit) -> bool:
        """Record one attempt; return False if it exceeds the limit."""
        ...


class InMemoryLimiter:
    """Sliding-window counter per (bucket, identity). Not shared across
    processes — fine for a single backend instance; a multi-replica deployment
    needs the Redis-backed implementation (R-016)."""

    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], list[float]] = defaultdict(list)

    def hit(self, bucket: str, identity: str, limit: Limit) -> bool:
        now = time.monotonic()
        window = self._hits[(bucket, identity)]
        window[:] = [t for t in window if now - t < limit.seconds]
        if len(window) >= limit.times:
            return False
        window.append(now)
        return True


def client_ip(request: Request) -> str:
    """Best-effort client identity for anonymous routes.

    Only trusts X-Forwarded-For when TS_TRUSTED_PROXIES explicitly lists the
    immediate peer as a known proxy. With no trusted proxies configured
    (the default), the header is ignored entirely and the peer IP is used —
    otherwise any client could set X-Forwarded-For itself and claim a fresh
    identity on every request, defeating the limit completely.
    """
    settings = request.app.state.ctx.settings
    trusted = set(settings.trusted_proxies_list())
    peer = request.client.host if request.client else "-"
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd and peer in trusted:
        return fwd.split(",")[0].strip()
    return peer


def rate_limit(bucket: str, limit: Limit):
    """FastAPI dependency: 429 once `limit` is exceeded for this bucket+IP."""

    def guard(request: Request) -> None:
        limiter = request.app.state.ctx.registry.get("core.ratelimiter")
        if limiter is None:
            return  # rate limiting is best-effort infra; never block on its absence
        identity = client_ip(request)
        if not limiter.hit(bucket, identity, limit):
            raise HTTPException(
                429, "rate_limited", headers={"Retry-After": str(limit.seconds)}
            )

    return guard
