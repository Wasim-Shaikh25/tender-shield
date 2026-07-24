# Frontend — Spec

**Status:** skeleton implemented — Next.js 15 app (landing, auth, opportunity
board/countdown wall, opportunity detail with document checklist + risk
workbench, static Help page), typed API client, session context. Builds clean;
verified full-stack against the API. shadcn, PDF.js source view, and the deadline
wall (needs TS-015) are follow-ups. Plain Tailwind for now (no component kit) so
it builds without extra tooling. The end-user AI assistant is intentionally not
surfaced in the UI; internal codes are rendered through human labels
(`lib/labels.ts`), and the type is set with a system font stack led by Inter.
**Requirement refs:** Doc §9, §0.1–0.2, §11.4
**Task refs:** TS-025, TS-040

## Purpose

Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui — marketing + app in
one repo (`apps/web` later; starts as `frontend/`).

## Structure (Doc §9)

```
(marketing)/  landing, pricing, /free-tender-check
(auth)/       login, signup, otp, forgot
(app)/
  opportunities/            # countdown board
  opportunities/[id]/
    overview | risks | boq | artifacts | export
  help/                     # static how-to + honest QS-lifecycle scope + disclaimer
  billing/ team/ playbook/
```

## Behavior (UX principles — binding)

- **B1:** opportunity board is a countdown wall — red <3 days, amber <7.
- **B2:** finding cards quote the clause inline; one tap opens the source PDF
  page with the span highlighted (PDF.js) — trust by inspection.
- **B3:** risk cards lead with money exposure where computable.
- **B4:** BOQ defects sort by rupee impact.
- **B5:** tri-state badges (extracted fact / deterministic check / AI suggestion)
  are design-system components, not copy.
- **B6:** empty states teach ("Upload the GCC too — 60% of traps live in
  conditions").
- **B7:** access token in memory only; silent refresh on 401; API client
  generated from OpenAPI.

- **B8:** the Help page (`/help`) is a static server component: an 8-step
  how-to-use walkthrough, the never-broken safety rules, a three-bucket
  QS-lifecycle coverage table (**Covered now** = Phase-1 pre-bid slice;
  **On the roadmap** = baseline lock / change-notice / time-bar engine /
  outcome graph per Doc §0.1, §1.2; **Not ours** = takeoff / BIM / pricing /
  CPM / legal opinions per §0.2), a "where it goes beyond typical QS tools"
  differentiator list, and a not-legal/QS-advice disclaimer (Doc §11.4). The
  table must not flatten roadmap items into "not covered." Reachable from the
  header nav.

## Acceptance criteria

- A1: app skeleton renders board + opportunity tabs against the mock API.
- A2: `/help` renders statically and states plainly that TenderShield covers the
  pre-bid slice, not the full QS lifecycle.

## Out of scope

WhatsApp alert UI (P2), white-label theming (P2), mobile capture (P3).
