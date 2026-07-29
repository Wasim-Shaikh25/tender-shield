# TS-025 — Frontend skeleton: Next.js 15 app router, opportunity board + deadline wall

**Status:** done
**Requirement:** Doc §9
**Spec(s) updated:** none
**Module(s):** frontend
**Severity / Gate:** P0 · Phase 1 MVP

## What this builds

The first frontend surface: Next.js 15 app-router project structure, login,
and the two core screens the backend's ingestion/deadline work (TS-014/015)
needed a UI for — the opportunity board and the deadline wall.

## Implementation

```
frontend/app/
├── login/
├── forgot-password/ reset-password/
├── opportunities/
│   └── [id]/          # opportunity detail: documents, deadline wall
├── workspaces/ new/
```

Next.js 15 app router + TypeScript + Tailwind per Build Doc §9. API calls hit
the backend's `/api/<module>` routes directly (no separate BFF layer).

## Files touched

- `frontend/app/{login,opportunities,workspaces}/**`
- `frontend/package.json`, `tailwind.config.*`

## Tests

None yet at this task — frontend testing arrives with TS-032 (CI build gate).

## Acceptance criteria

- [x] A user can log in and see their opportunity board.
- [x] Opening an opportunity shows its extracted deadlines.

## Commit

Predates commit-granular history (PR #10 bulk import).
