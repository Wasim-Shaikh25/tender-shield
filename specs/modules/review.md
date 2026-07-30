# Review Workbench & Audit — Spec

**Status:** implemented — accept/edit/reject/false_positive/needs_clarification per
finding with optional review reason, append-only audit log, export gate (blocks
until no finding is `proposed` or `needs_clarification`). Consumes the findings
store via capability; updates the review columns the findings module owns. Single-
member attestation (Doc §11.4) and multi-reviewer chains are follow-ups.
**Requirement refs:** Doc §1.1(7), §11.4, Phase 1.5 doc §5
**Task refs:** TS-021, TS-055, TS-116

## Purpose

The professional-liability core: humans accept/edit/reject every finding before
anything is exported; every decision is audited append-only.

## Public interface

- **Capabilities published:** `review.gate(opportunity_id) -> GateResult`
  (is export allowed + why not), `review.audit(action, ...)` (audit writer for
  all modules).
- **Events emitted:** `finding.reviewed`, `review.completed`.
- **Events consumed:** `finding.created` (adds to review queue).
- **API routes:** `/api/opportunities/{id}/review` (queue, accept/edit/reject
  with note), review-completion endpoint.

## Data owned

`audit_log` (append-only); review fields on `findings`
(`review_status`, `reviewed_by`, `review_note`, `review_reason`); `outcomes`.

## Behavior

- **B1:** finding review states:
  `proposed → accepted | edited | rejected | false_positive | needs_clarification`;
  reviewer identity + note + `review_reason` logged; rejection reasons structured
  (`wrong_clause` / `wrong_severity` / `not_a_risk_here` / `duplicate` /
  `needs_more_info` — feeds pattern telemetry §11.5 and the accuracy dashboard).
- **B2:** export gate passes only when review is complete; `needs_clarification`
  is treated as unresolved and blocks export, just like `proposed`. Requires a
  `reviewer`-role human (RBAC via `auth.require`).
- **B3:** single-member orgs get a mandatory full-screen attestation listing
  every unconfirmed extraction before export unlocks.
- **B4:** tri-state labeling (extracted fact / deterministic check / AI
  suggestion) is part of the finding contract, surfaced to the UI as distinct
  badge types — not copy.
- **B5:** `audit_log` has no UPDATE/DELETE grants; every acceptance/export/
  outcome writes a row.
- **B6:** outcome capture (won/lost/declined + reasons; risks materialized).
- **B7:** `review_finding` requires the `opportunity_id` of the opportunity under
  review and rejects the request when the finding does not belong to that
  opportunity.
- **B8:** `app.core.audit` provides a thin router helper that resolves the
  `review.service_factory` capability and writes append-only `audit_log` rows for
  auth, membership, role, billing, and export events without creating cross-module
  imports. Failures are logged and swallowed.
- **B9:** auth and workspace lifecycle events are recorded: workspace creation,
  member add/role change/remove, invitation create/accept/revoke, project creation,
  project member add, account settings/password changes (when a real workspace is
  selected), billing checkout/payment webhooks, and export pack/handover downloads.

## Acceptance criteria

- A1: gate blocks export while any finding is `proposed` or `needs_clarification`.
- A2: audit rows are written for accept/reject/export and cannot be updated.
- A3: `false_positive` and `needs_clarification` decisions are accepted by the
  review endpoint and persisted with `review_reason`.
- A4: the queue response includes `review_reason` and `explanation` for each finding.
- A5: reviewing a finding with a mismatched `opportunity_id` returns 404.
- A6: workspace lifecycle and billing/export actions produce `audit_log` rows
  with the correct `workspace_id`, `actor_user_id`, and `action`.

## Out of scope

Multi-reviewer approval chain (P2).
