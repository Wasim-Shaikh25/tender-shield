# R-011 — Workspace switching

**Status:** implemented (TS-100) — see `specs/modules/auth.md` §B18-B19 and
`specs/frontend.md` §B13 for behavior/acceptance criteria. One deviation
from this draft: the `WorkspaceSwitcher` calls `signIn()` (the same tokens-
adoption path login already uses) rather than a separate `adoptTokens`
export, and redirects to `/opportunities` (this app's actual home route)
rather than the draft's `/dashboard`, which doesn't exist.
**Severity:** P1 — multi-workspace users cannot reach most of their workspaces
**Requirement refs:** Doc §5, §16
**Task refs:** TS-100
**Task files:** code-level detail (current-vs-target snippets, file:line, files touched, tests) now lives per-task, split out by TS-126's restructure: [TS-100](../../tasks/specs/TS-100-workspace-switching.md). This document stays the business/behavior-level record (purpose, target behavior, acceptance criteria).

**Gap refs:** `docs/GAP_ANALYSIS.md` §3.2
**Specs to update:** `specs/modules/auth.md`, `specs/frontend.md`

## Purpose

A user who belongs to several workspaces lands in an arbitrary one and has no way
to reach the others. `GET /auth/workspaces` lists them; nothing can mint a token
for a different one. Persona P3 in the product overview — a QS consultancy
working across client workspaces — cannot use the product as designed.

## Current

```python
# backend/app/modules/auth/service.py:80
member = self.s.scalar(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id))
if not member:
    ...
return self._issue_tokens(user.id, member.workspace_id, member.role, ...)
```

No `ORDER BY`. Which workspace the user lands in is whatever the database returns
first, and it can change between logins for the same user — a genuinely
confusing bug to report and to debug.

The workspace is baked into the access token as the `workspace` claim
(`security.mint_access`), and `authenticate` binds RLS from that claim
(`auth/deps.py:32`). So switching workspace necessarily means minting a new
token; it cannot be a client-side selection.

## Target

### B.1 Deterministic default workspace

```python
# backend/app/modules/auth/models.py — User
default_workspace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
last_workspace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
```

```python
def _resolve_login_workspace(self, user: User) -> WorkspaceMember | None:
    """Pick the workspace to sign into, deterministically.

    Order: explicit default → last used → oldest membership. The current code
    takes whatever row the database returns first, so the same user can land in
    a different workspace between logins (R-011 §Current).
    """
    for candidate in (user.default_workspace_id, user.last_workspace_id):
        if candidate:
            member = self._workspace_member(candidate, user.id)
            if member:
                return member
    return self.s.scalar(
        select(WorkspaceMember)
        .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(Workspace.created_at.asc())      # ← deterministic tiebreak
        .limit(1)
    )
```

### B.2 The switch endpoint

```python
@router.post("/workspaces/{workspace_id}/switch")
def switch_workspace(
    workspace_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    """Re-issue tokens scoped to another workspace the caller belongs to.

    Membership is verified server-side; the client cannot select a workspace by
    editing a token, because the workspace claim is what binds RLS
    (auth/deps.py:32).
    """
    return _handle(lambda: _service(request, session).switch_workspace(
        principal.user_id, workspace_id, refresh_token=body.refresh_token))
```

```python
def switch_workspace(self, user_id, workspace_id, *, refresh_token: str | None = None) -> dict:
    member = self._workspace_member(workspace_id, user_id)
    if not member:
        raise AuthError("not_workspace_member")      # → 404, per R-001 §B2
    user = self.s.get(User, uuid.UUID(str(user_id)))
    user.last_workspace_id = uuid.UUID(str(workspace_id))

    # Retire the old family: one active session per user at a time keeps the
    # reuse-detection model simple and means a switch cannot leave a stale
    # token scoped to the previous workspace in play.
    if refresh_token:
        old = self.s.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == rf.hash_token(refresh_token))
        )
        if old:
            self._revoke_family(old.family_id)

    tokens = self._issue_tokens(
        user.id, member.workspace_id, member.role,
        is_superadmin=user.is_superadmin, new_family=True,
    )
    self.s.commit()
    return tokens
```

Retiring the old family is a deliberate trade-off: it means a user cannot hold
two workspaces open in two tabs. The alternative — concurrent families per
workspace — interacts badly with the reuse-detection model in
`auth/refresh.py` and with the single-flight refresh in R-010 §B.2. If
simultaneous multi-workspace tabs become a real customer need, revisit by scoping
families per workspace rather than per user.

### B.3 Role is per workspace

`Principal.role` comes from the token. A user may be `owner` in workspace A and
`viewer` in workspace B. After switching, the token carries B's role — so the UI
must re-read `/auth/me` and re-render permission-gated controls rather than
caching the role from login.

`GET /auth/workspaces` should return enough to render the switcher without a
second call:

```json
{"workspaces": [
  {"workspace_id": "…", "name": "Acme Infra", "role": "owner",  "plan": "pro",  "is_current": true},
  {"workspace_id": "…", "name": "Client XYZ", "role": "viewer", "plan": "free", "is_current": false}
]}
```

### B.4 Frontend switcher

```tsx
// frontend/components/workspace-switcher.tsx

export function WorkspaceSwitcher() {
  const { session, adoptTokens } = useSession();
  const { data } = useWorkspaces();
  const router = useRouter();

  async function switchTo(id: string) {
    const tokens = await api.switchWorkspace(session.token, id, session.refreshToken);
    adoptTokens(tokens);
    // Every cached query is workspace-scoped. Dropping the cache is not a
    // nicety — showing workspace A's tenders under workspace B's header would
    // read as a data leak even though the server never sent it (R-011 §B.4).
    queryClient.clear();
    router.replace("/dashboard");
  }
  ...
}
```

Placed in the app header, visible on every authenticated page, showing the
current workspace name and plan badge. Hidden entirely when the user belongs to
one workspace — a switcher with one option is noise.

### B.5 Related gaps closed here

- **`no_workspace` dead end.** A user whose only membership is removed gets
  `401 no_workspace` at login (`service.py:86`) with no route back. Instead,
  issue a token with no workspace and land them on `/workspaces/new`, where they
  can create one or accept a pending invitation.
- **Invitation acceptance across workspaces.** `accept_invitation` adds the
  membership but leaves the user's token scoped to the old workspace. After
  accepting, offer "Switch to <workspace>".

## Behavior

- **B1** Login resolves the workspace deterministically: default → last used →
  oldest.
- **B2** `POST /auth/workspaces/{id}/switch` verifies membership server-side and
  re-issues tokens carrying that workspace's role.
- **B3** Non-members receive `404`, consistent with R-001 §B2.
- **B4** Switching retires the previous refresh family.
- **B5** The client clears all cached workspace-scoped data on switch.
- **B6** A user with no workspace receives a workspace-less token and is routed
  to workspace creation rather than being locked out.
- **B7** The switcher is hidden for single-workspace users.

## Acceptance criteria

- **A1** A user in three workspaces logs in twice and lands in the same
  workspace both times.
- **A2** `POST /auth/workspaces/{B}/switch` returns tokens whose `workspace`
  claim is B and whose `role` is the caller's role in B.
- **A3** Switching to a workspace the user does not belong to returns `404`.
- **A4** After switching, `GET /ingestion/opportunities` returns only B's
  opportunities.
- **A5** The pre-switch refresh token returns `401` afterwards.
- **A6** A user who is `owner` in A and `viewer` in B cannot create an
  opportunity after switching to B.
- **A7** A user with zero memberships logs in and reaches `/workspaces/new`.
- **A8** The switcher does not render for a single-workspace user.

## Out of scope

- Simultaneous multi-workspace sessions in separate tabs (see §B.2).
- Cross-workspace search or reporting.
- Workspace transfer / merge.

## Assumptions

- `assumption:` One active session per user. Revisit if consultancies ask for
  side-by-side workspaces.
