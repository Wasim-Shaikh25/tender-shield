"""In-process event bus — the second sanctioned cross-module channel.

Synchronous pub/sub for now; the interface is kept minimal so it can be backed
by Redis later without touching modules (Doc §3.1). Handlers are isolated: one
failing subscriber never breaks the publisher or other subscribers (spec core A2).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

EventHandler = Callable[[str, dict[str, Any]], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event: str, handler: EventHandler) -> None:
        self._subscribers[event].append(handler)

    def publish(self, event: str, payload: dict[str, Any] | None = None) -> int:
        """Deliver to all subscribers; returns the count successfully handled."""
        delivered = 0
        for handler in list(self._subscribers.get(event, [])):
            try:
                handler(event, payload or {})
                delivered += 1
            except Exception:
                logger.exception("event handler failed for %r (handler=%r)", event, handler)
        return delivered
