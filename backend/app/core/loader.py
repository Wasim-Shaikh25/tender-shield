"""Module discovery and fail-isolated loading (spec core B3/B4)."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass, field

from app.core.module import ModuleSpec

logger = logging.getLogger(__name__)

MODULES_PACKAGE = "app.modules"


@dataclass
class LoadReport:
    loaded: list[ModuleSpec] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    missing_soft_deps: dict[str, list[str]] = field(default_factory=dict)


def discover_module_names() -> list[str]:
    """Packages under app/modules; underscore-prefixed names are skipped
    (reserved for test fixtures)."""
    pkg = importlib.import_module(MODULES_PACKAGE)
    return sorted(
        info.name
        for info in pkgutil.iter_modules(pkg.__path__)
        if info.ispkg and not info.name.startswith("_")
    )


def load_modules(names: list[str] | None = None) -> LoadReport:
    """Import <MODULES_PACKAGE>.<name>.module:module for each name.

    A module that fails to import or exposes a bad spec is recorded in
    report.failed and skipped — it never prevents other modules from loading.
    """
    report = LoadReport()
    for name in names if names is not None else discover_module_names():
        try:
            mod = importlib.import_module(f"{MODULES_PACKAGE}.{name}.module")
            spec = getattr(mod, "module", None)
            if not isinstance(spec, ModuleSpec):
                raise TypeError(f"{name}/module.py must expose `module: ModuleSpec`")
            if spec.name != name:
                raise ValueError(f"module name {spec.name!r} != package name {name!r}")
            report.loaded.append(spec)
        except Exception as exc:  # fail-isolated by design
            logger.exception("failed to load module %r", name)
            report.failed[name] = f"{type(exc).__name__}: {exc}"

    loaded_names = {spec.name for spec in report.loaded}
    for spec in report.loaded:
        missing = [dep for dep in spec.soft_deps if dep not in loaded_names]
        if missing:
            report.missing_soft_deps[spec.name] = missing
            logger.warning(
                "module %r missing soft deps %s — related features will degrade",
                spec.name,
                missing,
            )
    return report
