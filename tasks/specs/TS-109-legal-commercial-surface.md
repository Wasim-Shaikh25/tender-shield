# TS-109 — Legal/commercial surface: ToS, privacy policy, refund policy, DPA, DPDP request paths

**Status:** todo
**Requirement:** [R-016](../../specs/requirements/R-016-platform-scale.md) + Doc §16
**Spec(s) updated:** none (to be updated when built)
**Module(s):** docs, frontend
**Severity / Gate:** P2 · Gate 4

## What this builds

The legal surface a paying customer expects to exist and can currently find
nowhere in the app: Terms of Service, Privacy Policy, Refund Policy, a Data
Processing Agreement, and a functioning DPDP (India's data-protection law)
data-subject-request path — referenced elsewhere in this audit (e.g.
TS-099/TS-103) as a real gap, not a hypothetical one (`docs/GAP_ANALYSIS.md`
§1.10 notes there is no code path for account/data erasure today).

## Implementation (reference plan — not yet built)

- Published, versioned legal documents (ToS, Privacy Policy, Refund
  Policy, DPA) linked from signup, footer, and account settings — not just
  existing as an internal doc nobody links to.
- A DPDP erasure/access request path: an authenticated user can request
  their data or request deletion; sole-owner workspaces must be
  transferred or deleted first (ties to TS-103's `/settings/profile`
  account-deletion flow).
- Refund policy content must match the actual refund behavior TS-097
  implements (webhook-driven credit notes), not describe a manual process
  that doesn't exist.

## Files touched (planned)

- `frontend/app/legal/{terms,privacy,refunds,dpa}/page.tsx`
- `backend/app/modules/auth/` (DPDP request endpoint, ties to account
  deletion)

## Tests (planned)

- `backend/tests/modules/auth/test_service.py::test_data_erasure_request`

## Acceptance criteria

- [ ] ToS/Privacy/Refund/DPA are published and linked from signup, footer,
      and account settings.
- [ ] A DPDP data-erasure request has a real, working code path (not just
      a documented policy with nothing behind it).

## Commit

Not yet implemented.
