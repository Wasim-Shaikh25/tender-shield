# R-001 — Tenant isolation: membership authorization + working RLS

**Status:** implemented (TS-084, TS-086 both done — see erratum below for
where the shipped implementation differs from this draft)
**Severity:** P0 — cross-tenant data leak and privilege escalation
**Requirement refs:** Doc §3.2, §5; `CLAUDE.md` §4 ("cross-tenant leakage is company-ending")
**Task refs:** TS-084 (authorization), TS-086 (RLS)
**Task files:** code-level detail (current-vs-target snippets, file:line, files touched, tests) now lives per-task, split out by TS-126's restructure: [TS-084](../../tasks/specs/TS-084-membership-authorization.md), [TS-086](../../tasks/specs/TS-086-rls-hardening.md). This document stays the business/behavior-level record (purpose, target behavior, acceptance criteria).

**Gap refs:** `docs/GAP_ANALYSIS.md` §1.1–§1.4
**Specs updated:** `specs/modules/auth.md`, `specs/data-model.md`

## Erratum — three things the implementation found that this draft didn't anticipate

Found by testing against a real (non-superuser) PostgreSQL role rather than
trusting the design on paper. Each is a real bug that would have shipped if
the §B code below had been implemented literally.

1. **`SET LOCAL app.workspace_id = :param` is a PostgreSQL syntax error.**
   `SET` only accepts a literal, never a bind parameter. Every code sample in
   §B.5/§B.6 below using this form is wrong. The shipped fix uses
   `set_config('app.workspace_id', :workspace_id, true)` — a normal function
   call, which does accept parameters, with `is_local=true` giving the same
   transaction-scoped lifetime as `SET LOCAL`.
2. **`after_commit` cannot emit SQL.** §B.5's rebinding listener as drafted
   uses `event.listens_for(session_factory, "after_commit")` and calls
   `session.execute(...)` from inside it — SQLAlchemy's own docs say the
   session has no active transaction when `after_commit` fires. It raises
   `"session is in 'committed' state"`. The shipped fix uses `after_begin`
   instead, which is the documented hook for populating per-transaction
   session state and fires exactly when a new transaction starts (i.e.
   immediately after the prior one committed).
