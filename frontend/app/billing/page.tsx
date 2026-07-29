"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useSession } from "@/components/session";

export default function BillingPage() {
  const { session } = useSession();
  const [status, setStatus] = useState<{ plan: string; reviews_used: number; reviews_limit: number | null; seats: number } | null>(null);
  const [invoices, setInvoices] = useState<{ id: string; invoice_number: string; amount_minor: number; currency: string; status: string; paid_at: string | null; created_at: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    api.billingStatus(session.token).then(setStatus).catch((e) => setError(e.message));
    api.listInvoices(session.token).then((d) => setInvoices(d.invoices)).catch(() => setInvoices([]));
  }, [session]);

  async function checkout(kind: string, plan?: string) {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.checkout(session.token, { kind, plan });
      setMessage(`Checkout created (${res.provider}). ${res.note}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Checkout failed");
    } finally {
      setBusy(false);
    }
  }

  if (!session) return <p className="text-sm text-slate-500">Sign in to view billing.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-ink">Billing</h1>
      {status && (
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <div className="flex items-center justify-between">
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
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <button onClick={() => checkout("paygo")} disabled={busy} className="rounded-md bg-ink px-3 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50">
          Pay for one review
        </button>
        <button onClick={() => checkout("subscription", "pro")} disabled={busy} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-white disabled:opacity-50">
          Subscribe to Pro
        </button>
        <button onClick={() => checkout("subscription", "scale")} disabled={busy} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-white disabled:opacity-50">
          Subscribe to Scale
        </button>
      </div>

      {message && <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p>}
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <h2 className="text-lg font-semibold text-ink">Invoices</h2>
      {invoices.length === 0 ? (
        <p className="text-sm text-slate-500">No invoices yet.</p>
      ) : (
        <table className="w-full text-sm">
          <thead className="border-b border-slate-200 text-left text-slate-500">
            <tr>
              <th className="py-2">Number</th>
              <th className="py-2">Amount</th>
              <th className="py-2">Status</th>
              <th className="py-2">Provider</th>
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
      )}
    </div>
  );
}

function formatMinor(minor: number, currency: string) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency }).format(minor / 100);
}
