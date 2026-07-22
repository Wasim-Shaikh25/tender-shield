# Review Workbench & Audit — Spec

**Status:** draft
**Requirement refs:** Doc §1.1(7), §11.4
**Task refs:** TS-021

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
(`review_status`, `reviewed_by`, `review_note`); `outcomes`.

## Behavior

- **B1:** finding review states: `proposed → accepted | edited | rejected`;
  reviewer identity + note logged; rejection reasons structured (wrong clause /
  wrong severity / not a risk here / duplicate — feeds pattern telemetry §11.5).
- **B2:** export gate passes only when review is complete; requires a
  `reviewer`-role human (RBAC via `auth.require`).
- **B3:** single-member orgs get a mandatory full-screen attestation listing
  every unconfirmed extraction before export unlocks.
- **B4:** tri-state labeling (extracted fact / deterministic check / AI
  suggestion) is part of the finding contract, surfaced to the UI as distinct
  badge types — not copy.
- **B5:** `audit_log` has no UPDATE/DELETE grants; every acceptance/export/
  outcome writes a row.
- **B6:** outcome capture (won/lost/declined + reasons; risks materialized).

## Acceptance criteria

- A1: gate blocks export while any finding is `proposed`.
- A2: audit rows are written for accept/reject/export and cannot be updated.

## Out of scope

Multi-reviewer approval chain (P2).