3. **A plain single-workspace predicate on `workspaces`/`workspace_members`
   breaks `list_workspaces`.** This draft's §B.3 gives both tables the same
   `workspace_id = bound` predicate as every other table. That's wrong for
   these two specifically: a user's own workspace memberships legitimately
   span *multiple* workspaces, and `list_workspaces` must show all of them —
   not just whichever one happens to be bound to the current session. The
   shipped fix uses a compound predicate on both tables (bound workspace OR
   the caller's own row/membership — see `workspaces_rls_statements` /
   `workspace_members_rls_statements` in `app/core/db.py`), backed by a second
   session-scoped GUC, `app.user_id`, bound once per request at
   `authenticate()`. This in turn exposed a fourth issue: `login`, `refresh`,
   and Apple sign-in's existing-user branch are unauthenticated entry
   points — `authenticate()` never runs for them — so each now binds
   `app.user_id` explicitly before its first `WorkspaceMember` query, and
   every workspace-creation path (`signup`, `create_workspace`, Apple
   sign-in's new-user branch) goes through one helper,
   `AuthService._create_workspace_and_owner`, which binds `app.workspace_id`
   to the new workspace's own pre-generated id before inserting it — there is
   no workspace to bind to until that insert creates one, so `WITH CHECK`
   would otherwise reject workspace creation entirely.

All four are covered by `tests/test_rls_postgres.py` (9 tests) and validated
against a real, non-superuser PostgreSQL role — a superuser bypasses RLS
regardless of `FORCE`, which would have made the whole test suite pass
vacuously against a misconfigured role.

The rest of this document is the original design; read it with the erratum in
mind — the numbered predicates in §B.5 below are the intent, and `app/core/db.py`
is the corrected, shipped implementation.

## Purpose

Three auth routes trust a workspace/project id taken from the URL path without
checking that the caller belongs to that workspace, and the RLS layer that is
supposed to be the backstop does not actually isolate anything. This document
closes both layers: an explicit application-level check on every path-scoped
route, and a database policy that holds even when the application forgets.

Defence in depth is the point — either layer alone has failed here before.

---

## Part A — Application-level authorization (TS-084)

### A.1 Current — the three defects

**Defect 1: any authenticated user can read any workspace's members.**

```python
# backend/app/modules/auth/router.py:215
@router.get("/workspaces/{workspace_id}/members")
def list_workspace_members(
    workspace_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),   # ← only "is logged in"
):
    return _service(request, session).list_workspace_members(workspace_id)
    #                                                        ↑ path param, unchecked
```

`AuthService.list_workspace_members` (`service.py:310`) filters on that id alone
and returns `{user_id, email, role}` per member. Iterating workspace UUIDs
enumerates the customer base and every user's email.

**Defect 2: project members leak with no workspace filter at all.**

```python
# backend/app/modules/auth/service.py:384
def list_project_members(self, project_id) -> list[dict]:
    project_id = uuid.UUID(str(project_id))
    rows = self.s.execute(
        select(ProjectMember, User)
        .join(User, ProjectMember.user_id == User.id)
        .where(ProjectMember.project_id == project_id)   # ← workspace never consulted
    ).all()
```

**Defect 3: cross-tenant privilege escalation.**

```python
# backend/app/modules/auth/router.py:202
@router.post("/workspaces/{workspace_id}/members")
def add_workspace_member(
    workspace_id: str,
    body: AddMemberBody,
    ...
    principal: Principal = Depends(require("admin")),  # ← role in the CALLER's own workspace
):
    return _handle(
        lambda: _service(request, session).add_workspace_member(workspace_id, body.email, body.role)
        #                                                       ↑ but writes to the PATH workspace
    )
```

An admin of workspace A calls this with workspace B's id and `role="owner"` and
gains full access to another tenant's tenders.

`create_project` (`service.py:321`) already does this correctly — it is the
pattern to copy:

```python
if not self._workspace_member(workspace_id, user_id):
    raise AuthError("not_workspace_member")
```

### A.2 Target — a reusable path-scope guard

Add one dependency that resolves the caller's membership in the **path**
workspace, and use it on every path-scoped route.

```python
# backend/app/modules/auth/deps.py  (append)

from app.modules.auth.rbac import ROLE_RANK


def require_workspace_member(min_role: str = "viewer"):
    """Authorize against the workspace named in the PATH, not the token.

    `require(...)` checks the role the caller holds in their *own* active
    workspace. Any route that takes a workspace_id/project_id path parameter
    must additionally prove membership of that workspace (gap R-001 §A.1).
    Superadmins bypass by design (Doc §16 admin console).
    """

    def guard(
        workspace_id: str,
        session: Session = Depends(get_session),
        principal: Principal = Depends(current_principal),
    ) -> Principal:
        if principal.is_superadmin:
            return principal
        member = session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == uuid.UUID(workspace_id),
                WorkspaceMember.user_id == uuid.UUID(principal.user_id),
            )
        )
        if member is None:
            # 404, not 403: a non-member must not learn the workspace exists.
            raise HTTPException(404, "not_found")
        if ROLE_RANK.get(member.role, -1) < ROLE_RANK[min_role]:
            raise HTTPException(403, "insufficient_role")
        # Re-bind RLS to the workspace actually being addressed.
        bind_workspace_context(session, workspace_id)
        return principal

    return guard
```

Two design points worth keeping:

- **404 rather than 403 for non-members.** A 403 confirms the workspace exists,
  which is itself an enumeration oracle.
- **The role is read from the database, not the token.** The token carries the
  role for the caller's *active* workspace; a user may hold a different role in
  the workspace being addressed.

For project-scoped routes, resolve the project's workspace first:

```python
def require_project_member(min_role: str = "viewer"):
    def guard(
        project_id: str,
        session: Session = Depends(get_session),
        principal: Principal = Depends(current_principal),
    ) -> Principal:
        project = session.scalar(select(Project).where(Project.id == uuid.UUID(project_id)))
        if project is None:
            raise HTTPException(404, "not_found")
        return require_workspace_member(min_role)(
            str(project.workspace_id), session=session, principal=principal
        )

    return guard
```

### A.3 Routes to convert

| Route | Today | Required |
|---|---|---|
| `GET /auth/workspaces/{id}/members` | `current_principal` | `require_workspace_member("viewer")` |
| `POST /auth/workspaces/{id}/members` | `require("admin")` | `require_workspace_member("admin")` |
| `POST /auth/workspaces/{id}/projects` | `require("admin")` | `require_workspace_member("admin")` |
| `GET /auth/workspaces/{id}/projects` | `current_principal` | `require_workspace_member("viewer")` |
| `GET /auth/projects/{id}/members` | `current_principal` | `require_project_member("viewer")` |
| `POST /auth/projects/{id}/members` | `require("admin")` | `require_project_member("admin")` |

`list_project_members` must also filter by workspace defensively:

```python
def list_project_members(self, workspace_id, project_id) -> list[dict]:
    rows = self.s.execute(
        select(ProjectMember, User)
        .join(User, ProjectMember.user_id == User.id)
        .where(
            ProjectMember.project_id == uuid.UUID(str(project_id)),
            ProjectMember.workspace_id == uuid.UUID(str(workspace_id)),  # ← added
        )
    ).all()
```

### A.4 Owner-demotion guard

While in here: `add_workspace_member` can currently demote the last `owner`,
orphaning the workspace. Add:

```python
if existing and existing.role == "owner" and role != "owner":
    owners = self.s.scalar(
        select(func.count()).select_from(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.role == "owner",
        )
    )
    if owners <= 1:
        raise AuthError("last_owner")   # → 400
```

---

## Part B — RLS that actually isolates (TS-086)

### B.1 Current — three reasons the policy does nothing

```python
# backend/app/core/db.py:59
def rls_statements(table: str) -> list[str]:
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        (
            f"CREATE POLICY workspace_isolation ON {table} "
            "USING (workspace_id = current_setting('app.workspace_id')::uuid)"
        ),
    ]
```

1. **No `FORCE ROW LEVEL SECURITY`.** PostgreSQL exempts the table owner from
   RLS. The application connects as the role that ran `alembic upgrade head`,
   which owns the tables — so in the default deployment the policies are inert.
2. **No `WITH CHECK`.** `USING` filters reads only; an `INSERT`/`UPDATE` may
   still write a row carrying another workspace's `workspace_id`.
3. **Key tables are not covered.** `WORKSPACE_SCOPED_TABLES` is populated by
   `WorkspaceScopedMixin.__tablename__` (`db.py:46`), and these are plain `Base`
   subclasses so they never register:
   `workspaces`, `workspace_members`, `project_members`, `users`,
   `refresh_tokens`, `password_resets`.

### B.2 Target — policy generator

```python
# backend/app/core/db.py  (replace rls_statements)

def rls_statements(table: str, *, id_column: str = "workspace_id") -> list[str]:
    """RLS enable + workspace-isolation policy for one table (PostgreSQL only).

    FORCE is required: without it PostgreSQL exempts the table owner, and the
    application connects as the owner in every deployment we ship (R-001 §B.1).
    WITH CHECK is required so a write cannot place a row in another workspace.
    current_setting(..., true) returns NULL when unbound; comparing to NULL
    yields no rows, so an unbound session fails closed rather than erroring.
    """
    predicate = (
        f"{id_column} = NULLIF(current_setting('app.workspace_id', true), '')::uuid"
    )
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        f"DROP POLICY IF EXISTS workspace_isolation ON {table}",
        f"CREATE POLICY workspace_isolation ON {table} "
        f"USING ({predicate}) WITH CHECK ({predicate})",
    ]
```

`workspaces` keys on its own `id`, so it uses `id_column="id"`.

### B.3 Tables and their policy column

| Table | Policy column | Note |
|---|---|---|
| all current `WORKSPACE_SCOPED_TABLES` | `workspace_id` | unchanged |
| `workspaces` | `id` | the tenant row itself |
| `workspace_members` | `workspace_id` | add `WorkspaceScopedMixin`-equivalent coverage |
| `project_members` | `workspace_id` | column already exists (`auth/models.py:93`) |
| `invitations` | `workspace_id` | already scoped |
| `users` | — | **not** workspace-scoped (a user may join many workspaces); protected by application logic only |
| `refresh_tokens`, `password_resets` | — | user-scoped, never workspace-queried |

`workspace_members` and `project_members` cannot simply adopt
`WorkspaceScopedMixin` — they already declare `workspace_id` as part of a
composite primary key, and the mixin's `__tablename__` directive would fight the
existing `__tablename__`. Register them explicitly instead:

```python
# backend/app/core/db.py
WORKSPACE_SCOPED_TABLES: set[str] = set()

# Tables that carry a workspace column but are not WorkspaceScopedMixin
# subclasses (composite PKs / the tenant row itself). Kept explicit so the
# RLS migration cannot silently miss them again (R-001 §B.3).
EXTRA_RLS_TABLES: dict[str, str] = {
    "workspaces": "id",
    "workspace_members": "workspace_id",
    "project_members": "workspace_id",
}
```

### B.4 New migration

```python
"""rls hardening: FORCE + WITH CHECK + missing tables

Revision ID: f1a2b3c4d5e6
Revises: ca05e77bd02c
"""
from alembic import op
from app.core.db import EXTRA_RLS_TABLES, WORKSPACE_SCOPED_TABLES, rls_statements

revision = "f1a2b3c4d5e6"
down_revision = "ca05e77bd02c"


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in sorted(WORKSPACE_SCOPED_TABLES):
        for stmt in rls_statements(table):
            op.execute(stmt)
    for table, col in EXTRA_RLS_TABLES.items():
        for stmt in rls_statements(table, id_column=col):
            op.execute(stmt)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in sorted(WORKSPACE_SCOPED_TABLES) + list(EXTRA_RLS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS workspace_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
```

Migrations must import module models so `WORKSPACE_SCOPED_TABLES` is populated —
`migrations/env.py` already auto-discovers each module's `models.py`.

### B.5 The `SET LOCAL` lifetime problem

`bind_workspace_context` (`db.py:70`) issues `SET LOCAL`, which is scoped to the
**current transaction**. Services in this codebase commit mid-request —
`AuthService.signup` (`service.py:67`), `BillingService.record_usage`
(`service.py:50`), `WorkspaceAdmin.set_plan` (`workspaces.py:33`) all do. After
that commit the binding is gone, and with FORCE enabled the next statement sees
`current_setting('app.workspace_id', true) → NULL` and silently returns zero rows.

That is fail-closed, which is the right direction, but it will present as
"my data disappeared" bugs. Rebind after commit with a session event listener:

```python
# backend/app/core/db.py

def install_rls_rebinding(session_factory: sessionmaker) -> None:
    """Re-apply SET LOCAL after every commit.

    SET LOCAL dies with its transaction, and services commit mid-request, so a
    single bind at authenticate() time does not survive the request (R-001 §B.5).
    """
    from sqlalchemy import event

    @event.listens_for(session_factory, "after_commit")
    def _rebind(session: Session) -> None:
        workspace_id = session.info.get("workspace_id")
        if workspace_id and session.get_bind().dialect.name == "postgresql":
            session.execute(
                text("SET LOCAL app.workspace_id = :w"), {"w": str(workspace_id)}
            )


def bind_workspace_context(session: Session, workspace_id) -> None:
    session.info["workspace_id"] = str(workspace_id)   # ← remember for rebinding
    if session.get_bind().dialect.name != "postgresql":
        return
    session.execute(text("SET LOCAL app.workspace_id = :w"), {"w": str(workspace_id)})
```

Wire `install_rls_rebinding` in `create_app` right after
`make_session_factory` (`main.py:30`).

### B.6 Superadmin and the zero-UUID sentinel

`AuthService._issue_tokens` gives a workspace-less superadmin
`_NO_WORKSPACE = "00000000-0000-0000-0000-000000000000"` (`service.py:229`), and
`BillingService._log` uses `uuid.UUID(int=0)` for unattributed webhook rows
(`billing/service.py:191`). These are the same value, so superadmin queries and
orphaned payment logs collide in one pseudo-workspace.

Required:
- Superadmin routes must run on a session bound with a dedicated Postgres role
  that holds `BYPASSRLS`, **or** explicitly bind each workspace they inspect.
  Do not special-case the zero UUID in the policy — a bypass predicate in the
  policy is exactly the kind of thing that gets exploited later.
- Give billing its own sentinel (`UNATTRIBUTED_WORKSPACE`) and exclude
  `payment_log` rows carrying it from customer-facing queries.

---

## Behavior

- **B1** Every route taking a `workspace_id` or `project_id` path parameter
  authorizes the caller's membership of *that* workspace before acting.
- **B2** Non-members receive `404 not_found`, never `403`, so existence is not
  disclosed.
- **B3** The effective role is read from `workspace_members` at request time, not
  from the JWT.
- **B4** Every workspace-scoped table carries an RLS policy with both `USING` and
  `WITH CHECK`, and `FORCE ROW LEVEL SECURITY`.
- **B5** An unbound session sees zero rows (fail closed), never another
  workspace's rows.
- **B6** The RLS binding survives mid-request commits.
- **B7** The last `owner` of a workspace cannot be demoted or removed.

## Acceptance criteria

- **A1** A user in workspace A calling `GET /auth/workspaces/{B}/members` gets
  `404`. Test: `test_auth_security.py::test_member_list_is_workspace_scoped`.
- **A2** An admin of A calling `POST /auth/workspaces/{B}/members` with
  `role="owner"` gets `404` and no `workspace_members` row is created.
- **A3** `GET /auth/projects/{id}/members` for a project in another workspace
  returns `404`.
- **A4** Against **PostgreSQL**, a session bound to workspace A cannot
  `SELECT` or `UPDATE` a findings row belonging to B, and an `INSERT` carrying
  B's `workspace_id` is rejected by `WITH CHECK`.
- **A5** A session with no binding returns zero rows from every scoped table.
- **A6** After a service performs a mid-request `commit()`, a subsequent query
  in the same request still sees the caller's own rows.
- **A7** Demoting the sole owner returns `400 last_owner`.
- **A8** `alembic upgrade head && alembic downgrade base` succeeds on PostgreSQL.

## Test scaffolding — the Postgres CI job

A1–A3 run on SQLite. **A4–A6 cannot** — `bind_workspace_context` is a documented
no-op on SQLite (`db.py:76`), so the current CI has never once exercised
isolation. Add a Postgres service to `.github/workflows/ci.yml`:

```yaml
  backend-postgres:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: tendershield_test
        options: >-
          --health-cmd pg_isready --health-interval 10s
          --health-timeout 5s --health-retries 5
        ports: ["5432:5432"]
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11", cache: pip }
      - run: pip install -e ".[dev]" psycopg[binary]
      - name: Migrate
        env:
          TS_DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/tendershield_test
        run: alembic upgrade head
      - name: RLS isolation tests
        env:
          TS_DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/tendershield_test
        run: pytest -q -m postgres
```

Mark the tests `@pytest.mark.postgres` and register the marker in
`pyproject.toml` so the SQLite job skips them:

```toml
[tool.pytest.ini_options]
markers = ["postgres: requires a real PostgreSQL server (RLS isolation)"]
addopts = "-m 'not postgres'"
```

Sketch of the isolation test:

```python
@pytest.mark.postgres
def test_rls_blocks_cross_workspace_read(pg_session):
    a, b = uuid.uuid4(), uuid.uuid4()
    bind_workspace_context(pg_session, a)
    pg_session.add(FindingRow(workspace_id=a, opportunity_id=uuid.uuid4(), ...))
    pg_session.commit()

    bind_workspace_context(pg_session, b)
    assert pg_session.scalars(select(FindingRow)).all() == []

    with pytest.raises(ProgrammingError):          # WITH CHECK violation
        pg_session.add(FindingRow(workspace_id=a, ...))
        pg_session.flush()
```

## Out of scope

- Column-level encryption of tender text (Phase 3).
- Per-project RLS (projects are a sub-scope of a workspace; workspace-level
  isolation is the security boundary).
- Superadmin `BYPASSRLS` role provisioning — tracked in R-016 (deployment).

## Assumptions

- `assumption:` The application connects to PostgreSQL as the schema owner. If a
  deployment uses a separate low-privilege application role, `FORCE` is
  belt-and-braces rather than load-bearing — keep it regardless.
