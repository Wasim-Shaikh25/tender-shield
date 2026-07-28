# R-008 — Billing UI: pricing, checkout, paywall, invoices, usage

**Status:** implemented (thin path) — `/pricing`, `<Paywall/>`,
`<CheckoutDialog/>`, `/billing` account page shipped and validated end to
end against a live backend (Playwright screenshots). Coupons/credits/
referral (needs R-006/TS-090) and real seats/storage/entitlement fields
(needs R-009/TS-098) are deferred — those backend capabilities don't exist
yet; see `specs/frontend.md` B11 for what shipped vs. what's deferred.
Fixed two real backend bugs found while wiring this UI — see
`specs/modules/billing.md` B9/B10.
**Severity:** P0 — a user cannot give this product money through its own interface
**Requirement refs:** Doc §7, §9, §15
**Task refs:** TS-091
**Gap refs:** `docs/GAP_ANALYSIS.md` §4.1
**Specs to update:** `specs/frontend.md`, `specs/modules/billing.md`

## Purpose

`frontend/lib/api.ts` contains **no billing calls at all** — not `status`, not
`checkout`, not `invoices`, not `authorize-review`. There is no pricing page, no
plan comparison, no payment method, no invoice list, no usage meter, and no
upgrade prompt. The complete monetization journey today is:

> paywall blocks a review → 402 with an upsell payload → **nothing**

Depends on R-004 (the 402 actually fires) and R-005 (there is an order to open).

## API client additions

```ts
// frontend/lib/api.ts

export type Plan = "free" | "paygo" | "pro" | "scale";

export type BillingStatus = {
  plan: Plan;
  plan_status: "active" | "past_due" | "cancelled" | "trialing";
  free_review_used: boolean;
  reviews_this_month: number;
  reviews_included: number | null;   // null = not a metered plan
  seats_used: number;
  seats_included: number;
  storage_used_bytes: number;
  storage_quota_bytes: number;
  grace_until: string | null;
  current_period_end: string | null;
  credit_balance_minor: number;
};

export type CouponQuote = {
  valid: boolean;
  code_reason?: string;
  code?: string;
  list_amount_minor: number;
  discount_minor: number;
  credit_applied_minor: number;
  tax_minor: number;
  total_minor: number;
  currency: string;
  description?: string;
};

export type CheckoutHandle = {
  intent_id: string;
  provider: "razorpay" | "stripe";
  order_id: string;
  amount_minor: number;
  currency: string;
  breakdown: { list: number; discount: number; tax: number; total: number };
  checkout: Record<string, unknown>;
};

export const billing = {
  status: (token: string) => req<BillingStatus>("/billing/status", {}, token),

  validateCoupon: (token: string, code: string, plan: Plan, kind: string) =>
    req<CouponQuote>("/billing/coupons/validate",
      { method: "POST", body: JSON.stringify({ code, plan, kind }) }, token),

  checkout: (token: string, body: { kind: "paygo" | "subscription"; plan?: Plan;
                                    opportunity_id?: string; coupon_code?: string }) =>
    req<CheckoutHandle>("/billing/checkout", { method: "POST", body: JSON.stringify(body) }, token),

  intent: (token: string, id: string) =>
    req<{ status: string }>(`/billing/intents/${id}`, {}, token),

  invoices: (token: string) => req<{ invoices: Invoice[] }>("/billing/invoices", {}, token),

  credits: (token: string) =>
    req<{ balance_minor: number; currency: string; entries: CreditEntry[] }>("/billing/credits", {}, token),

  referral: (token: string) =>
    req<{ code: string; url: string; stats: { signed_up: number; qualified: number } }>(
      "/billing/referral", {}, token),
};
```

### Money formatting — one helper, never inline

