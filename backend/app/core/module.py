"""The plugin contract every feature module implements.

A module package (app/modules/<name>/) exposes exactly one entry point:
a `module: ModuleSpec` object in its module.py. Modules may import only
app.core.* and their own package — never app.modules.<other> (spec core B1;
enforced by tests/test_architecture.py).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import APIRouter

from app.core.config import Settings
from app.core.events import EventBus
from app.core.registry import ServiceRegistry


@dataclass
class AppContext:
    """Handed to every module's setup/shutdown hooks."""

    settings: Settings
    registry: ServiceRegistry
    events: EventBus


SetupHook = Callable[[AppContext], None]


@dataclass(frozen=True)
class ModuleSpec:
    name: str
    version: str
    router: APIRouter | None = None
    # Advisory only: names of modules this one integrates with when present.
    # The module MUST still work (degraded) when these are absent (spec core B2).
    soft_deps: tuple[str, ...] = field(default_factory=tuple)
    setup: SetupHook | None = None
    shutdown: SetupHook | None = None
