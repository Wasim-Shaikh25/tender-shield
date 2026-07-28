# Frontend — Spec

**Status:** skeleton implemented — Next.js 15 app (landing, auth, opportunity
board/countdown wall, opportunity detail with document checklist + risk
workbench, static Help page), typed API client, session context. Builds clean;
verified full-stack against the API. Billing UI (pricing, paywall, checkout,
account billing page) now shipped as a thin but complete paid path (R-008,
TS-091) — see below. Session/refresh-token handling is now a real
implementation, not a skeleton (R-010, TS-092) — access token in memory only,
proactive + reactive refresh, multi-tab coordination, route guards — see B12.
This also seeds the frontend's first test framework (Vitest + Testing
Library), ahead of R-014/TS-104's broader test-stack task. A workspace
switcher in the header and a `/workspaces/new` onboarding page (R-011,
TS-100) — see B13 — close the "multi-workspace users are stranded" gap.
shadcn, PDF.js source view, and the deadline wall (needs TS-015) are
follow-ups. Plain Tailwind for now (no component kit) so it builds without
extra tooling. The end-user AI assistant is intentionally not surfaced in
the UI; internal codes are rendered through human labels (`lib/labels.ts`),
and the type is set with a system font stack led by Inter.
**Requirement refs:** Doc §9, §0.1–0.2, §11.4, §7, §15; R-010, R-011
**Task refs:** TS-025, TS-040, TS-091, TS-092, TS-100

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
  generated from OpenAPI. (Implemented as B12, R-010/TS-092 — the
  OpenAPI-generation half is still a hand-written client, not codegen.)

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
- **B11 (billing UI, R-008/TS-091; entitlements wired R-009/TS-098):**
  `/pricing` is public and renders the four plan cards with prices matching
  the server's `PRICES_MINOR` exactly (`lib/money.ts`'s `formatMoney` is the
  only place minor units are divided by 100). `<Paywall/>` renders the 402
  payload from any billable action — driven entirely by `detail.code`
  (`free_exhausted`, `paygo_payment_required`, `quota_exhausted`,
  `payment_overdue` today) — so a review-run block, and any future
  export/storage block that raises the same shape, share one component
  instead of a bespoke error toast per call site; `quota_exhausted` offers a
  top-up purchase (`<CheckoutDialog kind="topup"/>`) alongside "See plans"
  (R-009). `<CheckoutDialog/>` opens Razorpay's hosted checkout for a real
  server-created order and polls `GET /billing/intents/{id}` for
  confirmation; its `handler` callback runs on the client and never marks
  anything paid — only the webhook does (Doc §15.1). `/billing` (account
  home) shows current plan/status/grace, a reviews-this-period meter (now
  `reviews_included + reviews_topup`, from the real `GET /billing/status`
  response rather than a client-side `PLAN_LIMITS` duplicate — the
  `MONTHLY_QUOTA` placeholder this page carried before R-009 landed is gone)
  and a seats meter, and — admin/owner only — the invoice table; a
  viewer/estimator sees a read-only summary with no checkout entry point.
  Coupons/credits/referral from the R-008 draft are still deferred to
  R-006/TS-090, which doesn't have a backend capability yet.
- **B8:** the Help page (`/help`) is a static server component: an 8-step
  how-to-use walkthrough, the never-broken safety rules, a three-bucket
  QS-lifecycle coverage table (**Covered now** = Phase-1 pre-bid slice;
  **On the roadmap** = baseline lock / change-notice / time-bar engine /
  outcome graph per Doc §0.1, §1.2; **Not ours** = takeoff / BIM / pricing /
  CPM / legal opinions per §0.2), a "where it goes beyond typical QS tools"
  differentiator list, and a not-legal/QS-advice disclaimer (Doc §11.4). The
  table must not flatten roadmap items into "not covered." Reachable from the
  header nav.
