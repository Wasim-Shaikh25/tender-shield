"""Lightweight Prometheus-compatible metrics.

No third-party dependency is required. Counters and histograms are kept in memory
per process and exposed as Prometheus text at `/api/health/metrics`. For
production-scale deployments replace this with `prometheus-fastapi-instrumentator`
or the equivalent.
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class _Metrics:
    """Thread-unsafe but GIL-protected in CPython; sufficient for observability."""

    def __init__(self) -> None:
        self._counters: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._histogram_max_buckets = 10000

    def inc(self, name: str, value: float = 1.0) -> None:
        self._counters[name] += value

    def observe(self, name: str, value: float) -> None:
        bucket = self._histograms[name]
        if len(bucket) >= self._histogram_max_buckets:
            bucket.pop(0)
        bucket.append(value)

    def _counter_line(self, name: str, value: float, labels: str = "") -> str:
        suffix = "{" + labels + "}" if labels else ""
        return f"# HELP {name} counter\n# TYPE {name} counter\n{name}{suffix} {value}\n"

    def _histogram_lines(self, name: str, values: list[float], labels: str = "") -> str:
        if not values:
            return ""
        suffix = "{" + labels + "}" if labels else ""
        lines = [f"# HELP {name} histogram\n# TYPE {name} histogram"]
        # Prometheus-style cumulative buckets (seconds).
        buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        total = sum(values)
        count = len(values)
        for bucket in buckets:
            le_count = sum(1 for v in values if v <= bucket)
            lines.append(f'{name}_bucket{suffix}le="{bucket}" {le_count}')
        lines.append(f'{name}_bucket{suffix}le="+Inf" {count}')
        lines.append(f"{name}_sum{suffix} {total:.6f}")
        lines.append(f"{name}_count{suffix} {count}")
        return "\n".join(lines) + "\n"

    def exposition(self) -> str:
        parts = []
        for name, value in self._counters.items():
            parts.append(self._counter_line(name, value))
        for name, values in self._histograms.items():
            parts.append(self._histogram_lines(name, values))
        return "".join(parts)


METRICS = _Metrics()


def inc_counter(name: str, value: float = 1.0) -> None:
    METRICS.inc(name, value)


def observe_histogram(name: str, value: float) -> None:
    METRICS.observe(name, value)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Starlette middleware recording request counts and latency."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            METRICS.inc("http_requests_total", 1)
            METRICS.inc("http_5xx_total", 1)
            raise
        elapsed = time.perf_counter() - start
        METRICS.inc("http_requests_total", 1)
        METRICS.observe("http_request_duration_seconds", elapsed)
        if response.status_code >= 500:
            METRICS.inc("http_5xx_total", 1)
        elif response.status_code >= 400:
            METRICS.inc("http_4xx_total", 1)
        return response


def expose_metrics() -> str:
    return METRICS.exposition()
