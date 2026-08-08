"use client";

import { useEffect, useState } from "react";
import { api, type Opportunity } from "@/lib/api";
import { useSession } from "@/components/session";

function rupees(minor?: number | null, currency?: string | null) {
  if (minor === undefined || minor === null || Number.isNaN(minor)) return "—";
  const code = currency || "INR";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: code, maximumFractionDigits: 0 }).format(minor / 100);
}

function percent(value?: number | null) {
  if (value === undefined || value === null) return "—";
  return `${Math.round(value)}%`;
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString();
}

function isUnavailable(data: Record<string, unknown> | null) {
  return data?.unavailable === true;
}

function MetricCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs text-slate-500 uppercase">{label}</p>
      <p className="mt-1 text-xl font-semibold text-ink">{value}</p>
    </div>
  );
}

export default function ControlTowerPage() {
  const { session } = useSession();
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const [exposure, setExposure] = useState<Record<string, unknown> | null>(null);
  const [dashboard, setDashboard] = useState<Record<string, unknown> | null>(null);
  const [executive, setExecutive] = useState<Record<string, unknown> | null>(null);
  const [responseTimes, setResponseTimes] = useState<Record<string, unknown> | null>(null);
  const [paymentSchedule, setPaymentSchedule] = useState<Record<string, unknown> | null>(null);

  const [portfolio, setPortfolio] = useState<Record<string, unknown> | null>(null);
  const [clauseTrends, setClauseTrends] = useState<Record<string, unknown> | null>(null);
  const [recurringOmissions, setRecurringOmissions] = useState<Record<string, unknown> | null>(null);
  const [economics, setEconomics] = useState<Record<string, unknown> | null>(null);
  const [outcomes, setOutcomes] = useState<Record<string, unknown> | null>(null);

  const [forecast, setForecast] = useState<Record<string, unknown> | null>(null);
  const [forecastForm, setForecastForm] = useState({ projected_final_cost_minor: "", contingency_percent: "5", cost_of_capital_pa: "0.12", currency: "INR" });
  const [paymentForm, setPaymentForm] = useState({ kind: "progress", due_date: "", amount_minor: "", certified_amount_minor: "", currency: "INR", status: "pending", description: "" });

  useEffect(() => {
    if (!session) return;
    api.listOpportunities(session.token).then((d) => {
      setOpportunities(d.opportunities);
      if (d.opportunities.length > 0) setSelected(d.opportunities[0].id);
    }).catch(() => {});
    api.getPortfolio(session.token).then(setPortfolio).catch(() => {});
    api.getClauseTrends(session.token).then(setClauseTrends).catch(() => {});
    api.getRecurringOmissions(session.token).then(setRecurringOmissions).catch(() => {});
    api.getEconomics(session.token).then(setEconomics).catch(() => {});
    api.getCustomerOutcomes(session.token).then(setOutcomes).catch(() => {});
  }, [session]);

  useEffect(() => {
    if (!session || !selected) return;
    setLoading(true);
    setError(null);
    Promise.all([
      api.getExposure(session.token, selected).then(setExposure).catch(() => setExposure(null)),
      api.getControlDashboard(session.token, selected).then(setDashboard).catch(() => setDashboard(null)),
      api.getExecutiveSummary(session.token, selected).then(setExecutive).catch(() => setExecutive(null)),
      api.getResponseTimes(session.token, selected).then(setResponseTimes).catch(() => setResponseTimes(null)),
      api.getPaymentSchedule(session.token, selected).then(setPaymentSchedule).catch(() => setPaymentSchedule(null)),
      api.getRecurringOmissions(session.token, selected).then(setRecurringOmissions).catch(() => setRecurringOmissions(null)),
    ]).finally(() => setLoading(false));
  }, [session, selected]);

  async function runForecast(e: React.FormEvent) {
    e.preventDefault();
    if (!session || !selected) return;
    setLoading(true);
    setError(null);
    try {
      const f = await api.postForecast(session.token, {
        opportunity_id: selected,
        projected_final_cost_minor: parseInt(forecastForm.projected_final_cost_minor, 10),
        contingency_percent: parseFloat(forecastForm.contingency_percent || "0"),
        cost_of_capital_pa: parseFloat(forecastForm.cost_of_capital_pa || "0.12"),
        currency: forecastForm.currency,
      });
      setForecast(f as Record<string, unknown>);
      setNote("Forecast updated");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Forecast failed");
    } finally {
      setLoading(false);
    }
  }

  async function addPaymentEvent(e: React.FormEvent) {
    e.preventDefault();
    if (!session || !selected || !paymentForm.due_date || !paymentForm.amount_minor) return;
    setLoading(true);
    try {
      await api.recordPaymentEvent(session.token, {
        opportunity_id: selected,
        kind: paymentForm.kind,
        due_date: paymentForm.due_date,
        amount_minor: parseInt(paymentForm.amount_minor, 10),
        certified_amount_minor: paymentForm.certified_amount_minor ? parseInt(paymentForm.certified_amount_minor, 10) : undefined,
        currency: paymentForm.currency,
        status: paymentForm.status,
        description: paymentForm.description || undefined,
      });
      setPaymentForm({ kind: "progress", due_date: "", amount_minor: "", certified_amount_minor: "", currency: "INR", status: "pending", description: "" });
      const d = await api.getPaymentSchedule(session.token, selected);
      setPaymentSchedule(d);
      setNote("Payment event recorded");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Payment event failed");
    } finally {
      setLoading(false);
    }
  }

  if (!session) {
    return null;
  }

  const dashboardData = dashboard || {};
  const deadlines = (dashboardData.deadlines_dashboard as Record<string, string[]>) || {};
  const health = (dashboardData.evidence_health as { score?: number; reasons?: string[] }) || { score: undefined, reasons: [] };
  const topRisks = (executive?.top_risks as Record<string, unknown>[]) || [];
  const schedule = (paymentSchedule?.schedule as Record<string, unknown>[]) || [];
  const responseStats = (responseTimes?.response_stats as Record<string, unknown>[]) || [];
  const overall = (responseTimes?.overall as Record<string, number>) || {};

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Control Tower</h1>
        <p className="text-sm text-slate-600">Commercial command centre: exposure, forecasts, response times, and payment control.</p>
      </div>

      {note && <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{note}</p>}
      {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      {loading && <p className="text-sm text-slate-500">Loading…</p>}

      <div className="flex items-center gap-3">
        <label htmlFor="opp-select" className="text-sm font-medium text-slate-700">Opportunity</label>
        <select
          id="opp-select"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm"
        >
          {opportunities.length === 0 && <option value="">No opportunities</option>}
          {opportunities.map((o) => <option key={o.id} value={o.id}>{o.title}</option>)}
        </select>
      </div>

      {portfolio && !isUnavailable(portfolio) && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-ink">Portfolio</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard label="Opportunities" value={(portfolio.opportunities_count as number) ?? "—"} />
            <MetricCard label="Contract value" value={rupees(portfolio.total_contract_value_minor as number, portfolio.currency as string)} />
            <MetricCard label="Submitted" value={rupees(portfolio.total_submitted_minor as number, portfolio.currency as string)} />
            <MetricCard label="Certified" value={rupees(portfolio.total_certified_minor as number, portfolio.currency as string)} />
            <MetricCard label="Cash exposure" value={rupees(portfolio.total_cash_exposure_minor as number, portfolio.currency as string)} />
            <MetricCard label="Healthy" value={(portfolio.opportunities_healthy as number) ?? 0} />
            <MetricCard label="At risk" value={(portfolio.opportunities_at_risk as number) ?? 0} />
            <MetricCard label="Margin protected" value={rupees(typeof portfolio.margin_protected === "object" && portfolio.margin_protected !== null ? (portfolio.margin_protected as Record<string, unknown>).total_margin_protected_minor as number : (portfolio.margin_protected as number | null), portfolio.currency as string)} />
          </div>
        </section>
      )}

      {selected && (
        <>
          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-ink">Exposure</h2>
            {exposure && !isUnavailable(exposure) ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard label="Submitted" value={rupees(exposure.submitted_minor as number, exposure.currency as string)} />
                <MetricCard label="Certified" value={rupees(exposure.certified_minor as number, exposure.currency as string)} />
                <MetricCard label="Rejected" value={rupees(exposure.rejected_minor as number, exposure.currency as string)} />
                <MetricCard label="Unnotified change" value={rupees(exposure.unnotified_change_minor as number, exposure.currency as string)} />
                <MetricCard label="Cash exposure" value={rupees(exposure.cash_exposure_minor as number, exposure.currency as string)} />
                <MetricCard label="Avg age (days)" value={exposure.age_days_avg as number} />
                <MetricCard label="Max age (days)" value={exposure.age_days_max as number} />
                <MetricCard label="At risk revenue" value={rupees(exposure.at_risk_revenue_minor as number, exposure.currency as string)} />
              </div>
            ) : <p className="text-sm text-slate-500">Exposure unavailable for this opportunity.</p>}
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-ink">Dashboard</h2>
            {dashboard && !isUnavailable(dashboard) ? (
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <p className="text-sm font-medium text-slate-700">Evidence health</p>
                    <p className="text-2xl font-semibold">{percent(health.score)}</p>
                    {health.reasons && health.reasons.length > 0 && (
                      <ul className="mt-1 list-disc pl-4 text-xs text-slate-600">
                        {health.reasons.map((r, i) => <li key={i}>{r}</li>)}
                      </ul>
                    )}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-700">Unclaimed change events</p>
                    <p className="text-2xl font-semibold">{dashboardData.unclaimed_change_events as number}</p>
                  </div>
                </div>
                {Object.keys(deadlines).length > 0 && (
                  <div className="mt-4">
                    <p className="text-sm font-medium text-slate-700">Deadlines</p>
                    <div className="mt-2 grid gap-2 sm:grid-cols-3">
                      {Object.entries(deadlines).map(([bucket, items]) => (
                        <div key={bucket} className="rounded-md bg-slate-50 p-3">
                          <p className="text-xs font-medium uppercase text-slate-500 capitalize">{bucket.replace(/_/g, " ")}</p>
                          <p className="text-lg font-semibold">{items.length}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : <p className="text-sm text-slate-500">Dashboard unavailable.</p>}
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-ink">Executive summary</h2>
            {executive ? (
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <p className="text-sm"><span className="font-medium text-slate-700">Contract value:</span> {rupees(executive.contract_value_minor as number, executive.currency as string)}</p>
                {topRisks.length > 0 && (
                  <div className="mt-3">
                    <p className="text-sm font-medium text-slate-700">Top risks</p>
                    <ul className="mt-2 space-y-2 text-sm">
                      {topRisks.map((r, i) => (
                        <li key={i} className="rounded-md border border-slate-100 p-2">
                          <span className="font-medium">{r.title as string}</span>
                          <span className="ml-2 text-xs capitalize">{r.severity as string}</span>
                          {r.amount_exposure !== undefined && <span className="ml-2 text-slate-500">{rupees(r.amount_exposure as number, r.currency as string)}</span>}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : <p className="text-sm text-slate-500">No executive summary.</p>}
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-ink">Response times</h2>
            {responseTimes && !isUnavailable(responseTimes) ? (
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <div className="grid gap-4 sm:grid-cols-4">
                  <MetricCard label="Count" value={overall.count ?? 0} />
                  <MetricCard label="Avg days" value={overall.avg_days ?? 0} />
                  <MetricCard label="Median days" value={overall.median_days ?? 0} />
                  <MetricCard label="P90 days" value={overall.p90_days ?? 0} />
                </div>
                {responseStats.length > 0 && (
                  <ul className="mt-4 space-y-1 text-sm">
                    {responseStats.map((s, i) => (
                      <li key={i} className="flex items-center justify-between border-b border-slate-100 py-2 last:border-0">
                        <span>{s.responder as string} · {s.response_kind as string}</span>
                        <span className="text-slate-500">avg {s.avg_days as number}d · max {s.max_days as number}d</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ) : <p className="text-sm text-slate-500">Response analytics unavailable.</p>}
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-ink">Payment schedule</h2>
            {paymentSchedule && !isUnavailable(paymentSchedule) ? (
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <div className="grid gap-4 sm:grid-cols-3 mb-4">
                  <MetricCard label="Pending" value={rupees(paymentSchedule.total_pending_minor as number, "INR")} />
                  <MetricCard label="Certified" value={rupees(paymentSchedule.total_certified_minor as number, "INR")} />
                  <MetricCard label="Overdue" value={rupees(paymentSchedule.total_overdue_minor as number, "INR")} />
                </div>
                {schedule.length > 0 ? (
                  <ul className="space-y-2 text-sm">
                    {schedule.map((p) => (
                      <li key={p.id as string} className="flex items-center justify-between border-b border-slate-100 py-2 last:border-0">
                        <span className="capitalize">{p.kind as string} · {formatDate(p.due_date as string)}</span>
                        <span className={`rounded-full px-2 py-0.5 text-xs ${p.status === "pending" ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700"}`}>{p.status as string}</span>
                        <span className="font-medium">{rupees(p.amount_minor as number, p.currency as string)}</span>
                      </li>
                    ))}
                  </ul>
                ) : <p className="text-sm text-slate-500">No payment events yet.</p>}
              </div>
            ) : <p className="text-sm text-slate-500">Payment schedule unavailable.</p>}

            <form onSubmit={addPaymentEvent} className="rounded-xl border border-slate-200 bg-white p-4">
              <h3 className="mb-3 text-sm font-semibold text-ink">Record payment event</h3>
              <div className="grid gap-3 sm:grid-cols-4">
                <label htmlFor="pay-kind" className="sr-only">Kind</label>
                <select id="pay-kind" value={paymentForm.kind} onChange={(e) => setPaymentForm({ ...paymentForm, kind: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm" required>
                  {["ra", "progress", "retention", "security"].map((k) => <option key={k} value={k}>{k}</option>)}
                </select>
                <label htmlFor="pay-due" className="sr-only">Due date</label>
                <input id="pay-due" aria-label="Due date" type="date" value={paymentForm.due_date} onChange={(e) => setPaymentForm({ ...paymentForm, due_date: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm" required />
                <label htmlFor="pay-amount" className="sr-only">Amount</label>
                <input id="pay-amount" aria-label="Amount minor" type="number" value={paymentForm.amount_minor} onChange={(e) => setPaymentForm({ ...paymentForm, amount_minor: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm" placeholder="amount (minor)" required />
                <label htmlFor="pay-certified" className="sr-only">Certified amount</label>
                <input id="pay-certified" aria-label="Certified amount minor" type="number" value={paymentForm.certified_amount_minor} onChange={(e) => setPaymentForm({ ...paymentForm, certified_amount_minor: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm" placeholder="certified (minor)" />
              </div>
              <button type="submit" disabled={loading} className="mt-3 rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40">Record</button>
            </form>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-ink">Forecast</h2>
            <form onSubmit={runForecast} className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="grid gap-3 sm:grid-cols-4">
                <label htmlFor="fc-cost" className="sr-only">Projected final cost</label>
                <input id="fc-cost" aria-label="Projected final cost minor" type="number" value={forecastForm.projected_final_cost_minor} onChange={(e) => setForecastForm({ ...forecastForm, projected_final_cost_minor: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm" placeholder="projected final cost (minor)" required />
                <label htmlFor="fc-contingency" className="sr-only">Contingency</label>
                <input id="fc-contingency" aria-label="Contingency percent" type="number" value={forecastForm.contingency_percent} onChange={(e) => setForecastForm({ ...forecastForm, contingency_percent: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm" placeholder="contingency %" />
                <label htmlFor="fc-coc" className="sr-only">Cost of capital</label>
                <input id="fc-coc" aria-label="Cost of capital pa" type="number" step="0.01" value={forecastForm.cost_of_capital_pa} onChange={(e) => setForecastForm({ ...forecastForm, cost_of_capital_pa: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm" placeholder="cost of capital pa" />
                <label htmlFor="fc-currency" className="sr-only">Currency</label>
                <input id="fc-currency" aria-label="Currency" value={forecastForm.currency} onChange={(e) => setForecastForm({ ...forecastForm, currency: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm" required />
              </div>
              <button type="submit" disabled={loading} className="mt-3 rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40">Run forecast</button>
            </form>
            {forecast && (
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <div className="grid gap-4 sm:grid-cols-3">
                  <MetricCard label="Forecast revenue" value={rupees(forecast.forecast_revenue_minor as number, forecast.currency as string)} />
                  <MetricCard label="Forecast cost" value={rupees(forecast.forecast_cost_minor as number, forecast.currency as string)} />
                  <MetricCard label="Forecast margin" value={rupees(forecast.forecast_margin_minor as number, forecast.currency as string)} />
                </div>
              </div>
            )}
          </section>
        </>
      )}

      {clauseTrends && !isUnavailable(clauseTrends) && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-ink">Clause trends</h2>
          {((clauseTrends.by_category as unknown[]) || []).length > 0 ? (
            <ul className="space-y-2">
              {(clauseTrends.by_category as Record<string, unknown>[]).map((c, i) => (
                <li key={i} className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 text-sm">
                  <span className="capitalize">{c.category as string}</span>
                  <span className="text-slate-500">{c.count as number} · {rupees(c.exposure_minor as number, c.currency as string)}</span>
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-slate-500">No trend data.</p>}
          {((clauseTrends.loss_reasons as unknown[]) || []).length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-semibold text-slate-700">Loss reasons</h3>
              <ul className="mt-2 space-y-2">
                {(clauseTrends.loss_reasons as Record<string, unknown>[]).map((r, i) => (
                  <li key={i} className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 text-sm">
                    <span>{r.reason as string}</span>
                    <span className="text-slate-500">{r.count as number} · {rupees(r.exposure_minor as number)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {recurringOmissions && !isUnavailable(recurringOmissions) && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-ink">Recurring omissions</h2>
          {((recurringOmissions.patterns as unknown[]) || []).length > 0 ? (
            <ul className="space-y-2">
              {(recurringOmissions.patterns as Record<string, unknown>[]).map((p, i) => (
                <li key={i} className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 text-sm">
                  <span className="capitalize">{p.label as string} {p.severity ? <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{p.severity as string}</span> : null}</span>
                  <span className="text-slate-500">historical count {p.historical_count as number}</span>
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-slate-500">No recurring omissions found.</p>}
        </section>
      )}

      {economics && !isUnavailable(economics) && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-ink">Economics</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard label="Paid conversion" value={percent(economics.paid_conversion_percent as number)} />
            <MetricCard label="Gross margin" value={percent(economics.gross_margin_percent as number)} />
            <MetricCard label="Total invoiced" value={rupees(economics.total_invoiced_minor as number, economics.currency as string)} />
            <MetricCard label="Project retention" value={percent(economics.project_retention_percent as number)} />
          </div>
        </section>
      )}

      {outcomes && !isUnavailable(outcomes) && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-ink">Customer outcomes</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard label="Risks priced" value={outcomes.risks_priced_count as number} />
            <MetricCard label="Risks priced value" value={rupees(outcomes.risks_priced_value_minor as number, outcomes.currency as string)} />
            <MetricCard label="Bad bids declined" value={outcomes.bad_bids_declined as number} />
            <MetricCard label="Omissions corrected" value={outcomes.omissions_corrected as number} />
          </div>
        </section>
      )}
    </div>
  );
}
