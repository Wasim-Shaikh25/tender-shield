"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useSession } from "@/components/session";

export default function BillingSettingsPage() {
  const { session, activeWorkspace } = useSession();
  const router = useRouter();
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null);
  const [form, setForm] = useState({
    gstin: "",
    pan: "",
    billing_address: "",
    city: "",
    country: "IN",
    payment_method: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    api.getBillingSettings(session.token)
      .then((s) => {
        setSettings(s);
        setForm({
          gstin: String(s.gstin ?? ""),
          pan: String(s.pan ?? ""),
          billing_address: String(s.billing_address ?? ""),
          city: String(s.city ?? ""),
          country: String(s.country ?? "IN"),
          payment_method: String(s.payment_method ?? ""),
        });
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load billing settings"));
  }, [session]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session) return;
    setError(null);
    setMessage(null);
    try {
      const updated = await api.updateBillingSettings(session.token, form);
      setSettings(updated);
      setMessage("Billing settings saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    }
  };

  const cancel = async () => {
    if (!session || !confirm("Cancel subscription? The workspace will move to the free plan.")) return;
    try {
      const r = await api.cancelSubscription(session.token);
      setMessage(`Subscription cancelled; reverted to ${r.plan}.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Cancel failed");
    }
  };

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold text-ink">Billing settings</h1>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {message && <p className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">{message}</p>}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <p className="mb-4 text-sm text-slate-500">Workspace: {activeWorkspace?.name ?? "—"} (plan: {String(settings?.plan ?? "free")})</p>
        <form onSubmit={save} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="billing-gstin" className="mb-1 block text-sm font-medium text-slate-700">GSTIN</label>
              <input id="billing-gstin" value={form.gstin} onChange={(e) => setForm({ ...form, gstin: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
            </div>
            <div>
              <label htmlFor="billing-pan" className="mb-1 block text-sm font-medium text-slate-700">PAN</label>
              <input id="billing-pan" value={form.pan} onChange={(e) => setForm({ ...form, pan: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="billing-address" className="mb-1 block text-sm font-medium text-slate-700">Billing address</label>
              <input id="billing-address" value={form.billing_address} onChange={(e) => setForm({ ...form, billing_address: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
            </div>
            <div>
              <label htmlFor="billing-city" className="mb-1 block text-sm font-medium text-slate-700">City</label>
              <input id="billing-city" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
            </div>
            <div>
              <label htmlFor="billing-country" className="mb-1 block text-sm font-medium text-slate-700">Country</label>
              <input id="billing-country" value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
            </div>
            <div>
              <label htmlFor="billing-payment-method" className="mb-1 block text-sm font-medium text-slate-700">Payment method token</label>
              <input id="billing-payment-method" value={form.payment_method} onChange={(e) => setForm({ ...form, payment_method: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
            </div>
          </div>
          <button type="submit" className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white">Save billing details</button>
        </form>
      </section>

      <section className="rounded-xl border border-red-200 bg-white p-6">
        <h2 className="mb-2 text-lg font-semibold text-red-700">Danger zone</h2>
        <button onClick={cancel} className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white">Cancel subscription</button>
      </section>
    </div>
  );
}
