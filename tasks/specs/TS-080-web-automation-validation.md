# TS-080 — Real web automation validation of signup → workspace → project → invite flow

**Status:** done
**Requirement:** Doc §11.1
**Spec(s) updated:** none
**Module(s):** —
**Severity / Gate:** P2 · Phase 1 (remaining)

## What this builds

Browser-driven (not just API-level pytest) validation that the whole
TS-075..078 tenant refactor works end-to-end through the actual frontend UI
— signup, default workspace creation, project creation, member invite.

## Implementation

Playwright-driven walkthrough exercising the real frontend against a real
backend instance, following the exact user journey TS-074's spec describes
(bare user + default workspace on signup, then create additional
workspace/project, then invite a collaborator).

## Files touched

- Test/validation script (not a permanent CI fixture — a one-time
  verification pass per this task's scope)

## Tests

The automation run itself is the test; no new permanent test file was
added to the CI suite by this task (frontend component/e2e tests are a
separate, later concern).

## Acceptance criteria

- [x] Signup → default workspace → create project → invite member all
      work through the real UI, not just the API.

## Commit

Predates commit-granular history (PR #10 bulk import).
