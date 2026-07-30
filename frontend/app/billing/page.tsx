"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useSession } from "@/components/session";

export default function BillingPage() {
  const { session } = useSession();
  const [tab, setTab] = useState<"overview" | "invoices" | "payments" | "history">("overview");
  const [status, setStatus] = useState<{ plan: string; reviews_used: number; reviews_limit: number | null; seats: number } | null>(null);
  const [invoices, setInvoices] = useState<{ id: string; invoice_number: string; amount_minor: number; currency: string; status: string; paid_at: string | null; created_at: string }[]>([]);
  const [payments, setPayments] = useState<{ id: string; provider: string; event_type: string; amount_minor: number | null; currency: string | null; status: string; created_at: string }[]>([]);
  const [history, setHistory] = useState<{ id: string; old_plan: string; new_plan: string; reason: string | null; created_at: string }[]>([]);
  const [plans, setPlans] = useState<{ id: string; name: string; price_minor: number; currency: string }[]>([]);
  const [coupon, setCoupon] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    api.billingStatus(session.token).then(setStatus).catch((e) => setError(e.message));
    api.listInvoices(session.token).then((d) => setInvoices(d.invoices)).catch(() => setInvoices([]));
    api.listPayments(session.token).then((d) => setPayments(d.payments)).catch(() => setPayments([]));
    api.listPlanHistory(session.token).then((d) => setHistory(d.history)).catch(() => setHistory([]));
    api.listPlans(session.token).then((d) => setPlans(d.plans)).catch(() => setPlans([]));
  }, [session]);

  async function checkout(kind: string, plan?: string) {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const body: { provider?: string; kind: string; plan?: string; coupon_code?: string } = { kind, plan };
      if (coupon.trim()) body.coupon_code = coupon.trim();
      const res = await api.checkout(session.token, body);
      setMessage(`Checkout created (${res.provider}). ${res.note}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Checkout failed");
    } finally {
      setBusy(false);
    }
  }

  async function changePlan(planId: string) {
    if (!session) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const body: { plan: string; provider?: string; coupon_code?: string } = { plan: planId };
      if (coupon.trim()) body.coupon_code = coupon.trim();
      const res = await api.changePlan(session.token, body);
      if (res.action === "downgraded") {
        setMessage(`Plan downgraded from ${res.previous_plan || "paid"} to Free.`);
      } else {
        setMessage(`Checkout created (${res.provider || "mock"}). ${res.note || ""}`);
      }
      // refresh status/history to reflect change
      api.billingStatus(session.token).then(setStatus).catch(() => {});
      api.listPlanHistory(session.token).then((d) => setHistory(d.history)).catch(() => {});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Plan change failed");
    } finally {
      setBusy(false);
    }
  }

  if (!session) return <p className="text-sm text-slate-500">Sign in to view billing.</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink">Billing</h1>
        <Link href="/billing/settings" className="text-sm text-slate-600 hover:underline">Billing settings</Link>
      </div>

      {status && (
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <div className="grid gap-4 sm:grid-cols-4">
            <div>
              <p className="text-sm text-slate-500">Plan</p>
              <p className="font-semibold capitalize">{status.plan}</p>
            </div>
            <div>
              <p className="text-sm text-slate-500">Reviews used</p>
              <p className="font-semibold">{status.reviews_used}{status.reviews_limit ? ` / ${status.reviews_limit}` : ""}</p>
            </div>
            <div>
              <p className="text-sm text-slate-500">Seats</p>
              <p className="font-semibold">{status.seats}</p>
            </div>
            <div>
              <p className="text-sm text-slate-500">Coupon</p>
              <input
                type="text"
                value={coupon}
                onChange={(e) => setCoupon(e.target.value)}
                placeholder="Optional code"
                className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
              />
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <button onClick={() => checkout("paygo")} disabled={busy} className="rounded-md bg-ink px-3 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50">
          Pay for one review
        </button>
      </div>

      {status && plans.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-3">
          {plans.map((p) => {
            const isCurrent = status.plan === p.id;
            const isUpgrade = rankPlan(p.id) > rankPlan(status.plan);
            return (
              <div key={p.id} className={`rounded-xl border p-4 ${isCurrent ? "border-emerald-500 bg-emerald-50" : "border-slate-200 bg-white"}`}>
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold capitalize text-ink">{p.name}</h3>
                  {isCurrent && <span className="rounded-full bg-emerald-200 px-2 py-0.5 text-xs font-medium text-emerald-800">Current</span>}
                </div>
                <p className="mt-1 text-2xl font-bold text-ink">
                  {new Intl.NumberFormat("en-IN", { style: "currency", currency: p.currency }).format(p.price_minor / 100)}
                  <span className="text-sm font-normal text-slate-500">{p.id === "free" ? "" : "/mo"}</span>
                </p>
                <button
                  onClick={() => changePlan(p.id)}
                  disabled={busy || isCurrent}
                  className="mt-4 w-full rounded-md bg-ink px-3 py-1.5 text-sm text-white disabled:opacity-50"
                >
                  {isCurrent ? "Current plan" : isUpgrade ? `Upgrade to ${p.name}` : `Downgrade to ${p.name}`}
                </button>
              </div>
            );
          })}
        </div>
      )}

      {message && <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p>}
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <div className="flex gap-1 border-b border-slate-200 pb-1">
        {(["overview", "invoices", "payments", "history"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-t-md px-3 py-1.5 text-sm ${tab === t ? "bg-white font-medium text-ink" : "text-slate-500 hover:text-ink"}`}
          >
            {t === "history" ? "Plan history" : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="space-y-4">
          <p className="text-sm text-slate-500">Pick a plan above to upgrade or downgrade. Enter a coupon code before clicking to apply a discount. Payments are verified by signed webhooks before your plan is activated.</p>
          <div className="rounded-xl border border-slate-200 bg-white p-6">
            <h2 className="text-lg font-semibold text-ink">Need help?</h2>
            <p className="text-sm text-slate-500">Downgrading to Free takes effect immediately. Upgrades require a verified payment.</p>
          </div>
        </div>
      )}

      {tab === "invoices" && <InvoiceTable invoices={invoices} />}
      {tab === "payments" && <PaymentTable payments={payments} />}
      {tab === "history" && <HistoryTable history={history} />}
    </div>
  );
}

