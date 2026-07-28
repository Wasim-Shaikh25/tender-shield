# R-014 — Design system, error copy, accessibility, frontend tests

**Status:** draft
**Severity:** P2 — quality and velocity; blocks nothing, slows everything
**Requirement refs:** Doc §9
**Task refs:** TS-104
**Gap refs:** `docs/GAP_ANALYSIS.md` §4.6
**Specs to update:** `specs/frontend.md`

## Purpose

The frontend is 9 pages and ~2.1k lines with three runtime dependencies. Tailwind
utilities are written inline in every page, `Field` is redeclared per file
(`login/page.tsx:82`), raw backend error codes are rendered to users, there are no
tests, and there is no accessibility work. None of this blocks a release; all of
it makes every subsequent task slower and the product feel unfinished to a
customer paying ₹24,999/month.

## A. Design tokens

`tailwind.config.ts` defines `ink` and little else; spacing, type scale and state
colours are ad hoc.

```ts
// frontend/tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        ink:     { DEFAULT: "#0F172A", muted: "#475569", subtle: "#94A3B8" },
        surface: { DEFAULT: "#FFFFFF", raised: "#F8FAFC", sunken: "#F1F5F9" },
        // Severity is domain vocabulary, not decoration. These five map 1:1 to
        // Finding.severity so a badge can never disagree with the register.
        severity: {
          critical: "#B91C1C", high: "#EA580C", medium: "#CA8A04",
          low: "#0369A1", info: "#475569",
        },
        // Finding provenance (product invariant 5: tri-state labelling).
        provenance: { extracted: "#1D4ED8", deterministic: "#047857", ai: "#7C3AED" },
      },
      borderRadius: { card: "0.75rem" },
    },
  },
};
```

Severity and provenance belong in the token layer specifically because they are
*meaning*, not style. `frontend/lib/labels.ts` already centralises category
labels — the same discipline extends here.

## B. Component primitives

`frontend/components/ui/`: `Button`, `Input`, `Select`, `Textarea`, `Field`,
`Card`, `Badge`, `Table`, `Dialog`, `Toast`, `Tabs`, `Skeleton`, `EmptyState`,
`Banner`, `ProgressBar`.

```tsx
// frontend/components/ui/button.tsx
const VARIANTS = {
  primary:   "bg-ink text-white hover:bg-ink/90",
  secondary: "border border-slate-300 bg-white hover:bg-slate-50",
  danger:    "bg-red-600 text-white hover:bg-red-700",
  ghost:     "hover:bg-slate-100",
} as const;

export function Button({ variant = "primary", size = "md", loading, disabled, children, ...rest }: Props) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors",
        // Focus rings are not optional: keyboard users currently have no
        // visible focus state anywhere in the app (R-014 §D).
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
        VARIANTS[variant], SIZES[size],
      )}
    >
      {loading && <Spinner className="h-4 w-4" aria-hidden />}
      {children}
    </button>
  );
}
```

The existing tab strip (`opportunities/[id]/page.tsx:215`) is a `<button>` row
with no ARIA. `Tabs` must implement the roving-tabindex pattern with
`role="tablist"`, `role="tab"`, `aria-selected` and arrow-key navigation.

## C. Error copy — the highest-value item here

```tsx
// login/page.tsx:29
setError(err instanceof Error ? err.message : "Something went wrong");
```

`err.message` is the backend's error code, so users are shown `free_exhausted`,
`insufficient_role`, `invalid_credentials`. One table fixes every screen:

```ts
// frontend/lib/errors.ts

/** Backend error code → human copy. The API returns machine codes by design
 *  (auth/router.py:93 _STATUS); translating them is the client's job, and
 *  doing it in one table means no screen invents its own wording. */
export const ERROR_COPY: Record<string, { title: string; body?: string; action?: Action }> = {
  invalid_credentials: { title: "That email or password isn't right." },
  account_locked:      { title: "Too many attempts.",
                         body: "Your account is locked for a few minutes. Try again shortly or reset your password.",
                         action: { label: "Reset password", href: "/forgot-password" } },
  email_taken:         { title: "That email already has an account.",
                         action: { label: "Sign in instead", href: "/login" } },
  rate_limited:        { title: "Too many requests.", body: "Wait a moment and try again." },
  insufficient_role:   { title: "You don't have permission for that.",
                         body: "Ask a workspace admin to change your role." },
  not_workspace_member:{ title: "You're not a member of that workspace." },
  seat_limit_reached:  { title: "No seats left on your plan." },
  review_incomplete:   { title: "Finish reviewing before exporting.",
                         body: "Every finding needs an accept or reject decision. This is deliberate — nothing leaves TenderShield unreviewed." },
  free_exhausted:      { title: "You've used your free review." },
  quota_exhausted:     { title: "You've used this month's reviews." },
  file_too_large:      { title: "That file is too large." },
  unsupported_file_type:{ title: "We can't read that file type.",
                         body: "Upload a PDF, Word, Excel, CSV or ZIP file." },
  storage_quota_exceeded: { title: "You're out of storage." },
  needs_ocr:           { title: "This document is scanned.",
                         body: "Text extraction needs OCR, which is off for this workspace." },
  session_expired:     { title: "You've been signed out.", body: "Sign in to continue." },
  network_error:       { title: "Can't reach TenderShield.", body: "Check your connection and try again." },
};

export function errorCopy(err: unknown) {
  const code = err instanceof ApiError ? err.code : "unknown";
  return ERROR_COPY[code] ?? { title: "Something went wrong.", body: "Try again, or contact support if it persists." };
}
```

