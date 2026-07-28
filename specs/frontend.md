# Frontend — Spec

**Status:** skeleton implemented — Next.js 15 app (landing, auth, opportunity
board/countdown wall, opportunity detail with document checklist + risk
workbench, static Help page), typed API client, session context. Builds clean;
verified full-stack against the API. Billing UI (pricing, paywall, checkout,
account billing page) now shipped as a thin but complete paid path (R-008,
TS-091) — see below. shadcn, PDF.js source view, and the deadline wall (needs
TS-015) are follow-ups. Plain Tailwind for now (no component kit) so it builds
without extra tooling. The end-user AI assistant is intentionally not
surfaced in the UI; internal codes are rendered through human labels
(`lib/labels.ts`), and the type is set with a system font stack led by Inter.
**Requirement refs:** Doc §9, §0.1–0.2, §11.4, §7, §15
**Task refs:** TS-025, TS-040, TS-091

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
  generated from OpenAPI.

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

## Out of scope

WhatsApp alert UI (P2), white-label theming (P2), mobile capture (P3).
