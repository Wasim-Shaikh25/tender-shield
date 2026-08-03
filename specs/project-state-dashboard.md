# Project State Dashboard — Spec

**Status:** draft
**Requirement refs:** Doc §9, §1.1; `specs/modules/controltower.md`; user request
**Task refs:** TS-353, TS-354

## Purpose

Give users two new views:
1. **Marketing/landing project state dashboard** — a public or workspace-level
   page showing the current state of every tender project and the next required
   action (e.g. "Upload NIT", "Review risk findings", "Lock baseline").
2. **All-projects / workspace filter dashboard** — an authenticated page that
   lists all opportunities across the user's workspaces with filters (workspace,
   jurisdiction, status, deadline, health, value).

## Public interface

### New frontend routes

- `/projects` — authenticated list of all opportunities the user can access.
- `/projects/{opportunity_id}/state` — read-only state card + next-actions for a
  single project (can be shared as a public preview link later).
- `/dashboard/state` — workspace-level state summary cards (optional landing page).

### Backend routes

- `GET /api/opportunities` (exists) — extend with workspace filter and `state` summary.
- `GET /api/opportunities/{id}/state` — returns project state + next actions.
- `GET /api/workspaces/me/opportunities/state` — aggregate state counts per workspace.

## Data owned

No new tables. Uses existing `opportunities`, `findings`, `documents`,
`baseline`, `change_events`, `claims`, `payments`. Computes state at request
time from these rows.

## Behavior

### State machine

A project moves through these deterministic states:

1. `draft` — opportunity created, no documents uploaded.
2. `ingesting` — documents uploaded, classification/extraction in progress.
3. `ingested` — documents classified; next: run risk + BOQ.
4. `reviewing` — risk and/or BOQ findings generated; next: review all findings.
5. `reviewed` — all findings accepted/edited/rejected; next: lock baseline.
6. `baseline_locked` — baseline frozen; next: submit bid or run post-award.
7. `submitted` — bid submitted (manual status update or via outcome import).
8. `awarded` / `rejected` / `withdrawn` — final project outcomes.

- **B1 (state resolution):** `GET /api/opportunities/{id}/state` computes the
  highest state reached by checking counts and flags, not a single stored column.
- **B2 (next action):** each state returns one imperative next action with a
  deep link (e.g. `/opportunities/{id}/boq` when BOQ is unreviewed).
- **B3 (blockers):** if a required gate is incomplete (e.g. export unlocked only
  after all findings reviewed), the state remains `reviewing` and the blocker is
  listed.
- **B4 (workspace filter):** `/projects` supports `?workspace=`, `?jurisdiction=`,
  `?status=`, `?min_value=`, `?max_value=`, `?deadline_after=`, `?deadline_before=`,
  `?health=healthy|at_risk|poor`.
- **B5 (global all-projects view):** users with multiple workspaces see all
  opportunities they have access to; switching workspace is a filter, not a
  hard redirect.
- **B6 (state summary):** the `/dashboard/state` endpoint returns counts per
  state and a list of projects with upcoming deadlines (≤7 days).
- **B7 (public preview):** `/projects/{id}/state` can be made public via a
  `share_token` (out of scope for v1; prepare route structure now).
- **B8 (manual overrides):** state can be manually advanced by an editor only
  after the automated gate is satisfied; admins can add an audit-logged note
  explaining any override.
- **B9 (marketing labels):** each state has a human-readable label and a short
  description suitable for a marketing page ("7 of 8 projects are ready to bid").
- **B10 (bulk actions):** `/projects` supports selecting multiple opportunities
  and running one bulk action (re-run analysis, export summary) via `POST
  /api/opportunities/bulk-action`.

## Acceptance criteria

- A1: `/projects` renders a list of all opportunities for the user with filters.
- A2: each project card shows state, next action, deadline, value, and workspace.
- A3: clicking a project card navigates to the existing opportunity page.
- A4: `/projects/{id}/state` returns correct state and next action without
  requiring a full opportunity page load.
- A5: state counts in `/dashboard/state` match the opportunity list after filters.
- A6: filters by workspace, jurisdiction, status, deadline range, and value range
  work in combination.
- A7: a project with unreviewed findings cannot be marked `reviewed`.
- A8: the all-projects view is responsive from 360px to 1280px.
- A9: bulk re-run analysis updates state for selected opportunities.
- A10: the state API returns `state`, `next_action`, `blockers`, and
  `completed_gates` for any opportunity the user can view.

## Out of scope

- Public share tokens for `/projects/{id}/state` (placeholder route only).
- Custom state workflows per workspace.
- Analytics charts on the state dashboard (use existing `/analytics` page).
- Push notifications for state changes.

## Assumptions

- The `opportunities` table already has `status`, `jurisdiction`, `value`, and
  `deadline` fields.
- Workspace membership is checked via existing RBAC; the all-projects view reuses
  `GET /api/auth/workspaces` + `GET /api/opportunities` per workspace.
- State is computed on demand and may be cached in Redis later if slow.
