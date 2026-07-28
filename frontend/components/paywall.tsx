"use client";

// The conversion surface (R-008 §2). Renders the 402 payload from R-004/plans.py's
// PaywallError — driven entirely by `code`, so every blocked action (review run
// today; export and storage quota once those raise the same shape) reuses one
// component instead of a bespoke error toast per call site.
//
// Coupon field (R-006/TS-090) and a "seats"/"storage" variant of the upsell
// copy (R-009/TS-098) are deferred — those backend capabilities don't exist
// yet. This ships the three codes the backend can raise today: free_exhausted
// and paygo_payment_required (plans.py `authorize`, both payable per-tender
// from here) and quota_exhausted (no per-tender payment path yet — TS-098).

import { useState } from "react";
import { formatMoney } from "@/lib/money";
import { useSession } from "@/components/session";
import { CheckoutDialog } from "@/components/checkout-dialog";

export type PaywallDetail = {
  code: string;
  upsell?: {
    paygo_price_inr_paise?: number;
    topup_price_inr_paise?: number;
    plans?: string[];
    opportunity_id?: string | null;
  };
};

const COPY: Record<string, { title: string; body: string; cta: string }> = {
  free_exhausted: {
    title: "You've used your free review",
    body: "Your first review is on us. To review this tender, pay per tender or move to Pro.",
    cta: "See plans",
  },
  quota_exhausted: {
    title: "You've used this month's reviews",
    body: "Your plan's monthly review quota is used up. Move up a plan to continue.",
    cta: "See plans",
  },
  paygo_payment_required: {
    title: "Pay to start this review",
    body: "Your plan is pay-as-you-go — each tender is paid for before its review runs.",
    cta: "See plans",
  },
};

export function Paywall({
  detail,
  onDismiss,
  onPaid,
}: {
  detail: PaywallDetail;
  /** "Not now" or backdrop dismiss — no entitlement changed. */
  onDismiss: () => void;
  /** Checkout confirmed paid — defaults to onDismiss if the caller doesn't
   * need to retry the blocked action. */
  onPaid?: () => void;
}) {
  const { session } = useSession();
  const [showCheckout, setShowCheckout] = useState(false);
  const copy = COPY[detail.code] ?? {
    title: "Upgrade required",
    body: "This action needs a paid plan.",
    cta: "See plans",
  };

  const priceMinor =
    detail.code === "free_exhausted" || detail.code === "paygo_payment_required"
      ? detail.upsell?.paygo_price_inr_paise
      : undefined;
  const opportunityId = detail.upsell?.opportunity_id ?? undefined;
  const payable = detail.code === "free_exhausted" || detail.code === "paygo_payment_required";

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 p-4"
    >
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <h2 className="text-lg font-bold text-ink">{copy.title}</h2>
        <p className="mt-2 text-sm text-slate-600">{copy.body}</p>

        {priceMinor !== undefined && (
          <p className="mt-3 text-2xl font-bold text-ink">
            {formatMoney(priceMinor)} <span className="text-sm font-normal text-slate-500">per tender</span>
          </p>
        )}

        <div className="mt-5 flex flex-col gap-2">
          {payable && opportunityId && (
            <button
              onClick={() => setShowCheckout(true)}
              className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              Pay {priceMinor !== undefined ? formatMoney(priceMinor) : ""} for this tender
            </button>
          )}
          <a
            href="/pricing"
            className="rounded-md border border-slate-300 px-4 py-2 text-center text-sm font-medium text-ink hover:bg-slate-50"
          >
            {copy.cta}
          </a>
          <button onClick={onDismiss} className="mt-1 text-xs text-slate-400 hover:text-slate-600">
            Not now
          </button>
        </div>
      </div>

      {showCheckout && session && opportunityId && (
        <CheckoutDialog
          token={session.token}
          kind="paygo"
          opportunityId={opportunityId}
          onClose={() => setShowCheckout(false)}
          onSuccess={() => {
            setShowCheckout(false);
            (onPaid ?? onDismiss)();
          }}
        />
      )}
    </div>
  );
}
