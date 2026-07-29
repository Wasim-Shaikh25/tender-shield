# TS-040 — In-app Help page: how-to-use walkthrough + honest scope disclaimer

**Status:** done
**Requirement:** Doc §0.1–0.2, §11.4
**Spec(s) updated:** none
**Module(s):** frontend
**Severity / Gate:** P2 · Phase 1 MVP

## What this builds

A `/help` page that walks a new user through the product step-by-step and
states plainly what TenderShield does and does not do (it is a bid-decision
aid with human review, not an automated bid submission or legal-advice
tool) — an honest-scope disclaimer rather than implied full QS coverage.

## Implementation

```tsx
// frontend/app/help/page.tsx
export const metadata: Metadata = {
  title: "Help · TenderShield AI",
  description: "How to use TenderShield, what it checks, and what it deliberately does not do.",
};

const STEPS = [
  { n: 1, title: "Create your workspace", body: "..." },
  { n: 2, title: "Open an opportunity", body: "..." },
  // ...
];
```

## Files touched

- `frontend/app/help/page.tsx`

## Tests

None — static content page.

## Acceptance criteria

- [x] The page explains the upload → review → export flow end-to-end.
- [x] The page states the product's scope limits honestly (human review
      required; not a full QS replacement).

## Commit

Predates commit-granular history (PR #10 bulk import).
