# R-013 — Account UI: invitations, members, MFA, workspaces, admin console

**Status:** draft
**Severity:** P1 — implemented backend features are unreachable
**Requirement refs:** Doc §5, §16
**Task refs:** TS-103
**Task files:** code-level detail (current-vs-target snippets, file:line, files touched, tests) now lives per-task, split out by TS-126's restructure: [TS-103](../../tasks/specs/TS-103-account-ui.md). This document stays the business/behavior-level record (purpose, target behavior, acceptance criteria).

**Gap refs:** `docs/GAP_ANALYSIS.md` §4.5
**Specs to update:** `specs/frontend.md`

## Purpose

A large set of working backend endpoints has no user interface, so the features
effectively do not exist. Most striking: `POST /auth/invitations` issues a token
and there is **no page to redeem it on** — an invited colleague receives a token
they cannot use.

## What exists server-side with no UI

| Capability | Endpoints | UI today |
|---|---|---|
| Workspace CRUD | `POST/GET /auth/workspaces` | none — created implicitly at signup |
| Members | `POST/GET /auth/workspaces/{id}/members` | none |
| Projects | `POST/GET /auth/workspaces/{id}/projects` | none |
| Project members | `POST/GET /auth/projects/{id}/members` | none |
| Invitations | `POST /auth/invitations`, `POST /auth/invitations/{token}/accept` | none |
| MFA | `POST /auth/mfa/enroll`, `/verify` | none |
| Apple Sign-In | `GET /auth/apple/authorize`, `POST /auth/apple/callback` | none |
| Super-admin | `GET/POST /auth/admin/*` | none |
| Audit trail | `GET /review/opportunities/{id}/audit` | none |
| Export download | `GET /export/opportunities/{id}` | raw `fetch` inline (`opportunities/[id]/page.tsx:129`) |

Note on Apple Sign-In: it is fully implemented server-side and has no button.
Worth flagging as a sequencing observation rather than a defect — for an
India-first SMB product, Google and phone OTP (TS-036) matter far more than
Apple, and this looks like build order driven by what was implementable without
credentials rather than by user need.

## Pages

### 1. `/invitations/[token]` — accept an invitation (highest priority)

The gap that most obviously breaks a flow: without this page, team sharing does
not work at all.

```tsx
// frontend/app/invitations/[token]/page.tsx

export default function AcceptInvitation({ params }: { params: Promise<{ token: string }> }) {
  const { session, status } = useSession();
  const { token } = use(params);

  // Not signed in → send to signup/login and come back. The invitation email
  // is often the invitee's first contact with the product, so the signup path
  // must be the default, not the login path (R-013 §1).
  if (status === "unauthenticated") {
    return <Redirect to={`/signup?next=${encodeURIComponent(`/invitations/${token}`)}`} />;
  }
  ...
}
```

Error states the backend already distinguishes, each needing its own copy:
`invalid_invitation` (bad or expired), `invitation_used`,
`invitation_email_mismatch` — the last is the confusing one and needs explicit
help: *"This invitation was sent to alice@firm.com but you're signed in as
bob@firm.com. Sign out and sign in as alice@firm.com."*

After acceptance, offer "Switch to <workspace>" (R-011 §B.5).

### 2. `/settings/team` — members and invitations (admin)

Table of members with role dropdowns; pending invitations with copy-link and
revoke; an invite form; seat usage from R-009.

```tsx
const ROLE_HELP: Record<string, string> = {
  owner:     "Full control, including billing and deleting the workspace.",
  admin:     "Manage members and settings. Cannot delete the workspace.",
  estimator: "Upload tenders and run reviews.",
  reviewer:  "Review and accept findings. Cannot run new reviews.",
  viewer:    "Read-only.",
};
```

Roles need this help text inline. `ROLE_RANK` (`auth/rbac.py:7`) is meaningful to
the codebase and opaque to a contractor — "estimator" vs "reviewer" is not
self-evident, and picking wrong either blocks someone's work or over-grants.

Guards to surface: the last owner cannot be demoted (R-001 §A.4), and seat limits
return 402 → `<Paywall />` (R-009 §B.3).

### 3. `/settings/security` — MFA and sessions

Two-step TOTP enrollment per R-002 §D.4: password confirm → QR + manual secret →
verify a code → **recovery codes shown once**, with a forced "I've saved these"
confirmation. Losing recovery codes is a support ticket that ends in account
recovery, so the interstitial should be deliberately hard to skip.

