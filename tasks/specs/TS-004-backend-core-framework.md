# TS-004 — Backend core: pluggable module framework + tests

**Status:** done
**Requirement:** Doc §3.1 "modular monolith"; user: "pluggable, no hard dependency"
**Spec(s) updated:** `specs/modules/core.md`
**Module(s):** `core`
**Severity / Gate:** P0 · Bootstrap

## What this builds

The framework every feature module plugs into: a `ModuleSpec` contract, a
fail-isolated loader that discovers modules under `app/modules/`, a service
registry for cross-module capability lookup, and an event bus — so the app
boots with any subset of modules enabled (CLAUDE.md §2).

## Implementation

```python
# backend/app/core/module.py
@dataclass(frozen=True)
class ModuleSpec:
    name: str
    version: str
    router: APIRouter | None = None
    soft_deps: tuple[str, ...] = field(default_factory=tuple)
    setup: SetupHook | None = None
    shutdown: SetupHook | None = None
```

```python
# backend/app/core/loader.py — fail-isolated discovery (spec core B3/B4)
def discover_module_names() -> list[str]:
    """Packages under app/modules; underscore-prefixed names are skipped
    (reserved for test fixtures)."""
    pkg = importlib.import_module(MODULES_PACKAGE)
    return sorted(
        info.name for info in pkgutil.iter_modules(pkg.__path__)
        if not info.name.startswith("_")
    )
```

`app/core/registry.py` (`ServiceRegistry`) resolves capabilities by string
name at runtime with graceful-absence handling; `app/core/events.py`
(`EventBus`) is publish/subscribe on named events. Both are how modules talk
to each other WITHOUT importing one another (CLAUDE.md §2's non-negotiable
rule) — enforced by `tests/test_architecture.py`, which walks every module's
imports and fails the build on an `app.modules.<other>` import.

## Files touched

- `backend/app/core/module.py`, `loader.py`, `registry.py`, `events.py`, `config.py`

## Tests

- `backend/tests/test_architecture.py` — module-boundary enforcement
- `backend/tests/test_core_*.py` — loader/registry/events behavior

## Acceptance criteria

- [x] The app boots with `TS_ENABLED_MODULES` set to any subset.
- [x] A module importing `app.modules.<other>` fails CI.
- [x] A module whose import raises is isolated — the rest of the app still
      boots (`LoadReport.failed`).

## Commit

Predates commit-granular history (PR #10 bulk import).
