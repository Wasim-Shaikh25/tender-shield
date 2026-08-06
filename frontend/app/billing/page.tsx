"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { cn } from "@/lib/utils";

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

  if (!session) return <p className="text-sm text-text-muted">Sign in to view billing.</p>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-heading-lg text-text-primary">Billing</h1>
          <p className="text-sm text-text-muted mt-1">Manage your subscription and payments</p>
        </div>
        <Link href="/billing/settings">
          <Button variant="secondary" size="md">
            Billing Settings
          </Button>
        </Link>
      </div>

      {/* Billing Status */}
      {status && (
        <Card>
          <CardHeader>
            <CardTitle>Current Status</CardTitle>
            <CardDescription>Your plan and usage overview</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-4">
              <div>
                <p className="text-sm text-text-muted mb-1">Plan</p>
                <p className="text-base font-semibold text-text-primary capitalize">{status.plan}</p>
              </div>
              <div>
                <p className="text-sm text-text-muted mb-1">Reviews Used</p>
                <p className="text-base font-semibold text-text-primary">
                  {status.reviews_used}{status.reviews_limit ? ` / ${status.reviews_limit}` : " (unlimited)"}
                </p>
              </div>
              <div>
                <p className="text-sm text-text-muted mb-1">Seats</p>
                <p className="text-base font-semibold text-text-primary">{status.seats}</p>
              </div>
              <div>
                <label htmlFor="coupon-code" className="text-sm text-text-muted mb-2 block">Coupon Code</label>
                <input
                  id="coupon-code"
                  type="text"
                  value={coupon}
                  onChange={(e) => setCoupon(e.target.value)}
                  placeholder="Optional code"
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          size="md"
          onClick={() => checkout("paygo")}
          disabled={busy}
        >
          Pay for One Review
        </Button>
      </div>

      {/* Plans */}
      {status && plans.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-text-primary mb-4">Available Plans</h2>
          <div className="grid gap-4 sm:grid-cols-3">
            {plans.map((p) => {
              const isCurrent = status.plan === p.id;
              const isUpgrade = rankPlan(p.id) > rankPlan(status.plan);
              return (
                <Card
                  key={p.id}
                  className={cn(
                    isCurrent && "border-success bg-success-bg"
                  )}
                >
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <CardTitle className="capitalize">{p.name}</CardTitle>
                      {isCurrent && (
                        <Badge variant="success" size="sm">
                          Current
                        </Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <p className="text-3xl font-bold text-text-primary">
                        {new Intl.NumberFormat("en-IN", { style: "currency", currency: p.currency }).format(p.price_minor / 100)}
                      </p>
                      {p.id !== "free" && (
                        <p className="text-sm text-text-muted mt-1">per month</p>
                      )}
                    </div>
                    <Button
                      variant={isCurrent ? "secondary" : isUpgrade ? "primary" : "outline"}
                      size="md"
                      className="w-full"
                      onClick={() => changePlan(p.id)}
                      disabled={busy || isCurrent}
                    >
                      {isCurrent ? "Current Plan" : isUpgrade ? `Upgrade to ${p.name}` : `Downgrade to ${p.name}`}
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* Messages */}
      {message && (
        <Alert variant="success" title="Success">
          {message}
        </Alert>
      )}
      {error && (
        <Alert variant="error" title="Error">
          {error}
        </Alert>
      )}

      {/* Tab Navigation */}
      <div className="flex gap-1 border-b border-border-default overflow-x-auto">
        {(["overview", "invoices", "payments", "history"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors duration-base",
              tab === t
                ? "border-b-2 border-ink text-text-primary"
                : "text-text-secondary hover:text-text-primary"
            )}
          >
            {t === "history" ? "Plan History" : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="space-y-4">
          <Alert variant="info" title="Upgrade or Downgrade">
            Pick a plan above to change your subscription. Enter a coupon code to apply a discount. Payments are verified by webhook before activation.
          </Alert>
          <Card>
            <CardHeader>
              <CardTitle>Important Information</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm text-text-secondary">
                <li>- Downgrading to Free takes effect immediately</li>
                <li>- Upgrades require a verified payment</li>
                <li>- Payments are processed securely</li>
              </ul>
            </CardContent>
          </Card>
        </div>
      )}

      {tab === "invoices" && <InvoiceTable invoices={invoices} />}
      {tab === "payments" && <PaymentTable payments={payments} />}
      {tab === "history" && <HistoryTable history={history} />}
    </div>
  );
}

function InvoiceTable({ invoices }: { invoices: { id: string; invoice_number: string; amount_minor: number; currency: string; status: string; paid_at: string | null; created_at: string }[] }) {
  if (invoices.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <p className="text-text-secondary">No invoices yet.</p>
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardContent className="pt-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-border-default text-left text-text-secondary bg-bg-secondary">
              <tr>
                <th className="px-4 py-3 font-medium">Number</th>
                <th className="px-4 py-3 font-medium">Amount</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Paid At</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id} className="border-b border-border-default hover:bg-bg-secondary transition-colors">
                  <td className="px-4 py-3 text-text-primary font-medium">{inv.invoice_number}</td>
                  <td className="px-4 py-3 text-text-primary">{formatMinor(inv.amount_minor, inv.currency)}</td>
                  <td className="px-4 py-3">
                    <Badge variant={inv.status === "paid" ? "success" : inv.status === "pending" ? "warning" : "secondary"} size="sm">
                      {inv.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-text-secondary">
                    {inv.paid_at ? new Date(inv.paid_at).toLocaleDateString("en-IN") : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function PaymentTable({ payments }: { payments: { id: string; provider: string; event_type: string; amount_minor: number | null; currency: string | null; status: string; created_at: string }[] }) {
  if (payments.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <p className="text-text-secondary">No payments recorded.</p>
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardContent className="pt-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-border-default text-left text-text-secondary bg-bg-secondary">
              <tr>
                <th className="px-4 py-3 font-medium">Provider</th>
                <th className="px-4 py-3 font-medium">Event</th>
                <th className="px-4 py-3 font-medium">Amount</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Date</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p) => (
                <tr key={p.id} className="border-b border-border-default hover:bg-bg-secondary transition-colors">
                  <td className="px-4 py-3 text-text-primary font-medium capitalize">{p.provider}</td>
                  <td className="px-4 py-3 text-text-primary">{p.event_type}</td>
                  <td className="px-4 py-3 text-text-primary">
                    {p.amount_minor ? formatMinor(p.amount_minor, p.currency || "INR") : "-"}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={p.status === "success" ? "success" : p.status === "pending" ? "warning" : "secondary"} size="sm">
                      {p.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-text-secondary">{new Date(p.created_at).toLocaleDateString("en-IN")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function HistoryTable({ history }: { history: { id: string; old_plan: string; new_plan: string; reason: string | null; created_at: string }[] }) {
  if (history.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <p className="text-text-secondary">No plan changes yet.</p>
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardContent className="pt-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-border-default text-left text-text-secondary bg-bg-secondary">
              <tr>
                <th className="px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3 font-medium">From</th>
                <th className="px-4 py-3 font-medium">To</th>
                <th className="px-4 py-3 font-medium">Reason</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.id} className="border-b border-border-default hover:bg-bg-secondary transition-colors">
                  <td className="px-4 py-3 text-text-secondary">{new Date(h.created_at).toLocaleDateString("en-IN")}</td>
                  <td className="px-4 py-3">
                    <Badge variant="secondary" size="sm">
                      {h.old_plan}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant="primary" size="sm">
                      {h.new_plan}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-text-secondary">{h.reason || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function rankPlan(plan: string): number {
  return { free: 0, paygo: 1, pro: 2, scale: 3 }[plan] ?? 0;
}

function formatMinor(minor: number, currency: string) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency }).format(minor / 100);
}
