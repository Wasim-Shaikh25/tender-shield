# TS-086 — RLS hardening: FORCE, WITH CHECK, missing tables, post-commit rebinding

**Status:** done
**Requirement:** [R-001 §B](../../specs/requirements/R-001-tenant-isolation.md)
**Spec(s) updated:** `specs/modules/core.md`
**Module(s):** `core`, migrations, CI
**Severity / Gate:** P0 · Gate 1

## What this builds

Makes RLS actually isolate tenants in production, closing three silent
holes: no `FORCE ROW LEVEL SECURITY` (table owner — the role the app
connects as after running migrations — is exempt from RLS by default), no
`WITH CHECK` (a write could still insert a row into another workspace), and
several tables (`workspaces`, `workspace_members`, `project_members`, etc.)
never registered for a policy at all.

## Current — three reasons the original policy did nothing

```python
# backend/app/core/db.py:59 (before this task)
def rls_statements(table: str) -> list[str]:
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"CREATE POLICY workspace_isolation ON {table} "
        "USING (workspace_id = current_setting('app.workspace_id')::uuid)",
    ]
```

No `FORCE`; no `WITH CHECK`; `workspaces`/`workspace_members`/
`project_members`/`users`/`refresh_tokens`/`password_resets` were never
covered since they're plain `Base` subclasses, not `WorkspaceScopedMixin`.

## Implementation — the shipped, erratum-corrected design

The R-001 §B draft this task was scoped from used `SET LOCAL ... = :param`
and an `after_commit` listener — both are real PostgreSQL/SQLAlchemy bugs
(`SET` only accepts a literal, never a bind parameter; `after_commit` cannot
emit SQL). Caught by testing against a real non-superuser Postgres role
rather than trusting the design on paper. The shipped code fixes both:

```python
# backend/app/core/db.py — shipped
def rls_statements(table: str, *, id_column: str = "workspace_id") -> list[str]:
    predicate = f"{id_column} = NULLIF(current_setting('app.workspace_id', true), '')::uuid"
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        f"DROP POLICY IF EXISTS workspace_isolation ON {table}",
        f"CREATE POLICY workspace_isolation ON {table} "
        f"USING ({predicate}) WITH CHECK ({predicate})",
    ]

def bind_workspace_context(session: Session, workspace_id) -> None:
    session.info["workspace_id"] = str(workspace_id)
    if session.get_bind().dialect.name != "postgresql":
        return
    # set_config(), not "SET LOCAL ... = :param" — Postgres's SET only
    # accepts a literal, not a bind parameter (R-001 erratum #1).
    session.execute(_SET_WORKSPACE_SQL, {"workspace_id": str(workspace_id)})

def install_rls_rebinding(session_factory) -> None:
    """Re-applies the binding on after_begin, not after_commit — after_commit
    has no active transaction to execute SQL in (R-001 erratum #2). Fires
    exactly when a new transaction starts, i.e. right after the prior one
    committed."""
    @event.listens_for(session_factory, "after_begin")
    def _rebind_after_begin(session, transaction, connection): ...
```

`workspaces` and `workspace_members` additionally need a *compound*
predicate (bound workspace OR the caller's own row/membership) rather than
the plain single-workspace predicate every other table gets — see
`workspaces_rls_statements()`/`workspace_members_rls_statements()` — because
`list_workspaces` must show all of a user's memberships, not just whichever
workspace happens to be bound (R-001 erratum #3). This is backed by a
second GUC, `app.user_id`, bound once per request via `bind_user_context`,
and explicitly by `login`/`refresh`/Apple-sign-in's existing-user branch
since those are unauthenticated entry points where the normal
`authenticate()` binding never runs.

New migration (`ae76edba3a7a_rls_hardening_force_with_check.py`) applies
`FORCE`+`WITH CHECK` to every existing table and adds policies for
`workspaces` (`id_column="id"`), `workspace_members`, `project_members`.

## Files touched

- `backend/app/core/db.py`
- `backend/migrations/versions/ae76edba3a7a_rls_hardening_force_with_check.py`
- `.github/workflows/ci.yml` (`backend-postgres` job — RLS must be tested
  against real Postgres, never SQLite, per this project's standing
  validation discipline)

## Tests

- `backend/tests/test_rls_postgres.py` (9 tests, run only against real
  Postgres via the `backend-postgres` CI job — a superuser role bypasses
  RLS regardless of `FORCE`, which would make this suite pass vacuously
  against a misconfigured role, so CI explicitly uses a non-superuser role)

## Acceptance criteria (R-001 §B, A4–A6, A8)

- [x] Every workspace-scoped table (including `workspaces`,
      `workspace_members`, `project_members`) has `FORCE`+`WITH CHECK` RLS.
- [x] A write attempting to insert a row into another workspace is rejected
      by `WITH CHECK`, not just filtered on read.
- [x] The binding survives a mid-request commit (re-applied via
      `after_begin`, not the broken `after_commit` draft).
- [x] `list_workspaces` still returns all of a user's own workspaces despite
      the compound predicate.

## Commit

Predates commit-granular history (PR #10 bulk import).
