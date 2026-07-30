"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useSession } from "@/components/session";

export default function AdminCouponsPage() {
  const { session } = useSession();
  const [coupons, setCoupons] = useState<{ id: string; code: string; discount_type: string; discount_value: number; currency: string | null; max_uses: number | null; uses_count: number; valid_from: string | null; valid_until: string | null; active: boolean; created_at: string }[]>([]);
  const [form, setForm] = useState({ code: "", discount_type: "percent", discount_value: "", currency: "INR", max_uses: "", valid_from: "", valid_until: "" });
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!session) return;
    try {
      const d = await api.listCoupons(session.token);
      setCoupons(d.coupons);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load coupons");
    }
  }, [session]);

  useEffect(() => {
    load();
  }, [load]);

  async function createCoupon(e: React.FormEvent) {
    e.preventDefault();
    if (!session) return;
    setError(null);
    try {
      const body = {
        code: form.code,
        discount_type: form.discount_type,
        discount_value: parseInt(form.discount_value, 10),
        currency: form.currency,
        max_uses: form.max_uses ? parseInt(form.max_uses, 10) : null,
        valid_from: form.valid_from || null,
        valid_until: form.valid_until || null,
      };
      await api.createCoupon(session.token, body);
      setMessage(`Coupon ${form.code} created.`);
      setForm({ code: "", discount_type: "percent", discount_value: "", currency: "INR", max_uses: "", valid_from: "", valid_until: "" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  }

  async function deleteCoupon(code: string) {
    if (!session) return;
    try {
      await api.deleteCoupon(session.token, code);
      setMessage(`Coupon ${code} disabled.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  if (!session) return <p className="text-sm text-slate-500">Sign in as super-admin.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-ink">Coupon codes</h1>

      <form onSubmit={createCoupon} className="rounded-xl border border-slate-200 bg-white p-6 space-y-3">
        <h2 className="text-lg font-semibold text-ink">Create coupon</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <input required placeholder="Code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
          <select value={form.discount_type} onChange={(e) => setForm({ ...form, discount_type: e.target.value })} className="rounded-md border border-slate-300 px-3 py-2 text-sm">
            <option value="percent">Percent (%)</option>
            <option value="fixed">Fixed amount (paise)</option>
          </select>
          <input required type="number" placeholder={form.discount_type === "percent" ? "Percent (e.g. 15)" : "Amount in paise"} value={form.discount_value} onChange={(e) => setForm({ ...form, discount_value: e.target.value })} className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
          <input placeholder="Currency (INR)" value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
          <input type="number" placeholder="Max uses (optional)" value={form.max_uses} onChange={(e) => setForm({ ...form, max_uses: e.target.value })} className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
          <input type="datetime-local" value={form.valid_from} onChange={(e) => setForm({ ...form, valid_from: e.target.value })} className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
          <input type="datetime-local" value={form.valid_until} onChange={(e) => setForm({ ...form, valid_until: e.target.value })} className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
        </div>
        <button type="submit" className="rounded-md bg-ink px-3 py-1.5 text-sm text-white">Create</button>
      </form>

      {message && <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p>}
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <table className="w-full text-sm">
        <thead className="border-b border-slate-200 text-left text-slate-500">
          <tr>
            <th className="py-2">Code</th>
            <th className="py-2">Type</th>
            <th className="py-2">Value</th>
            <th className="py-2">Uses</th>
            <th className="py-2">Valid until</th>
            <th className="py-2">Active</th>
            <th className="py-2"></th>
          </tr>
        </thead>
        <tbody>
          {coupons.map((c) => (
            <tr key={c.id} className="border-b border-slate-100">
              <td className="py-2 font-medium">{c.code}</td>
              <td className="py-2">{c.discount_type}</td>
              <td className="py-2">{c.discount_value}</td>
              <td className="py-2">{c.uses_count}{c.max_uses ? ` / ${c.max_uses}` : ""}</td>
              <td className="py-2">{c.valid_until ? new Date(c.valid_until).toLocaleDateString() : "—"}</td>
              <td className="py-2">{c.active ? "Yes" : "No"}</td>
              <td className="py-2">
                {c.active && (
                  <button onClick={() => deleteCoupon(c.code)} className="text-red-600 hover:underline text-xs">Disable</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
