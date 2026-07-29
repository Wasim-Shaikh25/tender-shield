# TS-100 — Workspace switching: deterministic default, switch endpoint, UI switcher

**Status:** done
**Requirement:** [R-011](../../specs/requirements/R-011-workspace-switching.md)
**Spec(s) updated:** `specs/modules/auth.md`, `specs/modules/frontend`
**Module(s):** `auth`, frontend
**Severity / Gate:** P1 · Gate 2

## What this builds

Fixes a nondeterministic-login bug and adds the ability to actually switch
workspaces: since the workspace claim is baked into the access token and
binds RLS, switching necessarily means minting a new token — it can't be a
client-side selection.

## Current (the defect)

```python
# backend/app/modules/auth/service.py:80 (before this task)
member = self.s.scalar(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id))
# no ORDER BY — which workspace the user lands in is whatever the database
# returns first, and can change between logins for the same user
```

## Implementation

```python
# backend/app/modules/auth/models.py — User
default_workspace_id: Mapped[uuid.UUID | None]
last_workspace_id: Mapped[uuid.UUID | None]
```

```python
def _resolve_login_workspace(self, user: User) -> WorkspaceMember | None:
    """Order: explicit default → last used → oldest membership (deterministic
    tiebreak on Workspace.created_at)."""
    for candidate in (user.default_workspace_id, user.last_workspace_id):
        if candidate:
            member = self._workspace_member(candidate, user.id)
            if member: return member
    return self.s.scalar(select(WorkspaceMember).join(Workspace, ...)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(Workspace.created_at.asc()).limit(1))
```

```python
@router.post("/workspaces/{workspace_id}/switch")
def switch_workspace(...):
    """Re-issues tokens scoped to another workspace the caller belongs to.
    Membership verified server-side — the client cannot select a workspace
    by editing a token, since the workspace claim is what binds RLS."""

def switch_workspace(self, user_id, workspace_id, *, refresh_token=None) -> dict:
    member = self._workspace_member(workspace_id, user_id)
    if not member:
        raise AuthError("not_workspace_member")      # 404, per R-001 §B2
    user.last_workspace_id = uuid.UUID(str(workspace_id))
    # Retire the old family — one active session per user at a time keeps
    # reuse-detection simple; a switch cannot leave a stale token scoped to
    # the previous workspace in play. (Deliberate trade-off: a user cannot
    # hold two workspaces open in two tabs simultaneously.)
    if refresh_token:
        old = self.s.scalar(select(RefreshToken).where(RefreshToken.token_hash == rf.hash_token(refresh_token)))
        if old: self._revoke_family(old.family_id)
    tokens = self._issue_tokens(user.id, member.workspace_id, member.role, new_family=True)
    self.s.commit()
    return tokens
```

`GET /auth/workspaces` returns `{workspace_id, name, role, plan,
is_current}` per membership so the frontend switcher renders without a
second call.

```tsx
// frontend/components/workspace-switcher.tsx
async function switchTo(id: string) {
  const tokens = await api.switchWorkspace(session.token, id, session.refreshToken);
  adoptTokens(tokens);
  // Every cached query is workspace-scoped — dropping the cache prevents
  // workspace A's data appearing under workspace B's header, which would
  // read as a data leak even though the server never sent it.
  queryClient.clear();
  router.replace("/dashboard");
}
```

Hidden entirely when the user belongs to only one workspace.

## Files touched

- `backend/app/modules/auth/{models,service,router}.py`
- `frontend/components/workspace-switcher.tsx`
- `backend/migrations/versions/2a3786dab2f5_workspace_switching_user_columns.py`

## Tests

- `backend/tests/modules/auth/test_service.py::test_deterministic_login_workspace`,
  `test_switch_workspace_retires_old_family`

## Acceptance criteria (auth.md A17–A23, frontend.md A16–A17)

- [x] Repeated logins for the same user land on the same workspace
      (deterministic order, no more DB-order dependence).
- [x] Switching workspace requires real membership, verified server-side.
- [x] The client-side query cache is cleared on switch so no stale
      workspace data renders under the new workspace's header.

## Commit

Predates commit-granular history (PR #10 bulk import).
