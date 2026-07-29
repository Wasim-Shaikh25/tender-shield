# TS-111 — Opportunity lifecycle + bid/no-bid decision record

**Status:** todo
**Requirement:** [R-018](../../specs/requirements/R-018-opportunity-lifecycle.md)
**Spec(s) updated:** `specs/modules/ingestion.md` (to be updated when built)
**Module(s):** `ingestion`, frontend
**Severity / Gate:** P0 · Gate 5

## What this builds

`Opportunity.status` exists as a column but is a dead field — nothing
validates transitions, and there is no record of the actual bid/no-bid
decision the whole product exists to inform (TS-048's Bid Readiness Score
produces a recommendation that nothing then captures a decision against).

## Implementation (reference plan — not yet built)

```
reviewing → bid | no_bid → submitted → won | lost
         ↘ withdrawn
```

Transitions validated **server-side** against an explicit map — an invalid
jump is rejected (`invalid_transition`, 400, naming current and attempted
state), not silently written. Terminal states (`won`, `lost`, `withdrawn`,
`no_bid`) drop the record out of "live" views without deleting it.
`assumption:` this state list is inferred from the domain, not a product
brief — flagged as a product decision still needing owner sign-off.

```python
# decision record — kept ON the opportunity, not a separate table: exactly
# one current decision per opportunity; transition HISTORY lives in the
# audit trail (TS-114), not duplicated here
decided_by: Mapped[uuid.UUID | None]
decided_at: Mapped[datetime | None]
decision_rationale: Mapped[str | None]
```

`PATCH /api/ingestion/opportunities/{id}` (estimator+) accepts `status` +
decision fields. Every transition is audited (actor, from-state, to-state,
rationale) — a commercial decision worth potentially millions of exposure
needs an evidence record.

## Files touched (planned)

- `backend/app/modules/ingestion/{models,service,router}.py`
- `frontend/app/opportunities/[id]/page.tsx` (status/decision UI)

## Tests (planned)

- `backend/tests/modules/ingestion/test_lifecycle.py::test_invalid_transition_rejected`

## Acceptance criteria (R-018, A1–A6)

- [ ] An invalid status transition is rejected with `invalid_transition`,
      naming both states, not silently written.
- [ ] A decision (bid/no_bid) records actor and timestamp; rationale is
      optional.
- [ ] Every transition writes an audit-trail entry.

## Commit

Not yet implemented.
