# TS-116 — Member removal (with immediate session revocation) + invitation list/revoke/resend

**Status:** todo
**Requirement:** [R-022 §A](../../specs/requirements/R-022-team-lifecycle-and-run-recovery.md)
**Spec(s) updated:** `specs/modules/auth.md` (to be updated when built)
**Module(s):** `auth`, frontend
**Severity / Gate:** P0 · Gate 6

## What this builds

Onboarding exists; offboarding doesn't. There is no `DELETE` route for
removing a workspace member anywhere in the app, and no list/revoke/resend
for invitations. Two concrete harms: an employee who leaves keeps access to
every tender in the workspace forever (unshippable for a product holding
confidential commercial data), and a typo'd invitation silently holds a
billed seat (TS-098 counts pending invitations toward the seat limit) for
a full week with no way to cancel it.

## Implementation (reference plan — not yet built)

`DELETE /workspaces/{workspace_id}/members/{user_id}` (admin+). The
existing last-owner guard (TS-084's `AuthError("last_owner")`) applies
unchanged. Critically, **removal must revoke access immediately, not
eventually**: a removed member's existing access token still carries the
workspace claim until it expires (up to 15 minutes), and their refresh
family would keep re-minting it — so removal must revoke the refresh
families binding that user to that workspace (TS-093's
`_revoke_all_sessions` pattern, scoped to one workspace instead of all).
Otherwise "removed" silently means "removed in a quarter of an hour,"
which is not what an admin removing a departing employee understands it to
mean.

Invitation list/revoke/resend: a revoked invitation cannot be redeemed and
releases its seat immediately. Both member removal and invitation
revocation write an audit row (TS-114).

## Files touched (planned)

- `backend/app/modules/auth/{router,service}.py`
- `frontend/app/settings/team/page.tsx` (TS-103's planned page)

## Tests (planned)

- `backend/tests/modules/auth/test_service.py::test_removed_member_token_stops_working_immediately`,
  `test_last_owner_cannot_be_removed`, `test_revoked_invitation_rejected`

## Acceptance criteria (R-022 §A, A1–A6)

- [ ] A removed member's in-flight access token stops working immediately,
      not at natural expiry.
- [ ] The last owner cannot be removed (`400 last_owner`).
- [ ] A revoked invitation returns `invalid_invitation` on redemption and
      the seat count drops immediately.
- [ ] A `viewer`/`reviewer` cannot remove members (`403`).
- [ ] Removing a member from workspace A does not affect their membership
      of workspace B.

## Commit

Not yet implemented.