```ts
// frontend/lib/money.ts

/** Minor units → display string. The API only ever sends minor units
 *  (Doc §7: money in paise, never float); dividing by 100 happens here and
 *  nowhere else, so a rounding bug has exactly one place to live. */
export function formatMoney(minor: number, currency = "INR", locale = "en-IN"): string {
  return new Intl.NumberFormat(locale, {
    style: "currency", currency, minimumFractionDigits: 0, maximumFractionDigits: 2,
  }).format(minor / 100);
}
```

## Pages and components

### 1. `/pricing` — public, no auth

Three plan cards (Pro highlighted) plus paygo, and an honest feature matrix.
Because the free tier is a *complete* review (Doc §706), the free column must say
so — "full review, watermarked export" — not imply a crippled trial.

```tsx
// frontend/app/pricing/page.tsx
const PLANS = [
  { id: "free",  name: "Free",   priceMinor: 0,       cadence: "",
    line: "One complete tender review. Watermarked export.",
    features: ["1 full review", "All risk patterns", "Deadline wall", "2 seats", "Watermarked export"] },
  { id: "paygo", name: "Pay as you go", priceMinor: 750_000, cadence: "per tender",
    line: "For occasional bids.",
    features: ["Unlimited tenders, pay per review", "Clean export", "3 seats"] },
  { id: "pro",   name: "Pro",    priceMinor: 2_499_900, cadence: "per month", highlight: true,
    line: "For firms bidding regularly.",
    features: ["10 reviews / month", "Clean export", "10 seats", "Baseline lock", "Priority support"] },
  { id: "scale", name: "Scale",  priceMinor: 7_499_900, cadence: "per month",
    line: "For multi-office contractors.",
    features: ["40 reviews / month", "25 seats", "Custom notice standards", "Onboarding session"] },
];
```

Signed-in users see "Current plan" on their own tier and "Upgrade"/"Downgrade"
elsewhere. Signed-out users get "Start free" → `/signup?plan=pro`.

### 2. `<Paywall />` — the conversion surface

This component renders the 402 payload from R-004. It is the single most
commercially important component in the app, and it appears in at least three
places (review run, export, storage quota), so it must be one component driven by
the error code:

```tsx
// frontend/components/paywall.tsx

const COPY: Record<string, { title: string; body: string; cta: string }> = {
  free_exhausted: {
    title: "You've used your free review",
    body: "Your first review is on us. To review this tender, pay per tender or move to Pro.",
    cta: "See plans",
  },
  quota_exhausted: {
    title: "You've used this month's reviews",
    body: "Your plan includes {included} reviews per month. Add a top-up or move up a plan.",
    cta: "Add reviews",
  },
  paygo_payment_required: {
    title: "Pay to start this review",
    body: "₹7,500 for a complete review of this tender pack.",
    cta: "Pay and start",
  },
  storage_quota_exceeded: {
    title: "You're out of storage",
    body: "Delete old tender packs or move up a plan.",
    cta: "See plans",
  },
};
```

It must show what the user gets, the price **including tax**, and a coupon field.
Every dismissal fires `billing.paywall_dismissed` to analytics —
`specs/modules/billing.md` B6 requires dismissals to be logged, and that number
is the conversion denominator.

### 3. `/billing` — account billing home (admin+)

Sections: current plan + renewal date; usage meters (reviews, seats, storage);
payment method; credit balance; referral code with copy button; invoice table
with PDF download; plan change; cancel.

Usage meters must degrade honestly — an unmetered plan shows "unlimited", not a
bar at 0%.

