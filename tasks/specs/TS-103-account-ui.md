# TS-103 — Account UI: invitation accept, members, MFA, workspace/profile settings, admin console, audit viewer

**Status:** todo
**Requirement:** [R-013](../../specs/requirements/R-013-account-ui.md)
**Spec(s) updated:** none (to be updated when built)
**Module(s):** `auth`, frontend
**Severity / Gate:** P1 · Gate 3

## What this builds

A large batch of real, working backend capabilities that have no frontend
at all: workspace/project CRUD, member/invitation management, MFA
enrollment, Apple Sign-In, super-admin endpoints, and the audit trail — all
reachable only via direct API calls today.

## Implementation (reference plan — not yet built)

Highest priority: `/invitations/[token]` — without it, team sharing does
not work at all (the invite endpoints exist server-side with no accept UI).

```tsx
// frontend/app/invitations/[token]/page.tsx
export default function AcceptInvitation({ params }) {
  if (status === "unauthenticated") {
    // Signup, not login — an invitation email is often the invitee's first
    // contact with the product.
    return <Redirect to={`/signup?next=${encodeURIComponent(`/invitations/${token}`)}`} />;
  }
  ...
}
```

Distinguishes the backend's existing error codes with real copy —
`invalid_invitation`, `invitation_used`, and especially
`invitation_email_mismatch` ("This invitation was sent to alice@firm.com
but you're signed in as bob@firm.com"). Offers "Switch to <workspace>"
(TS-100) after acceptance.

Other pages in this batch: `/settings/team` (member table with role
dropdowns + inline role-help text, since `ROLE_RANK` is opaque to a
contractor; surfaces the last-owner-cannot-be-demoted guard from TS-084 and
seat-limit 402s from TS-098 via `<Paywall />`); `/settings/security`
(two-step TOTP enrollment per TS-101's design, recovery codes shown once
with a forced "I've saved these" confirmation, active-sessions list with
per-device revoke from TS-093); `/settings/workspace` (GST fields from
TS-096, danger zone: transfer ownership / delete workspace with typed
confirmation — must cancel an active subscription first); `/settings/
profile` (email re-verification via TS-099, account deletion — a DPDP
erasure-right gap with no code path today); `/admin` super-admin console
(workspace/user lists, coupon management — **no impersonation in v1**, the
fastest route to a cross-tenant incident); moving the inline `fetch` export
call into the API client so it gets the 401-refresh path from TS-092
(today an expired token during export downloads a file containing a JSON
error); an audit-trail viewer over TS-021's existing endpoint.

## Files touched (planned)

- `frontend/app/{invitations/[token],settings/*,admin}/page.tsx`
- `frontend/lib/api.ts` (`exportPack` moved off inline fetch)

## Tests (planned)

None planned beyond manual verification — frontend component/e2e tests are
a separate, later concern per this codebase's conventions to date.

## Acceptance criteria (R-013, A1–A11)

- [ ] An invited user can accept an invitation entirely through the UI,
      including the signup-first path for a new user.
- [ ] `/admin` has no impersonation capability in v1.
- [ ] Export requests get the 401-refresh path, never a downloaded
      JSON-error file.

## Commit

Not yet implemented.
