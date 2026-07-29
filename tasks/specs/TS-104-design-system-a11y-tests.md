# TS-104 — Design system, error copy table, `/signup` route, a11y pass, frontend test stack

**Status:** todo
**Requirement:** [R-014](../../specs/requirements/R-014-design-system.md)
**Spec(s) updated:** none (to be updated when built)
**Module(s):** frontend
**Severity / Gate:** P2 · Gate 3

## What this builds

The frontend foundations that have simply never been built: design tokens
beyond one `ink` color, a shared component primitive library, a single
error-code-to-copy translation table (today `err.message` — the backend's
raw error code — is shown directly to users), an accessibility pass
(nothing has been done here), and a frontend test stack (today CI runs
`npm run build` only — nothing verifies frontend *behavior*).

## Implementation (reference plan — not yet built)

```ts
// frontend/tailwind.config.ts — severity/provenance as tokens, not decoration
severity: { critical: "#B91C1C", high: "#EA580C", medium: "#CA8A04", low: "#0369A1", info: "#475569" },
provenance: { extracted: "#1D4ED8", deterministic: "#047857", ai: "#7C3AED" },
// These map 1:1 to Finding.severity so a badge can never disagree with the register.
```

```tsx
// frontend/components/ui/button.tsx — one of ~15 shared primitives
export function Button({ variant = "primary", loading, ...rest }) {
  return <button className={cx(
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink",
    // Focus rings are not optional — keyboard users currently have NO
    // visible focus state anywhere in the app.
  )} {...rest} />;
}
```

```ts
// frontend/lib/errors.ts — the highest-value item in this task: one table
// so login/page.tsx:29's `setError(err.message)` stops showing raw codes
// like "free_exhausted" and "insufficient_role" directly to users
export const ERROR_COPY: Record<string, {title, body?, action?}> = {
  invalid_credentials: { title: "That email or password isn't right." },
  review_incomplete: { title: "Finish reviewing before exporting.",
    body: "Every finding needs an accept or reject decision. This is deliberate — nothing leaves TenderShield unreviewed." },
  seat_limit_reached: { title: "No seats left on your plan." },
  ...
};
```

Accessibility baseline (currently nothing): focus-visible everywhere,
semantic HTML (`<main>`, one `<h1>` per page), labeled inputs,
full ARIA tab pattern with arrow keys, dialog focus trap, `aria-live`
regions for toasts/deadline warnings, 4.5:1 contrast (verify the severity
palette specifically — that's where color meets meaning), never color
alone for severity/urgency, `prefers-reduced-motion`, skip link. Target
WCAG 2.1 AA; add `eslint-plugin-jsx-a11y` + `@axe-core/react` + an axe CI
pass.

Test stack (currently none): Vitest unit tests (`lib/money.ts`,
`errors.ts`, `auth-client.ts` single-flight refresh from TS-092), Testing
Library + MSW component tests (paywall renders each 402 code, tabs are
keyboard-navigable), Playwright E2E for the flows that must never break
(signup → upload → review → export; paywall → checkout → plan active;
invitation accept; workspace switch). CI gains `npm run test`/`test:e2e`.

Structural gap fixed in the same pass: `/signup` doesn't exist today —
signup is a `useState` toggle inside `/login`, which can't be linked,
shared, or measured (a real problem for a referral-led GTM where the
invite/signup link is the whole growth loop).

## Files touched (planned)

- `frontend/tailwind.config.ts`, `frontend/components/ui/*.tsx`
- `frontend/lib/errors.ts`
- `frontend/app/signup/page.tsx` (new, split out of `/login`)
- `frontend/{vitest.config.ts,playwright.config.ts}`, `.github/workflows/ci.yml`

## Tests (planned)

The task's deliverable includes the test stack itself — see Implementation.

## Acceptance criteria (R-014, A1–A10)

- [ ] No screen shows a raw backend error code as user-facing text.
- [ ] `/signup` is a real, linkable route.
- [ ] An axe pass on main routes runs in CI and is green.
- [ ] `npm run test`/`test:e2e` run in CI alongside the existing build job.

## Commit

Not yet implemented.
