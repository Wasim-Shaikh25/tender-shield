# Frontend — Spec

**Status:** draft
**Requirement refs:** Doc §9
**Task refs:** TS-025

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
  assistant/ billing/ team/ playbook/
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

## Acceptance criteria

- A1: app skeleton renders board + opportunity tabs against the mock API.

## Out of scope

WhatsApp alert UI (P2), white-label theming (P2), mobile capture (P3).
