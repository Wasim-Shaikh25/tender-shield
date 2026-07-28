"use client";

// Account billing home (R-008 §3, TS-091; entitlement fields wired to real
// data in R-009/TS-098). Current plan, reviews/seats usage, invoice history,
// and a plan-change entry point. Credit/referral sections from the R-008
// draft still need R-006/TS-090's coupon endpoints, which don't exist yet.

import { useEffect, useState } from "react";
import Link from "next/link";
import { billing, type BillingStatus, type Invoice, type Plan } from "@/lib/api";
import { useSession } from "@/components/session";
import { RequireAuth } from "@/components/require-auth";
import { formatMoney } from "@/lib/money";

const PLAN_LABEL: Record<Plan, string> = {
  free: "Free",
  paygo: "Pay as you go",
  pro: "Pro",
  scale: "Scale",
};

const STATUS_TONE: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  trialing: "bg-sky-100 text-sky-700",
  past_due: "bg-amber-100 text-amber-800",
  cancelled: "bg-slate-200 text-slate-600",
};

export default function BillingPage() {
  return (
    <RequireAuth>
      <BillingPageInner />
    </RequireAuth>
  );
}

function BillingPageInner() {
  const { session } = useSession();
  const [status, setStatus] = useState<BillingStatus | null>(null);
  const [invoices, setInvoices] = useState<Invoice[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isAdmin = session?.role === "admin" || session?.role === "owner";

  async function load() {
    if (!session) return;
    setError(null);
    try {
      const s = await billing.status(session.token);
      setStatus(s);
      if (isAdmin) {
        const { invoices } = await billing.invoices(session.token);
        setInvoices(invoices);
      }
    } catch {
      setError("Couldn't reach the billing service. Retry in a moment.");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  if (!session) {
    return <p className="text-sm text-slate-500">Sign in to view billing.</p>;
  }

  if (error) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
        <p className="text-sm text-slate-500">{error}</p>
        <button
          onClick={load}
          className="mt-3 rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-ink hover:bg-slate-50"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!status) return <p className="text-sm text-slate-500">Loading…</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">Billing</h1>
        <p className="text-sm text-slate-500">Plan, usage and invoices for this workspace.</p>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Current plan</p>
            <p className="mt-1 text-xl font-bold text-ink">{PLAN_LABEL[status.plan]}</p>
          </div>
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_TONE[status.plan_status] ?? "bg-slate-100 text-slate-600"}`}>
            {status.plan_status.replace("_", " ")}
          </span>
        </div>

        {status.plan_status === "past_due" && status.grace_until && (
          <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Payment failed — access continues until {new Date(status.grace_until).toLocaleDateString()}.
            Update your payment method to avoid downgrade.
          </p>
        )}

        <div className="mt-4 space-y-3">
          {status.plan === "free" && (
            <Row label="Free review" value={status.free_review_used ? "used" : "available"} />
          )}
          {status.plan === "paygo" && (
            <Row label="Reviews" value="pay per tender — no monthly cap" />
          )}
          {status.reviews_included !== null && (
            <UsageMeter
              label="Reviews this period"
              used={status.reviews_this_month}
              included={status.reviews_included + status.reviews_topup}
            />
          )}
          {status.seats_included !== null && status.seats_used !== null && (
            <UsageMeter label="Seats" used={status.seats_used} included={status.seats_included} />
          )}
        </div>

        {isAdmin ? (
          <div className="mt-5 flex flex-wrap gap-2">
            <Link
              href="/pricing"
              className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              {status.plan === "free" ? "Upgrade" : "Change plan"}
            </Link>
          </div>
        ) : (
          <p className="mt-5 text-xs text-slate-400">
            Ask your workspace admin to change plans or view invoices.
          </p>
        )}
      </section>

      {isAdmin && (
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="font-semibold text-ink">Invoices</h2>
          {invoices === null ? (
            <p className="mt-2 text-sm text-slate-500">Loading…</p>
          ) : invoices.length === 0 ? (
            <p className="mt-2 text-sm text-slate-500">No invoices yet.</p>
          ) : (
            <table className="mt-3 w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
                  <th className="pb-2 font-medium">Invoice</th>
                  <th className="pb-2 font-medium">Date</th>
                  <th className="pb-2 font-medium">Amount</th>
                  <th className="pb-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {invoices.map((inv) => (
                  <tr key={inv.id}>
                    <td className="py-2 font-mono text-xs text-slate-600">{inv.invoice_number}</td>
                    <td className="py-2 text-slate-600">
                      {new Date(inv.paid_at ?? inv.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-2 text-slate-800">{formatMoney(inv.amount_minor, inv.currency)}</td>
                    <td className="py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          inv.status === "paid" ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {inv.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-ink">{value}</span>
    </div>
  );
}

function UsageMeter({ label, used, included }: { label: string; used: number; included: number }) {
  const pct = Math.min(100, Math.round((used / included) * 100));
  const tone = pct >= 100 ? "bg-red-500" : pct >= 80 ? "bg-amber-500" : "bg-ink";
  return (
    <div>
      <div className="flex justify-between text-sm">
        <span className="text-slate-500">{label}</span>
        <span className="font-medium text-ink">
          {used} / {included}
        </span>
      </div>
      <div
        className="mt-1 h-2 rounded bg-slate-100"
        role="progressbar"
        aria-valuenow={used}
        aria-valuemin={0}
        aria-valuemax={included}
        aria-label={label}
      >
        <div className={`h-2 rounded ${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