Also: active sessions list with per-device revoke and "sign out everywhere"
(R-002 §B.3), and a change-password form.

### 4. `/settings/workspace` — profile and billing identity

Name, country, and the GST fields R-007 §B.1 requires: legal name, GSTIN (with
inline checksum validation), billing address, place of supply. Also the danger
zone: transfer ownership, delete workspace (typed confirmation, explicit warning
that tender data is deleted).

Deleting a workspace with an active paid subscription must cancel it first — an
orphaned subscription billing a deleted workspace is the kind of thing that ends
up on social media.

### 5. `/settings/profile` — the user

Email (with re-verification on change, R-015), name, phone, notification
preferences, default workspace (R-011 §B.1), and account deletion.

Account deletion is not optional: DPDP gives data principals an erasure right and
there is no code path for it today (`docs/GAP_ANALYSIS.md` §1.10). Sole-owner
workspaces must be transferred or deleted first.

### 6. `/admin` — super-admin console

`require_superadmin` (`auth/deps.py:47`) protects a real API with no UI. Minimum:
workspace list with plan/usage/created; user list with superadmin toggle;
coupon management (R-006); comp a workspace; impersonation-free support view.

**No impersonation in v1.** It is the fastest route to a cross-tenant incident,
and every workspace here holds commercially sensitive tender data. If support
needs it later it must be time-boxed, workspace-owner-approved, and written to
the audit log on every request.

### 7. Export via the API client

```ts
// frontend/lib/api.ts
exportPack: async (token: string, id: string, format: "xlsx" | "docx" | "pdf") => {
  const res = await fetch(`${API_BASE}/export/opportunities/${id}?format=${format}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw await toApiError(res);      // 403 review_incomplete → real copy
  return { blob: await res.blob(), filename: parseFilename(res.headers) };
},
```

Moves the inline `fetch` (`opportunities/[id]/page.tsx:129`) into the client so it
gets the 401-refresh path from R-010 §B.3 — today an expired token during export
produces a downloaded file containing a JSON error.

### 8. Audit trail viewer

`GET /review/opportunities/{id}/audit` returns an append-only log that nothing
displays. Surface it as a timeline on the opportunity page. For a product whose
value is defensible decisions, "who accepted this finding and when" is a
feature, not diagnostics.

## Behavior

- **B1** Every implemented backend capability has a reachable UI, or is
  explicitly deferred in `specs/frontend.md`.
- **B2** Invitation acceptance works end to end, including for users without an
  account.
- **B3** Role selection carries plain-language help.
- **B4** Destructive actions require typed confirmation and state what is lost.
- **B5** MFA enrollment is two-step and cannot complete without a verified code;
  recovery codes are shown exactly once.
- **B6** Seat and plan limits surface as `<Paywall />`, not as errors.
- **B7** Admin routes are hidden, not merely denied, for non-superadmins.
- **B8** All settings pages are reachable from one navigation menu.

## Acceptance criteria

- **A1** An invited user with no account can follow the link, sign up, and land
  in the workspace.
- **A2** Accepting with the wrong signed-in account shows the mismatch message
  naming both addresses.
- **A3** An expired invitation shows an expiry message and a "request a new
  invitation" action.
- **A4** Demoting the last owner is blocked with an explanation.
- **A5** Adding a member beyond the seat limit shows the paywall.
- **A6** MFA enrollment cannot be completed without entering a valid code, and
  recovery codes must be acknowledged before the dialog closes.
- **A7** Revoking a session invalidates that device's refresh token.
- **A8** An invalid GSTIN checksum shows an inline error before submit.
- **A9** Deleting a workspace requires typing its name and cancels any active
  subscription.
- **A10** `/admin` is absent from navigation and returns 403 for non-superadmins.
- **A11** Export failures render human copy, never a downloaded JSON error.

## Out of scope

- Support impersonation (see §6).
- SCIM / directory sync (enterprise, Phase 3+).
- Granular per-project permissions beyond the existing role model.
- Apple/Google sign-in buttons — deferred until TS-036 makes Google available;
  shipping Apple alone would advertise the least relevant provider.

## Assumptions

- `assumption:` Workspace deletion is soft-delete with a 30-day recovery window,
  matching the "never delete data" posture in `specs/modules/billing.md` B8.