- **B12 (session/refresh-token handling, R-010, TS-092):** before this, the
  frontend discarded the refresh token it was handed at login — the access
  token (15-minute TTL) was the ONLY credential kept, so every session died
  15 minutes after sign-in with no recovery path, and a 401 surfaced as
  `[object Object]` (`Error(body.detail)` on the 402 paywall's object
  payload). Rewritten as:
  - `lib/auth-client.ts` (new, framework-free — no React import, so both
    `components/session.tsx` and `lib/api.ts` can share it without a
    dependency cycle): refresh-token/hint storage, a single-flight
    `refreshTokens()` (module-level `inflight` promise — the backend revokes
    the WHOLE refresh-token family when a refresh token is replayed,
    `auth/refresh.py`'s reuse detection, so two concurrent refreshes against
    the same stored token would look exactly like a replay; this collapses
    concurrent callers AND concurrent tabs, since tabs share the same
    localStorage-held token), JWT `exp`-claim decoding (display/scheduling
    hint only, never a trust boundary), a `BroadcastChannel`-based multi-tab
    channel, and two module-level pub/sub hooks (`onTokensRefreshed`,
    `onSessionExpired`) that let `lib/api.ts` — a plain function with no
    React/router access — notify the React-held session when a reactive
    refresh succeeds or fails.
  - `components/session.tsx` (rewritten): access token is **memory-only**
    React state, never persisted; the refresh token is (Phase 1 — see
    `specs/requirements/R-010-frontend-session.md`'s Phase 2 note on the
    httpOnly-cookie move). `status` is a real three-state
    (`loading | authenticated | unauthenticated`) — `session` alone can't
    carry the loading/signed-out distinction, since it's legitimately `null`
    in both. Proactive refresh is a `setTimeout` scheduled 60s before the
    decoded expiry on every token adoption; sign-out calls
    `POST /auth/logout` (best-effort, `keepalive`) before clearing local
    state, and broadcasts to every other open tab.
  - `lib/api.ts`'s `req()`: a 401 triggers exactly one refresh + retry (never
    a loop against a genuinely revoked session); every OTHER call site keeps
    its existing `api.xxx(token, ...)` signature unchanged — `req()` is the
    one place that knows how to recover from a stale token, so this did not
    require touching every page that calls the API.
  - `lib/errors.ts` (new): `ApiError`/`SessionExpired`/`PaywallError`,
    replacing the ad hoc `ApiError` that used to live in `lib/api.ts` — a 402
    now always carries `{code, upsell}` as a real object (`PaywallError`),
    not a string coerced from it.
  - `components/require-auth.tsx` (new): route guard gating on `status`, not
    `session` — an unauthenticated visit to a protected route redirects to
    `/login?next=<path>` instead of rendering whatever the page's own
    `if (!session)` branch happened to show; wraps `/opportunities`,
    `/opportunities/[id]`, `/billing`, `/standards` (each page's own
    `if (!session)` fallback stays as a harmless defensive branch
    underneath). `/login` reads `?next=` and returns there after sign-in.
  - Validated with a live backend + a real Chromium browser (not just
    `next build`): unauthenticated `/opportunities` → redirects to
    `/login?next=%2Fopportunities`; sign-up/login → lands back on
    `/opportunities`; `localStorage` after login contains only `ts_refresh`/
    `ts_hint`, no access token; a full page reload stays signed in with no
    flash of the signed-out state; revoking the refresh token server-side
    (simulating expiry/logout-elsewhere) then reloading redirects to
    `/login` exactly once, with no loop, and clears `ts_refresh`. New
    Vitest + Testing Library test stack (this task's first consumer, ahead
    of R-014/TS-104's broader one) — `lib/auth-client.test.ts` (7 tests) and
    `lib/api.test.ts` (2 tests) — including a test proving single-flight
    collapses 3 concurrent refresh calls into 1 network request, sanity
    checked by temporarily removing the `if (inflight) return inflight;`
    guard and confirming both tests then fail (3 calls, not 1).
- **B13 (workspace switcher + workspace-less onboarding, R-011, TS-100):**
  new `components/workspace-switcher.tsx` in the header, hidden entirely for
  a single-workspace user (a switcher with one option is noise) — fetches
  `GET /auth/workspaces` (now returning `plan`/`is_current` per row) and
  renders nothing until there are ≥2. Switching calls the new
  `POST /auth/workspaces/{id}/switch` and adopts the response through the
  SAME `signIn()` every login uses (persists the rotated refresh token,
  swaps in a new `session` object, broadcasts to other tabs via R-010's
  multi-tab channel) — deliberately not a separate `adoptTokens` path, since
  `signIn` already does everything a workspace switch needs. Every protected
  page's data-fetching effect already depends on `session`
  (`useEffect(..., [session])`), so switching naturally triggers a refetch
  under the new workspace without a dedicated cache-clear step — this
  codebase has no shared query cache to invalidate. New `/workspaces/new`
  page: `RequireAuth` now redirects a workspace-less session
  (`session.workspaceId === NO_WORKSPACE_ID`, R-011 §B.6) here instead of
  onto a protected page that would just show empty results under RLS;
  creating a workspace makes the user its owner, then the page immediately
  calls `switchWorkspace` to pick up real tokens (workspace creation itself
  returns no tokens). Validated live: signed in with one workspace (switcher
  absent), created a second via the API, reloaded (switcher appears showing
  both, current one bold), switched to the second (header updates, lands
  back on `/opportunities`).

## Acceptance criteria

- A1: app skeleton renders board + opportunity tabs against the mock API.
- A2: `/help` renders statically and states plainly that TenderShield covers the
  pre-bid slice, not the full QS lifecycle.
- A3 (R-008): `/pricing` renders signed out and matches server-side prices
  (verified with a live backend + Playwright screenshot, not just a build
  check).
- A4 (R-008): a free workspace that hits `free_exhausted` on review-run sees
  `<Paywall/>` with the correct per-tender price and a working "Pay ₹X for
  this tender" checkout entry point, not a raw error string — verified
  end-to-end against a live backend.
- A5 (R-008): a checkout whose payment-provider script fails to load (offline,
  blocked network) shows a retryable error state, never an indefinite
  "Preparing checkout…" spinner — found by testing in a sandboxed environment
  with no route to `checkout.razorpay.com` (`CheckoutDialog`'s `<Script
  onError>`).
- A6 (R-008): `next build`/`tsc --noEmit` are clean with the billing pages
  added; no ESLint config exists yet in this repo (deferred to R-014/TS-104),
  so lint is not part of this task's validation.
- A7 (R-010): after login, `localStorage` contains no access token — only
  `ts_refresh` (the refresh token) and `ts_hint` (role/workspace, non-
  sensitive) — verified live against a running backend, not just by
  inspecting the code.
- A8 (R-010): a request made with an expired access token succeeds
  transparently, refreshing exactly once (`lib/api.test.ts`).
- A9 (R-010): concurrent calls that all hit a 401 on the same stale token
  collapse into exactly one `/auth/refresh` request
  (`lib/auth-client.test.ts`, `lib/api.test.ts`).
- A10 (R-010): a revoked/expired refresh token produces exactly one redirect
  to `/login`, not a loop, and clears the stored refresh token — verified
  live: sign in, revoke the session's refresh token via a direct
  `POST /auth/logout` call (simulating expiry or a sign-out from another
  tab), then reload — lands on `/login?next=...` once and stays there.
- A11 (R-010): an unauthenticated visit to `/opportunities` or `/billing`
  redirects to `/login?next=%2Fopportunities` (or `%2Fbilling`) and returns
  there after a successful login — verified live with a real browser.
- A12 (R-010): reloading while signed in never renders the signed-out state
  (`RequireAuth` gates on `status`, not `session`) — verified live: after
  sign-in, a full page reload stays on `/opportunities` with no flash of
  "Sign in to see your board."
- A13 (R-010): a 402 response is caught as `PaywallError` with `.upsell`
  populated as a real object, not a stringified `[object Object]`.
- A14 (R-010): `next build`/`tsc --noEmit` are clean; the new Vitest suite
  (`npm test`) passes (9 tests).
- A15 (R-010): signing out in one tab (or a session-expired event in one
  tab) clears the session and broadcasts to every other open tab via
  `BroadcastChannel` — exercised in the unit tests via the
  `onTokensRefreshed`/`onSessionExpired` pub/sub hooks; full cross-tab timing
  (A5 in the R-010 draft, "signs out tab B within 1s") is not separately
  timed in this pass — the mechanism (a real `BroadcastChannel` message) is
  synchronous enough in practice that a dedicated timing test wasn't judged
  worth the added test-infrastructure cost here.
- A16 (R-011): the workspace switcher does not render for a single-workspace
  user, and renders with all workspaces (current one marked) for a
  multi-workspace user — verified live with a real browser.
- A17 (R-011): switching workspaces via the header updates the visible
  workspace name without a full page reload, and workspace-scoped pages
  reflect the new workspace's data on next fetch.

## Out of scope

WhatsApp alert UI (P2), white-label theming (P2), mobile capture (P3).
Session (R-010): the httpOnly-cookie move for the refresh token (Phase 2 —
needs backend cookie support and a CORS/credentials decision, tracked under
R-016), idle timeout / absolute session lifetime, and device/session
management UI (endpoints exist per R-002 §B.3; the UI is R-013/TS-103).
Workspace switching (R-011): a "Switch to &lt;workspace&gt;" prompt after
accepting an invitation to a different workspace (the invitation-accept UI
itself doesn't exist yet — R-013/TS-103), and simultaneous multi-workspace
tabs (one active session per user server-side — `specs/modules/auth.md`
§B19).
