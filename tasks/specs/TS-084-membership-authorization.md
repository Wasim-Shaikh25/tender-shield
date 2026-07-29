# TS-084 — Membership authorization on all path-scoped workspace/project routes

**Status:** done
**Requirement:** [R-001 §A](../../specs/requirements/R-001-tenant-isolation.md)
**Spec(s) updated:** `specs/modules/auth.md`
**Module(s):** `auth`
**Severity / Gate:** P0 · Gate 1

## What this builds

Closes a cross-tenant authorization gap: several workspace/project routes
checked only "is this caller logged in / does this caller hold role X in
*their own* active workspace" instead of "is this caller actually a member
of the workspace/project named in the *path*." An admin of workspace A
could call `POST /workspaces/{B}/members` with workspace B's id and grant
themselves `owner` there.

## Current (the three defects, fixed by this task)

```python
# backend/app/modules/auth/router.py:215 (defect 1 — no membership check at all)
@router.get("/workspaces/{workspace_id}/members")
def list_workspace_members(
    workspace_id: str,
    principal: Principal = Depends(current_principal),   # only "is logged in"
):
    return _service(request, session).list_workspace_members(workspace_id)
    #                                                        ↑ path param, unchecked
```

```python
# backend/app/modules/auth/service.py:384 (defect 2 — no workspace filter)
def list_project_members(self, project_id) -> list[dict]:
    rows = self.s.execute(
        select(ProjectMember, User)
        .where(ProjectMember.project_id == project_id)   # workspace never consulted
    ).all()
```

```python
# backend/app/modules/auth/router.py:202 (defect 3 — role checked against the
# CALLER's own workspace, but the write targets the PATH workspace)
@router.post("/workspaces/{workspace_id}/members")
def add_workspace_member(
    workspace_id: str,
    principal: Principal = Depends(require("admin")),  # role in the CALLER's own workspace
):
    return _handle(lambda: _service(...).add_workspace_member(workspace_id, ...))
```

## Implementation

```python
# backend/app/modules/auth/deps.py
def require_workspace_member(min_role: str = "viewer"):
    """Authorize against the workspace named in the PATH, not the token."""
    def guard(workspace_id: str, session=Depends(get_session),
              principal=Depends(current_principal)) -> Principal:
        if principal.is_superadmin:
            return principal
        member = session.scalar(select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == uuid.UUID(workspace_id),
            WorkspaceMember.user_id == uuid.UUID(principal.user_id),
        ))
        if member is None:
            raise HTTPException(404, "not_found")   # 404, not 403 — no enumeration oracle
        if ROLE_RANK.get(member.role, -1) < ROLE_RANK[min_role]:
            raise HTTPException(403, "insufficient_role")
        bind_workspace_context(session, workspace_id)   # re-bind RLS to the path workspace
        return principal
    return guard

def require_project_member(min_role: str = "viewer"):
    """Resolves the project's workspace, then delegates to require_workspace_member."""
```

Routes converted: `GET/POST /workspaces/{id}/members`,
`GET/POST /workspaces/{id}/projects`, `GET/POST /projects/{id}/members` — all
switched from `current_principal`/`require(role)` to
`require_workspace_member`/`require_project_member`.
`list_project_members` also gained an explicit `workspace_id` filter as
defense in depth (not relying on the guard alone). Also added while in
here: an owner-demotion guard rejecting a role change that would leave a
workspace with zero owners.

## Files touched

- `backend/app/modules/auth/{deps,router,service}.py`

## Tests

- `backend/tests/modules/auth/test_deps.py::test_require_workspace_member`
- `backend/tests/modules/auth/test_service.py::test_cross_tenant_member_add_rejected`

## Acceptance criteria (R-001 §A, A1–A3, A7)

- [x] A caller who is not a member of the path workspace gets 404, not data.
- [x] A caller's role is evaluated against their membership in the *path*
      workspace, never their token's active-workspace role.
- [x] Demoting the last `owner` of a workspace is rejected.

## Commit

Predates commit-granular history (PR #10 bulk import).
