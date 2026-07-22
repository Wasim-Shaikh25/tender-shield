# Core — Pluggable Module Framework — Spec

**Status:** implemented
**Requirement refs:** Doc §3.1 (modular monolith); user requirement: "module
pluggable format, no hard dependency"
**Task refs:** TS-004

## Purpose

`app/core` is the only shared code surface. It provides the plugin contract,
module loader, service registry, event bus, config, and shared contracts, so that
feature modules stay independently pluggable with **zero hard dependencies** on
each other.

## Public interface

- `app.core.module.ModuleSpec` — the plugin contract:
  `name: str`, `version: str`, `router: APIRouter | None`,
  `soft_deps: tuple[str, ...]`, `setup(ctx) -> None`, `shutdown(ctx) -> None`.
- `app.core.loader.load_modules(settings)` — imports
  `app.modules.<name>.module:module` for each enabled name; import/spec errors in
  one module never prevent others from loading (fail-isolated, logged).
- `app.core.registry.ServiceRegistry` — capabilities by string name:
  `provide(name, obj)`, `get(name) -> obj | None`, `require(name)` (raises
  `CapabilityUnavailable`). Consumers must handle `None` from `get()` gracefully.
- `app.core.events.EventBus` — `subscribe(event, handler)`, `publish(event,
  payload)`; handlers isolated (one failing handler never breaks the publisher);
  sync in-process now, same interface later backed by Redis (Doc §3.1).
- `app.core.config.Settings` — env-driven (`TS_` prefix), incl.
  `TS_ENABLED_MODULES` (comma-separated; empty = all discovered).
- `app.main.create_app()` — FastAPI factory: loads modules, calls `setup(ctx)`
  with `ctx = AppContext(registry, events, settings)`, mounts routers under
  `/api/<module>`, exposes `GET /api/health` listing loaded modules.

## Data owned

None (core owns no business tables).

## Behavior

- **B1 (no hard deps):** modules import only `app.core.*` and their own package.
  Enforced by an architecture test that scans imports of every
  `app/modules/<name>/**` file.
- **B2 (any subset boots):** the app starts with any combination of enabled
  modules; a disabled soft dep degrades the feature, never crashes startup.
- **B3 (fail isolation):** a module raising at import or `setup` is skipped with
  an error log; remaining modules still load.
- **B4 (discovery):** modules are discovered from `app/modules/*` packages
  containing `module.py`; explicit `TS_ENABLED_MODULES` wins over discovery.

## Acceptance criteria

- A1: registry `get` returns `None` for missing capability; `require` raises.
- A2: event bus delivers to all subscribers; a raising handler doesn't stop others.
- A3: `create_app` with `TS_ENABLED_MODULES=health` boots and `/api/health` lists it.
- A4: a broken fixture module doesn't prevent other modules from loading.
- A5: architecture test fails on any `app.modules.<a>` importing `app.modules.<b>`.

## Out of scope

Celery wiring, Redis-backed bus, DB session management (arrives with TS-013).
