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
  `TS_ENABLED_MODULES`, `TS_ENV` (`dev|prod`), `TS_CORS_ORIGINS`, `TS_ALLOWED_HOSTS`,
  `TS_STORAGE_TYPE` (`local|s3`), S3 credentials (SecretStr), `TS_REDIS_URL`, and
  all secrets as `SecretStr`.
- `app.core.db.WorkspaceScopedMixin` — adds `workspace_id` and registers the table
  for RLS policy generation.
- `app.core.db.rls_statements(table)` — returns PostgreSQL RLS DDL with `ENABLE`,
  `FORCE`, `USING`, and `WITH CHECK` expressions that fail closed when the GUC is unset.
- `app.core.db.bind_workspace_context` — `SET LOCAL app.workspace_id` on PostgreSQL;
  a no-op on SQLite.
- `app.core.ratelimit.RateLimiter` — pluggable per-IP rate limiting (memory or Redis)
  consumed by public routes.
- `app.core.storage.Storage` protocol — `LocalStorage` and `S3Storage` adapters
  selected by `TS_STORAGE_TYPE`.
- `app.main.create_app()` — FastAPI factory: validates prod settings, loads modules,
  mounts security / CORS / HTTPS / trusted-host middleware, and wires routers under
  `/api/<module>`.

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
- **B5 (production startup guard):** `create_app` raises if `TS_ENV=prod` and
  required secrets (JWT keys, Redis, notification sender, at least one payment
  provider with its webhook secret) are missing or invalid. It also rejects
  wildcard CORS/allowed-hosts, malformed JWT keypairs, weak placeholder webhook
  secrets, `SameSite=None` without Secure cookies, and unknown `TS_COOKIE_SAMESITE`
  values.
- **B6 (security headers):** every HTTP response carries `X-Content-Type-Options`,
  `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and CSP.
- **B7 (rate limiting):** public routes can declare per-IP limits; storage is
  in-memory by default and Redis when `TS_REDIS_URL` is set. The Redis backend uses
  wall-clock timestamps, atomic add-only-under-limit Lua scripts, and unique
  members per attempt. The client IP prefers `X-Forwarded-For` (rightmost entry)
  and falls back to the transport peer.
- **B8 (storage adapter):** `Storage` supports local files and S3 via
  `TS_STORAGE_TYPE`; S3 uses per-workspace prefixes and presigned GET URLs.
  `LocalStorage` reads/writes/deletes run in the default executor so they do not
  block the async event loop.
- **B9 (filename sanitization):** uploaded filenames are reduced to their basename,
  stripped of control characters, path separators, quotes, and other dangerous
  punctuation before being used as a storage key or in a `Content-Disposition`
  header. File downloads quote the filename and escape embedded quotes.
- **B10 (virus scanning):** every uploaded file is streamed through a local clamd
  daemon when `TS_CLAMD_SOCKET` is configured; detected files are quarantined to
  `TS_QUARANTINE_DIR` and rejected with a `ValidationError`. When no scanner is
  configured the step is skipped and a warning is logged.
- **B11 (prompt guard):** `app.core.prompt_guard` provides shared helpers for
  sanitizing free-form LLM input, detecting common prompt-injection/jailbreak
  patterns, and wrapping untrusted data in XML-style delimiters so the LLM is
  instructed to ignore any commands inside the tender text.

## Acceptance criteria

- A1: registry `get` returns `None` for missing capability; `require` raises.
- A2: event bus delivers to all subscribers; a raising handler doesn't stop others.
- A3: `create_app` with `TS_ENABLED_MODULES=health` boots and `/api/health` lists it.
- A4: a broken fixture module doesn't prevent other modules from loading.
- A5: architecture test fails on any `app.modules.<a>` importing `app.modules.<b>`.
- A6: production startup with default Razorpay webhook secret raises `RuntimeError`.
- A7: response headers include `X-Frame-Options: DENY` and CSP.
- A8: in-memory rate limiter blocks a 6th request within the limit window.
- A9: `S3Storage` with `moto` stores and retrieves a file under a workspace prefix.
- A10: rate-limited endpoints use `X-Forwarded-For` (rightmost) for the client IP
  and Redis rate limiting is atomic.
- A11: RLS migration emits `ENABLE`, `FORCE`, and `WITH CHECK` policies using
  `current_setting('app.workspace_id', true)`; every workspace-scoped table including
  membership tables is covered.
- A12: `bind_workspace_context` is a no-op on SQLite and `SET LOCAL` on PostgreSQL.
- A13: PostgreSQL CI runs RLS integration tests proving cross-tenant reads/writes are
  blocked and unbound sessions see no rows.
- A14: a simulated virus signature in an uploaded file is quarantined and rejected
  when `TS_CLAMD_SOCKET` is configured.
- A15: `prompt_guard` detects common prompt-injection patterns, caps message length,
  strips delimiter mimicry, and wraps untrusted text in XML-style tags.

## Out of scope

Celery wiring, Redis-backed bus, DB session management (arrives with TS-013).
