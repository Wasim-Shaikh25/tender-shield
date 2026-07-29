# R-023 — Unexposed capabilities: finished backends with no user interface

**Status:** draft
**Severity:** P0 for the review queue (it gates the paid export path); P1 for the
rest — this is the cheapest value in the backlog, because the engines are built,
tested and routable already
**Requirement refs:** Doc §6, §7, §9
**Task refs:** TS-118…TS-125
**Task files:** code-level detail (current-vs-target snippets, file:line, files touched, tests) now lives per-task, split out by TS-126's restructure: [TS-118](../../tasks/specs/TS-118-timeline-ics-calendar.md), [TS-119](../../tasks/specs/TS-119-review-queue-ui.md), [TS-120](../../tasks/specs/TS-120-qualification-ui.md), [TS-121](../../tasks/specs/TS-121-cross-tender-comparison-ui.md), [TS-122](../../tasks/specs/TS-122-addendum-crossref-ui.md), [TS-123](../../tasks/specs/TS-123-rulepack-transparency-ui.md), [TS-124](../../tasks/specs/TS-124-search-and-assignment.md), [TS-125](../../tasks/specs/TS-125-support-ops-console.md). This document stays the business/behavior-level record (purpose, target behavior, acceptance criteria).

**Gap refs:** `docs/PRODUCT_DISCOVERY_GAPS.md` §Gate 7
**Specs to update:** `specs/frontend.md` and the per-module specs named below

## Purpose

Seven backend modules are implemented, tested, registered in the loader and
routable — and have **no user interface at all**. The engine work is already
paid for; only the surface is missing.

| Task | Capability | Endpoints | Module spec |
|---|---|---|---|
| TS-118 | Deadline calendar + `.ics` subscription | `GET /timeline/opportunities/{id}/timeline`, `…/timeline.ics` | `timeline.md` |
| TS-119 | Review queue + audit viewer | `GET /review/…/queue`, `GET /review/…/audit` | `review.md` |
| TS-120 | Bid qualification / eligibility | `GET/POST /qualification/opportunities/{id}` | `qualification.md` |
| TS-121 | Cross-tender comparison | `GET /comparison/opportunities` | `comparison.md` |
| TS-122 | Addendum cross-reference / diff | `GET/POST /crossref/opportunities/{id}` | `crossref.md` |
| TS-123 | Rule-pack transparency | `GET /rulepacks`, `GET /rulepacks/{id}/patterns` | `rulepacks.md` |
| TS-124 | Search and findability | *(none — needs building)* | — |
| TS-125 | Support/ops investigation console | `GET /auth/admin/*` partial | `auth.md` |

Two of these are load-bearing rather than merely unexposed.

## TS-119 — Review queue (P0, release-blocking)

`ExportService._gate_ok` blocks export until **every** finding is accepted or
rejected. The only way to do that today is clicking through findings inline on a
single opportunity's Risks tab — no queue, no bulk action, no filtering, no
cross-opportunity view.

For an 800-page pack producing dozens of findings, this is the difference between
a usable and an unusable workflow, and it sits **directly on the paid path**: a
customer who has paid ₹7,500 cannot export until they finish a review flow that
has no proper interface.

The `reviewer` role gates three endpoints in total: these two, plus
`baseline/freeze` (which *is* reachable, via the Handover tab). So the workflow
the role is actually named for is the one it cannot perform.

**Acceptance:** a queue listing pending findings across an opportunity with
filter-by-severity/category, keyboard-navigable accept/reject, bulk accept for a
filtered set, progress toward the export gate, and the audit trail of decisions
visible alongside.

## TS-118 — Timeline and `.ics` calendar (P1, best value-to-effort)

`GET /timeline/opportunities/{id}/timeline.ics` already emits a calendar
subscription feed. This is the highest-leverage retention feature in a deadline
product: it puts TenderShield inside the tool the customer already lives in
(Outlook/Google Calendar) rather than competing with it. It is finished and
unreachable.

**Acceptance:** a timeline view per opportunity; a "Subscribe in your calendar"
action exposing the `.ics` URL; the feed authenticates safely (a calendar client
cannot send a bearer token — this needs a signed, revocable feed token, which is
**new backend work** and the one non-trivial part of this task).

## TS-120 / TS-121 / TS-122 / TS-123 (P1/P2)

- **Qualification** — eligibility criteria (turnover, similar-project experience,
  equipment) with met/not-met/unknown and the citation for each. Directly informs
  the bid/no-bid decision (R-018) and should surface alongside it.
- **Comparison** — a cross-tender view; overlaps R-012's dashboard and should be
  built with it rather than as a separate screen.
- **Crossref** — addendum diffing. The product's own copy warns that addenda
  change the commercial position; the engine exists, the surface does not.
- **Rulepacks** — which patterns ran, at which version, at what confidence.
  Supports the product invariant that findings are labelled by provenance
  (`validated` vs `unvalidated`), and is the honest answer to "why did you flag
  this?".

## TS-124 — Search and findability (P1, needs backend)

There is no search anywhere: not across opportunities, not within a pack's
clauses, not across findings. `doc_chunks` exists — suggesting retrieval was
planned — and the `assistant` module can answer questions but is deliberately
unsurfaced (`specs/frontend.md`).

Related and possibly more urgent: **there is no concept of assigning an
opportunity to a person.** A team product normally requires it, and R-020's
alerting needs it to answer "who gets alerted?".

## TS-125 — Support/ops console (P2, Domain-Expected)

`GET /auth/admin/users` and `/admin/workspaces` exist. There is no way for
support to investigate "why did this customer's review fail", inspect a
workspace's entitlement state, or see job/run status. Depends on R-022 Part B
(run records) to have anything useful to show.

**Impersonation is deliberately not proposed here** — for a product holding
confidential commercial packs, read-only diagnostics plus an audit record is the
safer default, and impersonation would need its own consent and audit design.

## Out of scope

- Surfacing the **end-user AI assistant**. `specs/frontend.md` states it is
  *intentionally* unsurfaced; six working endpoints and two tables are currently
  dark by choice. Confirm that decision still holds — but do not reverse it here.
- The `projects` / `project_members` sub-tenant layer (four endpoints, two tables,
  full RLS coverage, zero product references). **Clarification Required:** either
  a deliberate future capability or dead weight carrying real complexity and
  attack surface.

## Questions for the product owner

1. **Review queue:** is bulk-accept acceptable, or does the review invariant
   ("export blocked until human review completes") require each finding to be
   individually considered? Bulk-accept is a usability necessity and an integrity
   risk at the same time.
2. **Calendar feed:** signed feed tokens are long-lived by nature. Acceptable, or
   should the feed be per-user and revocable from account settings?
3. **Assignment:** should opportunities be assignable to a person? This blocks
   R-020's default-recipient decision.
4. **Projects:** keep and surface, or remove?
5. **Assistant:** does it stay unsurfaced?
