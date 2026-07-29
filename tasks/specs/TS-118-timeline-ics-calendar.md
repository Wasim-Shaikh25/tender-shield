# TS-118 — Timeline view + `.ics` calendar subscription

**Status:** todo
**Requirement:** [R-023](../../specs/requirements/R-023-unexposed-capabilities.md)
**Spec(s) updated:** `specs/modules/timeline.md` (to be updated when built)
**Module(s):** frontend, `timeline`
**Severity / Gate:** P1 (best value-to-effort) · Gate 7

## What this builds

`GET /timeline/opportunities/{id}/timeline.ics` (TS-052) already emits a
working calendar-subscription feed — it's finished and unreachable. This
is the highest-leverage retention feature available in the whole backlog:
it puts TenderShield inside the tool the customer already lives in
(Outlook/Google Calendar) rather than competing with it.

## Implementation (reference plan — not yet built)

A timeline view per opportunity (frontend surface for TS-052's existing
milestone calendar), plus a "Subscribe in your calendar" action exposing
the `.ics` URL. The one non-trivial new backend piece: a calendar client
cannot send a bearer token, so the feed needs a signed, revocable feed
token rather than the normal JWT auth path — a per-opportunity (or
per-user) token embedded in the URL, checked against a stored hash, and
revocable from the UI if the URL leaks.

## Files touched (planned)

- `backend/app/modules/timeline/{router,service}.py` (signed feed token)
- `frontend/app/opportunities/[id]/timeline/page.tsx` (new)

## Tests (planned)

- `backend/tests/modules/timeline/test_ics_feed_token.py::test_revoked_token_rejected`

## Acceptance criteria (R-023, TS-118 §Acceptance)

- [ ] A timeline view renders per opportunity.
- [ ] The `.ics` feed authenticates via a signed, revocable token, never a
      bearer JWT embedded in a URL.
- [ ] Revoking the feed token invalidates the previously-issued calendar
      subscription URL.

## Commit

Not yet implemented.
