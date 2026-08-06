"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";

export default function BillingSettingsPage() {
  const { session } = useSession();
  const router = useRouter();
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null);
  const [status, setStatus] = useState<{ plan: string } | null>(null);
  const [form, setForm] = useState({
    gstin: "",
    pan: "",
    billing_address: "",
    city: "",
    country: "IN",
    payment_method: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    api.billingStatus(session.token).then((s) => setStatus(s)).catch(() => setStatus(null));
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
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await api.updateBillingSettings(session.token, form);
      setSettings(updated);
      setMessage("Billing settings saved successfully.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save billing settings");
    } finally {
      setLoading(false);
    }
  };

  const cancel = async () => {
    if (!session || !confirm("Cancel subscription? Your account will move to the free plan.")) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const r = await api.cancelSubscription(session.token);
      setMessage(`Subscription cancelled; reverted to ${r.plan}.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to cancel subscription");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-heading-lg text-text-primary">Billing Settings</h1>
        <p className="text-sm text-text-muted mt-2">Manage your billing information and subscription</p>
      </div>

      {/* Alerts */}
      {error && <Alert variant="error" title="Error">{error}</Alert>}
      {message && <Alert variant="success" title="Success">{message}</Alert>}

      {/* Current Plan */}
      <Card>
        <CardHeader>
          <CardTitle>Current Plan</CardTitle>
          <CardDescription>Your active subscription</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <span className="text-sm text-text-muted">Plan:</span>
            <Badge variant={status?.plan === "free" ? "secondary" : "success"}>
              {status?.plan ? status.plan.charAt(0).toUpperCase() + status.plan.slice(1) : "Free"}
            </Badge>
          </div>
        </CardContent>
      </Card>

      {/* Billing Information */}
      <Card>
        <CardHeader>
          <CardTitle>Billing Information</CardTitle>
          <CardDescription>Update your tax and payment details</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={save} className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label htmlFor="billing-gstin" className="block text-sm font-medium text-text-primary mb-2">GSTIN</label>
                <input
                  id="billing-gstin"
                  type="text"
                  placeholder="Enter GSTIN"
                  value={form.gstin}
                  onChange={(e) => setForm({ ...form, gstin: e.target.value })}
                  disabled={loading}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                />
              </div>
              <div>
                <label htmlFor="billing-pan" className="block text-sm font-medium text-text-primary mb-2">PAN</label>
                <input
                  id="billing-pan"
                  type="text"
                  placeholder="Enter PAN"
                  value={form.pan}
                  onChange={(e) => setForm({ ...form, pan: e.target.value })}
                  disabled={loading}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                />
              </div>
              <div className="md:col-span-2">
                <label htmlFor="billing-address" className="block text-sm font-medium text-text-primary mb-2">Billing Address</label>
                <input
                  id="billing-address"
                  type="text"
                  placeholder="Enter billing address"
                  value={form.billing_address}
                  onChange={(e) => setForm({ ...form, billing_address: e.target.value })}
                  disabled={loading}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                />
              </div>
              <div>
                <label htmlFor="billing-city" className="block text-sm font-medium text-text-primary mb-2">City</label>
                <input
                  id="billing-city"
                  type="text"
                  placeholder="Enter city"
                  value={form.city}
                  onChange={(e) => setForm({ ...form, city: e.target.value })}
                  disabled={loading}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                />
              </div>
              <div>
                <label htmlFor="billing-country" className="block text-sm font-medium text-text-primary mb-2">Country</label>
                <input
                  id="billing-country"
                  type="text"
                  placeholder="Enter country"
                  value={form.country}
                  onChange={(e) => setForm({ ...form, country: e.target.value })}
                  disabled={loading}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                />
              </div>
              <div>
                <label htmlFor="billing-payment-method" className="block text-sm font-medium text-text-primary mb-2">Payment Method Token</label>
                <input
                  id="billing-payment-method"
                  type="text"
                  placeholder="Enter payment method token"
                  value={form.payment_method}
                  onChange={(e) => setForm({ ...form, payment_method: e.target.value })}
                  disabled={loading}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                />
              </div>
            </div>
            <Button variant="primary" size="md" type="submit" disabled={loading}>
              {loading ? "Saving..." : "Save Billing Details"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Danger Zone */}
      <Card>
        <CardHeader>
          <CardTitle className="text-error">Danger Zone</CardTitle>
          <CardDescription>Irreversible actions</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between p-4 rounded-lg border border-error bg-error/5">
            <div>
              <p className="text-sm font-medium text-text-primary">Cancel Subscription</p>
              <p className="text-xs text-text-muted mt-1">Your account will revert to the free plan</p>
            </div>
            <Button variant="destructive" size="sm" onClick={cancel} disabled={loading}>
              {loading ? "Processing..." : "Cancel Subscription"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
