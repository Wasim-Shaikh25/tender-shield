# TS-013a — Per-module SQLAlchemy models + migrations (0001-0008)

**Status:** done
**Requirement:** Doc §3.2
**Spec(s) updated:** `specs/modules/{auth,ingestion,findings,billing,export}.md`
**Module(s):** `auth`, `ingestion`, `findings`, `billing`, and others (multiple)
**Severity / Gate:** P0 · Phase 1 MVP

## What this builds

The first 8 migrations, each owned by its module per CLAUDE.md §2 ("each
module owns its DB tables, migrations, and tests"): auth, ingestion,
findings, audit_log, artifacts, billing. Risk and BOQ persist their findings
through the shared `findings` tables rather than owning separate ones;
review/drafting/export/billing are wired to read/write through those same
module-owned tables plus their own.

## Implementation

Each module's `models.py` declares its own tables via `Base` +
`WorkspaceScopedMixin`/`TimestampMixin` (TS-013); each migration under
`backend/migrations/versions/` calls that module's `rls_statements()` for
every workspace-scoped table it creates — no module's migration touches
another module's tables directly (CLAUDE.md §2: "Foreign keys may reference
core tables ... but not another module's tables directly; use IDs +
events").

## Files touched

- `backend/app/modules/{auth,ingestion,findings,billing}/models.py`
- `backend/migrations/versions/0001..0008_*.py`

## Tests

- Per-module `backend/tests/modules/<name>/test_models.py`

## Acceptance criteria

- [x] Every workspace-scoped table created in 0001-0008 has RLS enabled +
      forced.
- [x] No migration in this range creates a foreign key directly into
      another module's table.

## Commit

Predates commit-granular history (PR #10 bulk import).
