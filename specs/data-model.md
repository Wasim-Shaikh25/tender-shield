# Canonical Data Model — Spec

**Status:** agreed
**Requirement refs:** Doc §3.2
**Task refs:** TS-013, TS-086

## Purpose

Single PostgreSQL 16 (+pgvector) schema — the "baseline graph". The authoritative
DDL is in Doc §3.2; this spec records ownership and the rules around it.

## Table ownership (module → tables)

| Module | Tables |
|---|---|
| `auth` | `users`, `workspaces`, `workspace_members`, `projects`, `project_members`, `invitations`, `password_resets`, refresh-token tables |
| `ingestion` | `opportunities`*, `documents`, `clauses`, `deadlines`, `doc_chunks` |
| `findings` | `findings`** (shared table; owns model + migration + store) |
| `boq` | `boq_items` |
| `drafting` | `artifacts` |
| `review` | `audit_log`, `outcomes` (updates review columns on `findings`) |
| `billing` | `usage_events`, `payment_log`, payment intents/webhook dedup |

*`opportunities` is the shared aggregate root; owned by `ingestion`, referenced by
ID from every other module.

**`findings` is a shared table with one owner: the `findings` module owns the
SQLAlchemy model, migration, and `FindingStore`. Producers (`risk`, `boq`) write
via the `findings.store_factory` capability, scoped by a `producer` column so a
re-run of one producer never disturbs another's rows. The row shape mirrors the
core `Finding` contract (`app.core.contracts.findings`). This keeps the table
pluggable — no module imports another's models.

## Behavior

- **B1 (RLS non-negotiable):** every workspace-scoped table carries
  `POLICY workspace_isolation` with **both** `USING` and `WITH CHECK`
  (`workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid`),
  and `FORCE ROW LEVEL SECURITY` — without FORCE, PostgreSQL exempts the
  table's *owner* from RLS, and the application connects as the migration
  owner in every deployment, which made the original (pre-TS-086) policy
  inert. `current_setting(..., true)` returns NULL instead of raising when
  unbound, so an unbound session sees zero rows (fails closed) rather than
  erroring. The request layer binds via `set_config('app.workspace_id', …, true)`
  per transaction (**not** `SET LOCAL … = :param`, which is a PostgreSQL syntax
  error — SET only accepts a literal, never a bind parameter) and re-applies
  the binding on every new transaction (`after_begin`), because services in
  this codebase commit more than once per request and the binding is
  transaction-scoped.
  - **`workspaces`** is keyed on `id`, not `workspace_id` — it is the tenant
    row itself.
  - **`workspaces`** and **`workspace_members`** use a *compound* predicate
    (`workspace_id/id = bound` **OR** `user_id = app.user_id`), not the plain
    single-column predicate every other table uses: a user's own workspace
    memberships legitimately span multiple workspaces (`list_workspaces`), so
    a plain per-workspace predicate would hide every workspace except
    whichever one is currently bound. `app.user_id` is bound once per request,
    at `authenticate()`, and additionally at the start of `login`/`refresh`/
    Apple sign-in (which run before any authenticated binding exists) so those
    unauthenticated entry points can find the caller's own membership row.
  - See `app.core.db` (`rls_statements`, `workspaces_rls_statements`,
    `workspace_members_rls_statements`, `bind_workspace_context`,
    `bind_user_context`, `install_rls_rebinding`) and
    `tests/test_rls_postgres.py` (the only place this is actually exercised —
    SQLite has no RLS, so `bind_workspace_context` is a documented no-op there).
- **B2 (provenance columns):** extraction-derived rows carry `source_page` and
  verbatim `source_quote` (≤200 chars).
- **B3 (append-only):** `audit_log` and `payment_log` have no UPDATE/DELETE grants.
- **B4 (money):** amounts in minor units (`BIGINT`) for payments; `NUMERIC` for BOQ.
- **B5 (migrations):** Alembic; every migration reversible; CI runs up/down on a
  scratch DB (Doc §11.1).

## Foundation vs. per-module models (TS-013)

The DB **foundation** is core infrastructure (`app/core/db.py`): the declarative
`Base`, `WorkspaceScopedMixin` (adds `workspace_id` and self-registers the table
in `WORKSPACE_SCOPED_TABLES` for RLS generation), `TimestampMixin`,
`rls_statements()`, `bind_workspace_context()`/`bind_user_context()`,
`install_rls_rebinding()`, and the engine/session-factory builders. Tables with
a workspace-scoping column that aren't `WorkspaceScopedMixin` subclasses
(composite-PK tables, or the tenant row itself) register explicitly in
`EXTRA_RLS_TABLES` or get a dedicated statement builder (`workspaces`,
`workspace_members`) — `WorkspaceScopedMixin`'s `__tablename__` hook is the
*only* thing that populates `WORKSPACE_SCOPED_TABLES`, so a table that doesn't
subclass it is silently absent from RLS otherwise (this was true of
`workspaces`/`workspace_members`/`project_members` until TS-086). `create_app`
publishes `db.engine` and `db.sessionmaker` as registry capabilities so modules
consume the session factory without importing a DB module.

The **table models themselves are owned by their modules** (table above) and
land with each module's task — a module defines them in
`app/modules/<name>/models.py`, which `migrations/env.py` auto-discovers so
`Base.metadata` fills in as modules are enabled. This keeps the schema
pluggable: no orphan models for modules that don't exist yet.

## Acceptance criteria

- A1 (foundation): `WorkspaceScopedMixin` registers tables for RLS;
  `rls_statements` emits `FORCE` + `USING`/`WITH CHECK`; SQLite session
  roundtrip works; `bind_workspace_context`/`bind_user_context` are safe
  no-ops off PostgreSQL. `alembic upgrade head`/`downgrade base` clean on both
  SQLite and PostgreSQL (`.github/workflows/ci.yml` `backend-postgres` job).
- A2 (per module): each module's migration creates its Doc §3.2 tables; up/down
  clean; RLS denies cross-workspace reads/writes in a real-PostgreSQL
  integration test (`tests/test_rls_postgres.py`) — an unbound session sees
  zero rows, a bound session cannot read or `INSERT`/`UPDATE` another
  workspace's rows, and the binding survives a mid-request commit.

## Out of scope

Phase-3 tables (variations/notices), admin-console tables beyond `payment_log`.