```tsx
function UsageMeter({ label, used, included }: { label: string; used: number; included: number | null }) {
  if (included === null) return <Row label={label} value={`${used} used`} />;
  const pct = Math.min(100, Math.round((used / included) * 100));
  const tone = pct >= 100 ? "bg-red-500" : pct >= 80 ? "bg-amber-500" : "bg-ink";
  return (
    <div>
      <div className="flex justify-between text-sm"><span>{label}</span><span>{used} / {included}</span></div>
      <div className="mt-1 h-2 rounded bg-slate-100" role="progressbar"
           aria-valuenow={used} aria-valuemin={0} aria-valuemax={included} aria-label={label}>
        <div className={`h-2 rounded ${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
```

### 4. `<CheckoutDialog />` — provider handoff

```tsx
async function startCheckout(body: CheckoutBody) {
  const handle = await billing.checkout(token, body);
  const rz = new window.Razorpay({
    key: process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID,
    order_id: handle.order_id,
    amount: handle.amount_minor,
    currency: handle.currency,
    name: "TenderShield",
    // The handler runs on the CLIENT and activates NOTHING (Doc §15.1).
    // It only starts polling; the webhook is the only thing that grants a plan.
    handler: () => pollIntent(handle.intent_id),
    modal: { ondismiss: () => setState("cancelled") },
  });
  rz.open();
}

async function pollIntent(intentId: string) {
  // The webhook may land before or after the browser returns. Poll with a
  // ceiling and a clear "still processing" state — never claim success from
  // the client-side handler alone.
  for (let i = 0; i < 20; i++) {
    const { status } = await billing.intent(token, intentId);
    if (status === "paid") return setState("success");
    if (status === "failed" || status === "expired") return setState("failed");
    await new Promise((r) => setTimeout(r, 1500));
  }
  setState("pending_confirmation");   // "Payment received, activating…"
}
```

The Razorpay SDK is the one permitted external script. Load it with `next/script`
`strategy="lazyOnload"` and only on routes that need it, and add
`checkout.razorpay.com` to the CSP (R-014).

### 5. Upgrade nudges

- Free workspace on `/opportunities`: a dismissible banner once the free review
  is used.
- Export button when the pack will be watermarked: a "Remove watermark" link.
  This is the highest-intent moment in the product — the user is looking at
  output they want to send to a client.
- 80% of monthly quota: a banner on the dashboard.

Nudges must be dismissible and must not reappear within 7 days. A paywall that
nags stops being read.

## Behavior

- **B1** Every 402 from any endpoint renders `<Paywall />` driven by
  `detail.code`; no raw error strings reach the user.
- **B2** Prices displayed are computed by the server; the client never computes
  a total.
- **B3** The client never marks anything paid — success is confirmed by polling
  the intent, whose status only the webhook sets.
- **B4** A dismissed or abandoned checkout leaves no state change.
- **B5** Invoice PDFs download through the authorized route with the bearer
  token, never a public link.
- **B6** Billing pages require `admin`; `viewer`/`estimator` see a read-only
  usage summary and "ask your workspace admin to upgrade".
- **B7** All money is rendered by `formatMoney`; minor units never reach a
  template.
- **B8** Every paywall view, dismissal and checkout start/complete is
  instrumented.

## Acceptance criteria

- **A1** `/pricing` renders without auth and matches `PRICES_MINOR` server-side.
- **A2** A free workspace that hits `free_exhausted` sees the paywall with the
  paygo price and a plan link — not an error toast.
- **A3** Applying `PILOT25` in the paywall shows list, discount, tax and total,
  all from `validateCoupon`.
- **A4** Closing the Razorpay modal returns to the app with no plan change.
- **A5** After a successful test payment, `/billing` shows the new plan and one
  invoice; the invoice PDF downloads.
- **A6** A `viewer` navigating to `/billing` sees the read-only summary and no
  checkout button.
- **A7** A workspace at 8/10 reviews sees the 80% banner; at 10/10 the review
  button opens the paywall.
- **A8** No component divides by 100 outside `lib/money.ts` (lint rule or test).
- **A9** With the API unreachable, billing pages show a retry state, not a blank
  page.

## Out of scope

- Self-serve plan downgrade with proration — R-009.
- Dunning email templates — R-015.
- Admin coupon-management UI — superadmin console, R-013.

## Assumptions

- `assumption:` Razorpay Checkout (hosted modal) rather than a custom card form —
  it keeps the app out of PCI scope entirely.
