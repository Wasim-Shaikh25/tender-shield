"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";

export default function AdminCouponsPage() {
  const { session } = useSession();
  const [coupons, setCoupons] = useState<{ id: string; code: string; discount_type: string; discount_value: number; currency: string | null; max_uses: number | null; uses_count: number; valid_from: string | null; valid_until: string | null; active: boolean; created_at: string }[]>([]);
  const [form, setForm] = useState({ code: "", discount_type: "percent", discount_value: "", currency: "INR", max_uses: "", valid_from: "", valid_until: "" });
  const [loading, setLoading] = useState(false);
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
    setLoading(true);
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
      setMessage(`Coupon ${form.code} created successfully.`);
      setForm({ code: "", discount_type: "percent", discount_value: "", currency: "INR", max_uses: "", valid_from: "", valid_until: "" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create coupon");
    } finally {
      setLoading(false);
    }
  }

  async function deleteCoupon(code: string) {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      await api.deleteCoupon(session.token, code);
      setMessage(`Coupon ${code} disabled.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to disable coupon");
    } finally {
      setLoading(false);
    }
  }

  if (!session) return <Alert variant="info" title="Authentication Required">Sign in as superadmin to manage coupons.</Alert>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-heading-lg text-text-primary">Coupon Management</h1>
        <p className="text-sm text-text-muted mt-2">Create and manage discount coupons</p>
      </div>

      {/* Alerts */}
      {error && <Alert variant="error" title="Error">{error}</Alert>}
      {message && <Alert variant="success" title="Success">{message}</Alert>}

      {/* Create Coupon Form */}
      <Card>
        <CardHeader>
          <CardTitle>Create Coupon</CardTitle>
          <CardDescription>Create a new discount code</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={createCoupon} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="code" className="block text-sm font-medium text-text-primary mb-2">Code <span className="text-error">*</span></label>
                <input
                  id="code"
                  required
                  placeholder="e.g., SAVE15"
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  disabled={loading}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                />
              </div>
              <div>
                <label htmlFor="type" className="block text-sm font-medium text-text-primary mb-2">Discount Type</label>
                <select
                  id="type"
                  value={form.discount_type}
                  onChange={(e) => setForm({ ...form, discount_type: e.target.value })}
                  disabled={loading}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                >
                  <option value="percent">Percentage (%)</option>
                  <option value="fixed">Fixed Amount (paise)</option>
                </select>
              </div>
              <div>
                <label htmlFor="value" className="block text-sm font-medium text-text-primary mb-2">
                  Value <span className="text-error">*</span> {form.discount_type === "percent" && <span className="text-text-muted">(e.g., 15)</span>}
                </label>
                <input
                  id="value"
                  required
                  type="number"
                  value={form.discount_value}
                  onChange={(e) => setForm({ ...form, discount_value: e.target.value })}
                  disabled={loading}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                />
              </div>
              <div>
                <label htmlFor="currency" className="block text-sm font-medium text-text-primary mb-2">Currency</label>
                <input
                  id="currency"
                  placeholder="INR"
                  value={form.currency}
                  onChange={(e) => setForm({ ...form, currency: e.target.value })}
                  disabled={loading}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                />
              </div>
              <div>
                <label htmlFor="maxuses" className="block text-sm font-medium text-text-primary mb-2">Max Uses (optional)</label>
                <input
                  id="maxuses"
                  type="number"
                  value={form.max_uses}
                  onChange={(e) => setForm({ ...form, max_uses: e.target.value })}
                  disabled={loading}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                />
              </div>
              <div>
                <label htmlFor="from" className="block text-sm font-medium text-text-primary mb-2">Valid From</label>
                <input
                  id="from"
                  type="datetime-local"
                  value={form.valid_from}
                  onChange={(e) => setForm({ ...form, valid_from: e.target.value })}
                  disabled={loading}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                />
              </div>
              <div>
                <label htmlFor="until" className="block text-sm font-medium text-text-primary mb-2">Valid Until</label>
                <input
                  id="until"
                  type="datetime-local"
                  value={form.valid_until}
                  onChange={(e) => setForm({ ...form, valid_until: e.target.value })}
                  disabled={loading}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                />
              </div>
            </div>
            <Button variant="primary" size="md" type="submit" disabled={loading}>
              {loading ? "Creating..." : "Create Coupon"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Coupons List */}
      <Card>
        <CardHeader>
          <CardTitle>Active Coupons</CardTitle>
          <CardDescription>{coupons.length} coupon{coupons.length !== 1 ? "s" : ""}</CardDescription>
        </CardHeader>
        <CardContent>
          {coupons.length === 0 ? (
            <p className="text-sm text-text-muted py-4">No coupons yet.</p>
          ) : (
            <div className="space-y-3">
              {coupons.map((c) => (
                <div key={c.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-lg border border-border-default hover:bg-bg-secondary transition-colors">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-text-primary">{c.code}</p>
                      {!c.active && <Badge variant="secondary" size="sm">Disabled</Badge>}
                    </div>
                    <div className="flex items-center gap-3 mt-2 flex-wrap">
                      <Badge variant="info" size="sm">
                        {c.discount_type === "percent" ? `${c.discount_value}%` : `₹${(c.discount_value / 100).toFixed(2)}`}
                      </Badge>
                      <span className="text-sm text-text-muted">
                        {c.uses_count} use{c.uses_count !== 1 ? "s" : ""}{c.max_uses ? ` / ${c.max_uses}` : ""}
                      </span>
                      {c.valid_until && (
                        <span className="text-sm text-text-muted">
                          Valid until {new Date(c.valid_until).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>
                  {c.active && (
                    <Button variant="destructive" size="sm" onClick={() => deleteCoupon(c.code)} disabled={loading}>
                      {loading ? "Processing..." : "Disable"}
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
