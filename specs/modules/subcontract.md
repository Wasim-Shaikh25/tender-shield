# Subcontract Control — Spec

**Status:** draft
**Requirement refs:** Research Doc §13 Subcontract control
**Task refs:** TS-288, TS-289

## Purpose

Track subcontracts under a main opportunity, compare flow-down clauses to the
main contract, flag scope gaps, and compute back-to-back notice calendars and
pay-when-paid exposure across the subcontract chain.

## Public interface

- **Capability published:** `subcontract.service_factory`.
- **Capabilities consumed (soft):**
  - `change.service_factory` — read main-contract change events and notice deadlines.
  - `controltower.exposure_for_opportunity` — exposure totals for pay-when-paid.
- **Events:** `subcontract.notice_due`, `subcontract.payment_due`.

### API routes (prefix `/api/subcontract`)

- `POST /opportunities/{opportunity_id}/subcontracts` — create a subcontract.
- `GET /opportunities/{opportunity_id}/subcontracts` — list subcontracts.
- `GET /subcontracts/{subcontract_id}` — detail.
- `POST /subcontracts/{subcontract_id}/clauses` — add a flow-down clause.
- `GET /subcontracts/{subcontract_id}/flowdown-check` — compare against main contract.
- `GET /subcontracts/{subcontract_id}/scope-gaps` — missing scope items.
- `GET /subcontracts/{subcontract_id}/notice-calendar` — back-to-back notice dates.
- `POST /subcontracts/{subcontract_id}/payment-events` — record a payment event.
- `GET /subcontracts/{subcontract_id}/payment-exposure` — pay-when-paid ageing.

## Data owned

- `subcontracts` — workspace-scoped subcontract header.
- `subcontract_clauses` — clauses expected to flow down from main contract.
- `subcontract_scope_items` — scope line items.
- `subcontract_payment_events` — RA/progress/retention events for the subcontract.

All tables are workspace-scoped with RLS.

## Behavior

### Flow-down check (TS-288)

- Each `subcontract_clauses` row has `title` and `source_quote`.
- `GET /flowdown-check` returns:
  - `matched` — clauses whose title/quote appears in the main contract baseline.
  - `missing` — clauses not found in the main contract.
  - `missing_in_subcontract` — main contract clauses not present in the subcontract.
- Matching is deterministic: case-insensitive substring match on `title`.

### Scope-gap check (TS-288)

- `scope_items` may be provided explicitly or inferred from the subcontract `scope` text.
- A gap is a scope item whose text does not appear in the main contract scope or
  in a linked change event.

### Back-to-back notice calendar (TS-289)

- For each main-contract `change_events` row with a computed notice deadline,
  the subcontract notice deadline is the main deadline minus `notice_buffer_days`
  (default 7) and `postal_buffer_days` (default 2).
- Returns a list of `{change_event_id, main_deadline, subcontract_deadline, status}`.

### Pay-when-paid exposure (TS-289)

- `payment_events` store `kind`, `amount_minor`, `certified_amount_minor`, `due_date`, `status`.
- `GET /payment-exposure` returns `total_certified_minor`, `total_paid_minor`,
  `pending_minor`, `age_days_max`, and `pay_when_paid_exposed_minor`
  (pending amounts whose parent payment is not yet received).

## Acceptance criteria

- A1 (TS-288): `POST /subcontracts` and `/clauses` persist workspace-scoped rows.
- A2 (TS-288): `GET /flowdown-check` reports matched/missing/missing-in-subcontract.
- A3 (TS-288): `GET /scope-gaps` flags scope not covered by main contract.
- A4 (TS-289): `GET /notice-calendar` returns deterministic back-to-back deadlines.
- A5 (TS-289): `GET /payment-exposure` computes pending/ageing without invented numbers.
- A6: Migration and RLS are present.

## Out of scope

- Live integration with subcontractor ERP systems.
- Automated notice issue (manual gate).