`review_incomplete` deserves its explanatory sentence. A user blocked from
exporting will otherwise read it as a bug, when it is the product's central
quality guarantee (Doc §11.4).

## D. Accessibility

Nothing has been done here. The baseline for a paid B2B tool:

- **Focus visible** on every interactive element (§B).
- **Semantic HTML**: `<main>`, `<nav>`, `<h1>` per page, correct heading order.
- **Labels**: every input has a `<label>`; icon-only buttons carry `aria-label`.
- **Tabs**: full ARIA tab pattern with arrow keys.
- **Dialogs**: focus trap, `Escape` to close, focus restored on close.
- **Live regions**: `aria-live="polite"` for toasts; `assertive` for deadline
  warnings.
- **Contrast**: 4.5:1 for body text, 3:1 for large text — verify the severity
  palette, which is where colour choices meet meaning.
- **Never colour alone**: severity and deadline urgency carry icon + text
  (R-012 §B.6).
- **Reduced motion**: honour `prefers-reduced-motion`.
- **Skip link** to main content.

Target WCAG 2.1 AA. Add `eslint-plugin-jsx-a11y` and `@axe-core/react` in dev, and
an axe pass in CI on the main routes.

## E. Testing — there is none

```json
"devDependencies": {
  "vitest": "^2", "@vitejs/plugin-react": "^4",
  "@testing-library/react": "^16", "@testing-library/user-event": "^14",
  "jsdom": "^25", "msw": "^2",
  "@playwright/test": "^1.49",
  "eslint-plugin-jsx-a11y": "^6", "@axe-core/react": "^4"
}
```

Three layers, in priority order:

1. **Unit (Vitest)** — `lib/`: `money.ts` formatting, `errors.ts` mapping,
   `auth-client.ts` single-flight refresh (R-010).
2. **Component (Testing Library + MSW)** — paywall renders each 402 code; forms
   validate; tabs are keyboard navigable; export handles 403.
3. **E2E (Playwright)** — the flows that must never break:
   signup → create opportunity → upload → run review → accept → export;
   paywall → checkout → plan active; invitation accept; workspace switch.

Chromium is preinstalled in this repo's dev environment
(`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`), so E2E needs no download step.

CI gains `npm run test` and `npm run test:e2e` alongside the existing build job.
Today CI runs `npm run build` only, so **nothing verifies frontend behaviour at
all**.

## F. Structural gaps

- **`/signup` does not exist.** Signup is a `useState` toggle inside `/login`
  defaulting to signup mode (`login/page.tsx:12`). It cannot be linked,
  shared, or measured — a real problem for a referral-led GTM where the invite
  link *is* the funnel. Split into `/login` and `/signup`, each linking to the
  other, both honouring `?next=`.
- **No `error.tsx`, `not-found.tsx`, `loading.tsx`** at the app or route level.
  An API failure currently blanks the page.
- **No error boundary** around the app shell.
- **Loading states are text swaps** on buttons; add skeletons for page loads.
- **No CSP.** Add via `next.config.mjs` headers, allowing the Razorpay checkout
  script (R-008 §4) and nothing else inline.
- **No SEO/meta/OG** on the marketing page; no sitemap; no favicon set.
- **No dark mode** and **no i18n** — both deferred, but the token layer (§A) and
  the copy table (§C) are the prerequisites, so doing them now keeps the door
  open cheaply.

## Behavior

- **B1** Every screen composes `components/ui/` primitives; no bespoke inline
  Tailwind for buttons, inputs or cards.
- **B2** Design tokens are the only source of colour, spacing and radius;
  severity and provenance colours map 1:1 to their domain enums.
- **B3** Every user-facing error is resolved through `ERROR_COPY`; no raw code
  reaches the DOM.
- **B4** Every interactive element is keyboard reachable with a visible focus
  state.
- **B5** Every route has loading, empty and error states.
- **B6** Signup and login are separate routes.
- **B7** CI runs unit, component and E2E tests plus an a11y pass.

## Acceptance criteria

- **A1** No `<button className="...bg-...">` outside `components/ui/` (lint rule).
- **A2** Rendering an `ApiError` with an unmapped code shows the generic message,
  never the raw code. A test asserts no `ERROR_COPY` key appears verbatim in the
  DOM for mapped codes.
- **A3** The full signup → export flow is completable by keyboard alone.
- **A4** axe reports zero critical violations on `/`, `/login`, `/signup`,
  `/dashboard`, `/opportunities`, `/opportunities/[id]`, `/pricing`, `/billing`.
- **A5** All text meets 4.5:1 contrast; severity badges are distinguishable in
  greyscale.
- **A6** `/signup` is directly linkable and honours `?next=`.
- **A7** A thrown render error shows the error boundary, not a white screen.
- **A8** Playwright covers the four critical flows and runs in CI.
- **A9** `prefers-reduced-motion` suppresses transitions.
- **A10** No component divides by 100 to format money (R-008 §A8).

## Out of scope

- Dark mode, i18n, animation system, a published component library.
- Visual regression testing.
- Full design refresh — this is systematisation of what exists, not a redesign.

## Assumptions

- `assumption:` Tailwind stays; no move to a component library. Headless
  primitives (Radix) may be introduced for Dialog/Tabs if hand-rolled ARIA proves
  fragile.
