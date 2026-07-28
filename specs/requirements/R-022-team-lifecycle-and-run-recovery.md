# R-022 — Team offboarding and processing-failure recovery

**Status:** draft
**Severity:** P0 for member removal — a departed employee keeps access to every
tender in the workspace, permanently
**Requirement refs:** Doc §5, §16; R-009 §B.3 (seats)
**Task refs:** TS-116 (team lifecycle), TS-117 (run recovery)
**Gap refs:** `docs/PRODUCT_DISCOVERY_GAPS.md` §G-07, §G-08
**Specs to update:** `specs/modules/auth.md`, `specs/modules/risk.md`,
`specs/frontend.md`

## Part A — Member removal and invitation lifecycle (TS-116)

### Purpose

Onboarding exists; offboarding does not.

| Capability | Exists | Missing |
|---|---|---|
| Add member | `POST /workspaces/{id}/members` | — |
| List members | `GET /workspaces/{id}/members` | — |
| **Remove member** | — | **no DELETE route anywhere** |
| Create invitation | `POST /invitations` | — |
| **List invitations** | — | **none** |
| **Revoke invitation** | — | **none** |
| **Resend invitation** | — | **none** |

Two concrete harms:

1. **An employee who leaves keeps access** to every tender in the workspace,
   forever. For a product holding confidential commercial packs — and for the P3
   consultancy persona holding *several clients'* packs — this is not a shippable
   state.
2. **Pending invitations consume paid seats** (R-009 §B.3 counts live invitations
   toward the seat limit) and expire after 7 days. An invitation sent to a typo'd
   address silently holds a billed seat for a week with no way to cancel it.

### Target

- **A.1** `DELETE /workspaces/{workspace_id}/members/{user_id}` — `admin`+.
  The existing last-owner guard (`AuthError("last_owner")`) already prevents
  orphaning a workspace and applies here unchanged.
- **A.2 Removal revokes access immediately, not eventually.** A removed member's
  existing access token still carries the workspace claim until it expires (up to
  15 minutes), and their refresh family would keep re-minting it. Removal must
  revoke the refresh families that bind that user to that workspace — otherwise
  "removed" means "removed in a quarter of an hour", which is not what an admin
  removing a departing employee understands it to mean.
- **A.3** Invitation list / revoke / resend; a revoked invitation cannot be
  redeemed and releases its seat immediately.
- **A.4** Both actions audited (R-021).

### Acceptance criteria

- **A1** A removed member's in-flight access token stops working immediately —
  not at natural expiry.
- **A2** The last owner cannot be removed (`400 last_owner`).
- **A3** A revoked invitation returns `invalid_invitation` on redemption and the
  seat count drops immediately.
- **A4** Removal and revocation each write an audit row.
- **A5** A `viewer` or `reviewer` cannot remove members (`403`).
- **A6** Removing a member from workspace A does not affect their membership of
  workspace B (verified with a multi-workspace user, given R-011 switching).

### Out of scope

Bulk member import/removal; SCIM provisioning; transferring a departing member's
records to another user (see Questions).

---

## Part B — Processing-failure visibility and recovery (TS-117)

### Purpose

Review runs are synchronous with **no persisted run record**. A failed OCR pass or
LLM call surfaces as an HTTP error and vanishes: no status, no failure record, no
retry, no support-visible cause.

This collides with metering. `authorize_review` meters at processing **start**
(a `review_started` usage event) precisely so a re-run after an addendum is free.
But that also means **a run that fails for our reasons has already consumed the
customer's free or paid review** — with no record that it failed and no
automatic correction. On the paygo plan that is ₹7,500 for nothing.

It also collides with the NFR: 25-minute p95 for an 800-page pack cannot be
served synchronously, so the async model (R-016/TS-105) is implied by the NFR
itself — and async work with no visible state is unusable.

### Target

- **B.1** Persisted run records: state (`queued|running|succeeded|failed`),
  started/finished timestamps, error class and message, and the triggering user.
- **B.2** Progress and failure state visible in the UI, with a retry action.
- **B.3 Metering correction.** A run that fails for an internal reason must not
  consume the entitlement — either by not metering until success, or by writing a
  compensating refund event. **Product decision — see Questions.**
- **B.4** Support can see the failure cause without database access (ties to the
  ops console, R-023 §G-16).

### Acceptance criteria

- **B1** A failed run is visible in the UI with a human-readable cause.
- **B2** Retrying does not double-meter or double-charge.
- **B3** A run failing for an internal reason leaves the entitlement unconsumed
  (or visibly refunded).
- **B4** A run that fails because of a genuine user-input problem (corrupt file)
  is distinguishable from an internal failure.
- **B5** Run records are workspace-scoped and RLS-protected.

### Out of scope

Partial-result recovery (resuming a failed run mid-pipeline); per-stage progress
granularity beyond a coarse state machine.

---

## Questions for the product owner

1. **On member removal, what happens to records that member created** — retained
   with attribution (recommended: an audit-oriented product should not rewrite
   history) or reassigned to an admin?
2. **Does a failed review automatically refund the metered entitlement**, or does
   it require support intervention? Automatic is better for trust; it needs a
   clear internal-vs-user-error boundary to avoid being gamed.
3. How many automatic retries before a run escalates to support?

## Assumptions

- `assumption:` records created by a removed member are retained with attribution
  to the (now non-member) user id, and the UI renders them as a former member
  rather than as an unknown id.
- `assumption:` Part B is sequenced after R-016/TS-105 (job scheduler); building
  run records for a synchronous pipeline would mean building them twice.
