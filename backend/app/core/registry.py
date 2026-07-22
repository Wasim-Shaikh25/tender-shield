"""Service registry — the ONLY way modules call each other.

Capabilities are published and consumed by string name (e.g. "rulepacks.loader").
Consumers use get() and handle absence gracefully, or require() when the feature
cannot work at all without the capability (spec core B1/B2).
"""

from __future__ import annotations

from typing import Any


class CapabilityUnavailable(RuntimeError):
    def __init__(self, name: str):
        super().__init__(
            f"capability '{name}' is not available — its providing module "
            "may be disabled; consumers must degrade gracefully"
        )
        self.name = name


class ServiceRegistry:
    def __init__(self) -> None:
        self._services: dict[str, Any] = {}

    def provide(self, name: str, service: Any, *, replace: bool = False) -> None:
        if name in self._services and not replace:
            raise ValueError(f"capability '{name}' is already provided")
        self._services[name] = service

    def get(self, name: str, default: Any = None) -> Any:
        return self._services.get(name, default)

    def require(self, name: str) -> Any:
        if name not in self._services:
            raise CapabilityUnavailable(name)
        return self._services[name]

    def has(self, name: str) -> bool:
        return name in self._services

    def names(self) -> list[str]:
        return sorted(self._services)
