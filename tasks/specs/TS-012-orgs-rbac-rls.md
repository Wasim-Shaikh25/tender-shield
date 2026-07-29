# TS-012 — Orgs, org_members, RBAC guard, RLS binding

**Status:** done
**Requirement:** Doc §5, §3.2
**Spec(s) updated:** `specs/modules/auth.md`, `specs/modules/core.md`
**Module(s):** `auth`, `core`
**Severity / Gate:** P0 · Phase 1 MVP

## What this builds

Workspace-scoped RBAC (`Principal` + role ranking) and the Postgres
Row-Level-Security binding every org-scoped table depends on (CLAUDE.md §4:
"RLS / org isolation on every org-scoped table — cross-tenant leakage is
company-ending").

## Implementation

```python
# backend/app/modules/auth/rbac.py
ROLE_RANK = {"viewer": 0, "reviewer": 1, "estimator": 2, "admin": 3, "owner": 4}

@dataclass(frozen=True)
class Principal:
    user_id: str
    workspace_id: str
    role: str
    is_superadmin: bool = False

def role_at_least(role: str, min_role: str) -> bool:
    return ROLE_RANK.get(role, -1) >= ROLE_RANK[min_role]
```

```python
# backend/app/core/db.py
def bind_workspace_context(session: Session, workspace_id: uuid.UUID | str) -> None:
    """Bind app.workspace_id for the current transaction — the RLS binding
    every request must perform before touching workspace data (Doc §5, §3.2).
    A no-op on SQLite (tests): cross-workspace isolation is exercised by
    dedicated integration tests against PostgreSQL."""
    session.info["workspace_id"] = str(workspace_id)
    if session.get_bind().dialect.name != "postgresql":
        return
    session.execute(_SET_WORKSPACE_SQL, {"workspace_id": str(workspace_id)})
```

Uses `set_config()`, not `SET LOCAL <name> = :param` — Postgres's `SET`
command only accepts a literal, not a bind parameter, so `SET LOCAL
app.workspace_id = $1` is a syntax error. `install_rls_rebinding()` re-applies
the binding after any mid-request commit, since it's transaction-scoped and
several services (billing, auth) commit more than once per request.

## Files touched

- `backend/app/modules/auth/rbac.py`, `deps.py`
- `backend/app/core/db.py` (`bind_workspace_context`, `bind_user_context`,
  `rls_statements`, `install_rls_rebinding`)

## Tests

- `backend/tests/modules/auth/test_rbac.py`
- `backend/tests/test_rls_postgres.py` (real Postgres, FORCE RLS)

## Acceptance criteria

- [x] Every org-scoped table has an RLS policy bound from the JWT's
      `workspace` claim.
- [x] Binding survives a mid-request commit (re-applied via
      `install_rls_rebinding`).
- [x] A role below the guard's `min_role` is rejected by `auth.require`.

## Commit

Predates commit-granular history (PR #10 bulk import).
