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
    overview | risks | boq | artifacts | handover | export
  standards/                # org-custom notice standards editor (prevail / side-by-side)
  help/                     # static how-to + honest QS-lifecycle scope + disclaimer
  billing/                  # plan selection, invoices, usage
  settings/                 # account profile + security (password, sessions)
  team/                     # workspace members, role changes, invitations, revoke
  admin/                    # super-admin: users, workspaces, audit-log
  playbook/
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
- **B7:** access token in memory only; refresh token in `httpOnly` cookie;
  `credentials: "include"` on API calls; silent refresh on 401. The auth response
  types are generated from the backend OpenAPI spec (`lib/api-types.ts` via
  `npm run generate:api`); non-auth endpoints keep hand-rolled types until their
  response models are added.
- **B8:** workspace switcher in the nav lists the user's workspaces and calls
  `/api/auth/workspaces/{id}/switch`. The `/api/auth/workspaces` response includes
  `workspace_id`, `name`, `role`, `country`, and `plan`.
- **B9:** demo/sample data is removed from the main opportunity workbench;
  sample loading is gated behind `NEXT_PUBLIC_DEMO_MODE`.

- **B10:** the **Standards** page (`/standards`) lets an admin publish the
  firm's own notice regimes (key/label/typical-days/keywords/expected) with a
  prevail vs side-by-side mode. Saved regimes flow into every opportunity's
  notice register; org-origin gaps are badged "your standard" in the Handover
  tab.
- **B9:** the opportunity **Handover** tab (Phase 2) drives baseline lock:
  freeze tender/award baselines (gated on a completed review), lists the sealed
  baselines with their content hashes, shows the deterministic notice-rule
  register with page citations, the award-vs-tender delta when two baselines
  exist, and the commercial handover pack (sealed hash + key obligations).
- **B9:** the `/settings` page is a client route for account profile
  (org/firm, city, DOB, phone) and security (change password, sign out). Phone
  changes trigger a re-verification flow; password changes require the current
  password and enforce the same policy as sign-up.
- **B10:** the `/team` page lists workspace members and pending invitations,
  lets `admin`+ roles invite new members, change member roles, remove members,
  and revoke pending invitations. The invite form shows a dev/test token fallback
  when email is not configured.
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
- A3: access token is not stored in `localStorage`; `fetch` uses `credentials: "include"`.
- A4: workspace switcher lists workspaces and switches tokens.
- A5: `/opportunities/[id]` does not show sample-load buttons unless demo mode is on.
- A6: `/billing` renders plan status and `/admin` lists workspaces for a super-admin.
- A7: unverified hosting-region claims are removed from the landing page.
- A8: `/settings` loads the profile from `/api/auth/settings`, saves updates, and
  allows changing the password via `/api/auth/settings/password`.
- A9: `/team` lists members and pending invitations, lets admin+ users invite,
  change role, remove members, and revoke invitations through the typed API client.
- A10: `npm run generate:api` regenerates `lib/api-types.ts` from the running
  backend OpenAPI spec; `lib/api.ts` uses the generated types for all `/auth`
  responses (tokens, workspaces, members, invitations, settings).

## Out of scope

WhatsApp alert UI (P2), white-label theming (P2), mobile capture (P3).