function InvoiceTable({ invoices }: { invoices: { id: string; invoice_number: string; amount_minor: number; currency: string; status: string; paid_at: string | null; created_at: string }[] }) {
  if (invoices.length === 0) return <p className="text-sm text-slate-500">No invoices yet.</p>;
  return (
    <table className="w-full text-sm">
      <thead className="border-b border-slate-200 text-left text-slate-500">
        <tr>
          <th className="py-2">Number</th>
          <th className="py-2">Amount</th>
          <th className="py-2">Status</th>
          <th className="py-2">Paid at</th>
        </tr>
      </thead>
      <tbody>
        {invoices.map((inv) => (
          <tr key={inv.id} className="border-b border-slate-100">
            <td className="py-2">{inv.invoice_number}</td>
            <td className="py-2">{formatMinor(inv.amount_minor, inv.currency)}</td>
            <td className="py-2 capitalize">{inv.status}</td>
            <td className="py-2">{inv.paid_at ? new Date(inv.paid_at).toLocaleDateString() : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function PaymentTable({ payments }: { payments: { id: string; provider: string; event_type: string; amount_minor: number | null; currency: string | null; status: string; created_at: string }[] }) {
  if (payments.length === 0) return <p className="text-sm text-slate-500">No payments recorded.</p>;
  return (
    <table className="w-full text-sm">
      <thead className="border-b border-slate-200 text-left text-slate-500">
        <tr>
          <th className="py-2">Provider</th>
          <th className="py-2">Event</th>
          <th className="py-2">Amount</th>
          <th className="py-2">Status</th>
          <th className="py-2">Date</th>
        </tr>
      </thead>
      <tbody>
        {payments.map((p) => (
          <tr key={p.id} className="border-b border-slate-100">
            <td className="py-2">{p.provider}</td>
            <td className="py-2">{p.event_type}</td>
            <td className="py-2">{p.amount_minor ? formatMinor(p.amount_minor, p.currency || "INR") : "—"}</td>
            <td className="py-2 capitalize">{p.status}</td>
            <td className="py-2">{new Date(p.created_at).toLocaleDateString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function HistoryTable({ history }: { history: { id: string; old_plan: string; new_plan: string; reason: string | null; created_at: string }[] }) {
  if (history.length === 0) return <p className="text-sm text-slate-500">No plan changes yet.</p>;
  return (
    <table className="w-full text-sm">
      <thead className="border-b border-slate-200 text-left text-slate-500">
        <tr>
          <th className="py-2">Date</th>
          <th className="py-2">From</th>
          <th className="py-2">To</th>
          <th className="py-2">Reason</th>
        </tr>
      </thead>
      <tbody>
        {history.map((h) => (
          <tr key={h.id} className="border-b border-slate-100">
            <td className="py-2">{new Date(h.created_at).toLocaleDateString()}</td>
            <td className="py-2 capitalize">{h.old_plan}</td>
            <td className="py-2 capitalize">{h.new_plan}</td>
            <td className="py-2">{h.reason || "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function rankPlan(plan: string): number {
  return { free: 0, paygo: 1, pro: 2, scale: 3 }[plan] ?? 0;
}

function formatMinor(minor: number, currency: string) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency }).format(minor / 100);
}
