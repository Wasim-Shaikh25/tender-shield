"use client";

// Provider handoff (R-008 §4). Opens Razorpay's hosted checkout modal for a
// real order the server already created via `billing.checkout`. The Razorpay
// `handler` callback below runs entirely on the client and MUST NOT be
// treated as payment confirmation (Doc §15.1) — it only starts polling the
// intent; the webhook is the only thing that ever marks it paid.

import { useEffect, useState } from "react";
import Script from "next/script";
import { billing, ApiError, type Plan } from "@/lib/api";
import { formatMoney } from "@/lib/money";

declare global {
  interface Window {
    Razorpay?: new (opts: Record<string, unknown>) => { open: () => void };
  }
}

type Phase = "creating" | "awaiting_payment" | "polling" | "success" | "failed" | "cancelled";

export function CheckoutDialog({
  token,
  kind,
  plan,
  opportunityId,
  onClose,
  onSuccess,
}: {
  token: string;
  kind: "paygo" | "subscription" | "topup";
  plan?: Plan;
  opportunityId?: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("creating");
  const [error, setError] = useState<string | null>(null);
  const [amountMinor, setAmountMinor] = useState<number | null>(null);
  const [scriptReady, setScriptReady] = useState(false);

  useEffect(() => {
    if (!scriptReady) return;
    let cancelled = false;

    async function run() {
      try {
        const handle = await billing.checkout(token, {
          kind,
          plan,
          opportunity_id: opportunityId,
        });
        if (cancelled) return;
        setAmountMinor(handle.amount_minor);
        setPhase("awaiting_payment");

        if (!window.Razorpay) throw new Error("Payment SDK failed to load");
        const rz = new window.Razorpay({
          key: process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID,
          order_id: handle.order_id,
          amount: handle.amount_minor,
          currency: handle.currency,
          name: "TenderShield",
          handler: () => {
            if (!cancelled) pollIntent(handle.intent_id);
          },
          modal: {
            ondismiss: () => {
              if (!cancelled) setPhase("cancelled");
            },
          },
        });
        rz.open();
      } catch (e) {
        if (cancelled) return;
        const message =
          e instanceof ApiError && e.detail === "payment_provider_unavailable"
            ? "Payments aren't configured for this environment yet."
            : e instanceof Error
              ? e.message
              : "Could not start checkout.";
        setError(message);
        setPhase("failed");
      }
    }

    async function pollIntent(intentId: string) {
      setPhase("polling");
      // The webhook may land before or after the browser returns from the
      // modal. Poll with a ceiling and a clear "still processing" state —
      // never claim success from the client-side handler alone (R-008 §B3).
      for (let i = 0; i < 20; i++) {
        if (cancelled) return;
        const { status } = await billing.intent(token, intentId);
        if (status === "paid") {
          setPhase("success");
          return;
        }
        if (status === "failed" || status === "amount_mismatch") {
          setError("Payment could not be confirmed.");
          setPhase("failed");
          return;
        }
        await new Promise((r) => setTimeout(r, 1500));
      }
      if (!cancelled) {
        setError("Payment received — activation is taking longer than usual. Check back shortly.");
        setPhase("failed");
      }
    }

    run();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scriptReady]);

  useEffect(() => {
    if (phase === "success") {
      const t = setTimeout(onSuccess, 1200);
      return () => clearTimeout(t);
    }
  }, [phase, onSuccess]);

  return (
    <>
      <Script
        src="https://checkout.razorpay.com/v1/checkout.js"
        strategy="lazyOnload"
        onLoad={() => setScriptReady(true)}
        onError={() => {
          setError("Couldn't reach the payment provider. Check your connection and try again.");
          setPhase("failed");
        }}
      />
      <div role="dialog" aria-modal="true" className="fixed inset-0 z-[60] grid place-items-center bg-slate-900/50 p-4">
        <div className="w-full max-w-sm rounded-xl bg-white p-6 text-center shadow-xl">
          {phase === "creating" && <p className="text-sm text-slate-600">Preparing checkout…</p>}
          {phase === "awaiting_payment" && (
            <p className="text-sm text-slate-600">
              Complete payment{amountMinor !== null ? ` of ${formatMoney(amountMinor)}` : ""} in the Razorpay window…
            </p>
          )}
          {phase === "polling" && <p className="text-sm text-slate-600">Confirming your payment…</p>}
          {phase === "success" && <p className="text-sm font-semibold text-emerald-700">Payment confirmed.</p>}
          {phase === "cancelled" && <p className="text-sm text-slate-600">Checkout cancelled — no charge was made.</p>}
          {phase === "failed" && <p className="text-sm text-red-600">{error}</p>}

          {(phase === "cancelled" || phase === "failed" || phase === "success") && (
            <button
              onClick={onClose}
              className="mt-4 rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-ink hover:bg-slate-50"
            >
              Close
            </button>
          )}
        </div>
      </div>
    </>
  );
}
