# TS-124 — Search across opportunities, clauses and findings; opportunity assignment

**Status:** todo
**Requirement:** [R-023](../../specs/requirements/R-023-unexposed-capabilities.md)
**Spec(s) updated:** `specs/modules/ingestion.md`, `specs/modules/findings.md`
  (to be updated when built)
**Module(s):** frontend, `ingestion`, `findings`
**Severity / Gate:** P1 (needs backend) · Gate 7

## What this builds

There is no search anywhere in the product today: not across
opportunities, not within a pack's clauses, not across findings.
`doc_chunks` (TS-068) exists specifically to enable retrieval, and the
`assistant` module (TS-024/069) can already answer questions but is
deliberately unsurfaced for this purpose. Related and possibly more
urgent: there is no concept of assigning an opportunity to a person — a
team product normally requires this, and TS-113's deadline alerting needs
it to answer "who gets alerted?"

## Implementation (reference plan — not yet built)

Backend search over `doc_chunks` text (TS-068) and the `findings`/
`clauses` tables — likely full-text search (Postgres `tsvector` or
similar) rather than reusing the LLM-backed `assistant` for a simple
keyword lookup, keeping search fast and deterministic. Opportunity
assignment: an `assigned_to` field on `Opportunity` (or a small
`OpportunityAssignment` table if multiple assignees are needed), surfaced
in the opportunity list/board and consumed by TS-113's alerting to decide
recipients.

## Files touched (planned)

- `backend/app/modules/ingestion/{models,service,router}.py` (search
  endpoint, `assigned_to`)
- `frontend/components/search-bar.tsx` (new)
- Depends on / feeds TS-113 (alerting needs assignment to pick recipients)

## Tests (planned)

- `backend/tests/modules/ingestion/test_search.py`

## Acceptance criteria (R-023)

- [ ] A keyword search returns matching opportunities, clauses, and
      findings without invoking the LLM-backed assistant.
- [ ] An opportunity can be assigned to a workspace member, and TS-113's
      alerting can read that assignment.

## Commit

Not yet implemented.
