# TS-091 — Billing UI: pricing, paywall component, checkout, invoices, usage meters

**Status:** done
**Requirement:** [R-008](../../specs/requirements/R-008-billing-ui.md)
**Spec(s) updated:** none
**Module(s):** frontend
**Severity / Gate:** P0 · Gate 1

## What this builds

The frontend surface making TS-087/088/089/090/096's backend billing work
usable: a public `/pricing` page, the `<Paywall />` conversion component
(the single most commercially important component in the app), `/billing`
account home, `<CheckoutDialog />`, and upgrade nudges.

## Implementation

```tsx
// frontend/app/pricing/page.tsx — honest feature matrix; the free tier is a
// COMPLETE review (Doc §706), so its column says so, not "crippled trial"
const PLANS = [
  { id: "free", priceMinor: 0, line: "One complete tender review. Watermarked export." },
  { id: "paygo", priceMinor: 750_000, cadence: "per tender" },
  { id: "pro", priceMinor: 2_499_900, cadence: "per month", highlight: true },
  { id: "scale", priceMinor: 7_499_900, cadence: "per month" },
];
```

```tsx
// frontend/components/paywall.tsx — renders the 402 payload from TS-087,
// one component driven by error code, appears in review-run/export/storage
const COPY: Record<string, {...}> = {
  free_exhausted: { title: "You've used your free review", cta: "See plans" },
  quota_exhausted: { title: "You've used this month's reviews", cta: "Add reviews" },
  paygo_payment_required: { title: "Pay to start this review", cta: "Pay and start" },
  storage_quota_exceeded: { title: "You're out of storage", cta: "See plans" },
};
// Every dismissal fires billing.paywall_dismissed — the conversion denominator.
```

```tsx
// frontend/components/checkout-dialog.tsx
async function startCheckout(body: CheckoutBody) {
  const handle = await billing.checkout(token, body);
  const rz = new window.Razorpay({
    order_id: handle.order_id, amount: handle.amount_minor,
    // The handler runs on the CLIENT and activates NOTHING (Doc §15.1) — it
    // only starts polling; the webhook (TS-089/097) is the only thing that
    // grants a plan.
    handler: () => pollIntent(handle.intent_id),
  });
  rz.open();
}

async function pollIntent(intentId: string) {
  // Never claim success from the client-side handler alone.
  for (let i = 0; i < 20; i++) {
    const { status } = await billing.intent(token, intentId);
    if (status === "paid") return setState("success");
    if (status === "failed" || status === "expired") return setState("failed");
    await sleep(1500);
  }
  setState("pending_confirmation");
}
```

`/billing`: current plan, usage meters (degrade honestly — an unmetered
plan shows "unlimited," not a 0% bar), payment method, credit balance,
referral code, invoice table with PDF download. Upgrade nudges: free-tier
banner, "Remove watermark" link on a would-be-watermarked export (the
highest-intent moment in the product), 80%-quota banner — all dismissible
and non-repeating within 7 days.

## Files touched

- `frontend/app/{pricing,billing}/page.tsx`
- `frontend/components/{paywall,checkout-dialog,usage-meter}.tsx`
- `frontend/lib/api.ts` (billing client additions)

## Tests

None recorded at this task — frontend component/e2e tests are a separate,
later concern per this codebase's testing conventions to date.

## Acceptance criteria (R-008, A1–A2, A4–A9; A3 coupon UI deferred)

- [x] The free plan's pricing copy describes a complete review, not a
      crippled trial.
- [x] `<Paywall />` renders correctly for all four 402 error codes.
- [x] Checkout never claims payment success from the client-side handler
      alone — always polls the intent status.
- [x] Usage meters show "unlimited" for unmetered plans instead of a
      misleading 0% bar.

## Commit

Predates commit-granular history (PR #10 bulk import).
