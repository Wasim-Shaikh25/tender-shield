"use client";

import { useEffect, useState } from "react";
import { api, type CashflowResult, type PricingLoading, type RateBenchmark, type RateBuildupResult, type SensitivityResult } from "@/lib/api";

function rupees(minor?: number, currency = "INR") {
  if (minor === undefined || minor === null) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(minor / 100);
}

export function PricingTab({
  token,
  opportunityId,
  boqCsv,
  gate,
}: {
  token: string;
  opportunityId: string;
  boqCsv: string;
  gate: { export_allowed?: boolean; reason?: string } | null;
}) {
  const [subTab, setSubTab] = useState<"loadings" | "benchmark" | "cashflow" | "buildup" | "sensitivity">("loadings");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const [loadings, setLoadings] = useState<PricingLoading[]>([]);
  const [benchmark, setBenchmark] = useState<RateBenchmark | null>(null);
  const [cashflow, setCashflow] = useState<CashflowResult | null>(null);
  const [buildup, setBuildup] = useState<RateBuildupResult | null>(null);
  const [sensitivity, setSensitivity] = useState<SensitivityResult | null>(null);

  const [benchForm, setBenchForm] = useState({ csv: boqCsv, authority: "in-works", year: "2025" });
  const [cfForm, setCfForm] = useState({
    contract_value_minor: "",
    duration_months: "12",
    cost_of_capital_pa: "0.12",
    currency: "INR",
    payment_days: "30",
    retention_pct: "5",
    retention_release_month: "13",
    mobilization_advance_pct: "5",
    mobilization_recovery_months: "3",
  });
  const [buildupForm, setBuildupForm] = useState({
    csv: boqCsv,
    currency: "INR",
    material_pct: "35",
    labour_pct: "30",
    equipment_pct: "15",
    overhead_pct: "10",
    profit_pct: "10",
  });
  const [sensForm, setSensForm] = useState({ csv: boqCsv, currency: "INR" });

  useEffect(() => {
    setBenchForm((f) => ({ ...f, csv: boqCsv }));
    setBuildupForm((f) => ({ ...f, csv: boqCsv }));
    setSensForm((f) => ({ ...f, csv: boqCsv }));
  }, [boqCsv]);

  async function runBuildup(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setNote(null);
    try {
      const d = await api.runRateBuildup(token, opportunityId, {
        csv: buildupForm.csv,
        currency: buildupForm.currency,
        material_pct: parseFloat(buildupForm.material_pct) / 100,
        labour_pct: parseFloat(buildupForm.labour_pct) / 100,
        equipment_pct: parseFloat(buildupForm.equipment_pct) / 100,
        overhead_pct: parseFloat(buildupForm.overhead_pct) / 100,
        profit_pct: parseFloat(buildupForm.profit_pct) / 100,
      });
      setBuildup(d);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Build-up failed");
    } finally {
      setBusy(false);
    }
  }

  async function runSensitivity(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setNote(null);
    try {
      const d = await api.runSensitivity(token, opportunityId, {
        csv: sensForm.csv,
        currency: sensForm.currency,
      });
      setSensitivity(d);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Sensitivity failed");
    } finally {
      setBusy(false);
    }
  }

  async function fetchLoadings() {
    setBusy(true);
    setNote(null);
    try {
      const d = await api.getLoadings(token, opportunityId);
      setLoadings(d.loadings);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Failed to load loadings");
    } finally {
      setBusy(false);
    }
  }

  async function runBenchmark(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setNote(null);
    try {
      const d = await api.runRateBenchmark(token, opportunityId, {
        csv: benchForm.csv,
        authority: benchForm.authority || undefined,
        year: benchForm.year || undefined,
      });
      setBenchmark(d);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Benchmark failed");
    } finally {
      setBusy(false);
    }
  }

  async function runCashflow(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setNote(null);
    try {
      const d = await api.runCashflow(token, opportunityId, {
        contract_value_minor: parseInt(cfForm.contract_value_minor, 10),
        duration_months: parseInt(cfForm.duration_months, 10),
        cost_of_capital_pa: parseFloat(cfForm.cost_of_capital_pa),
        currency: cfForm.currency,
        payment_days: cfForm.payment_days ? parseInt(cfForm.payment_days, 10) : undefined,
        retention_pct: cfForm.retention_pct ? parseFloat(cfForm.retention_pct) : undefined,
        retention_release_month: cfForm.retention_release_month ? parseInt(cfForm.retention_release_month, 10) : undefined,
        mobilization_advance_pct: cfForm.mobilization_advance_pct ? parseFloat(cfForm.mobilization_advance_pct) : undefined,
        mobilization_recovery_months: cfForm.mobilization_recovery_months ? parseInt(cfForm.mobilization_recovery_months, 10) : undefined,
      });
      setCashflow(d);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Cashflow failed");
    } finally {
      setBusy(false);
    }
  }

  const gateBlocked = gate && !gate.export_allowed;

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-semibold text-ink">Pricing intelligence</h3>
        <p className="text-sm text-slate-600">Loadings, rate benchmarks, and project cashflow.</p>
      </div>

      {note && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{note}</p>}

      {gateBlocked && (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-700">
          Review gate closed: {gate?.reason || "Complete review before pricing outputs are enabled."}
        </p>
      )}

      <div className="flex gap-1 border-b border-slate-200">
        {(["loadings", "benchmark", "cashflow", "buildup", "sensitivity"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setSubTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize ${subTab === t ? "border-b-2 border-ink text-ink" : "text-slate-500 hover:text-ink"}`}
          >
            {t}
          </button>
        ))}
      </div>

      {subTab === "loadings" && (
        <div className="space-y-4">
          <button
            onClick={fetchLoadings}
            disabled={busy}
            className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
          >
            Compute loadings
          </button>
          {loadings.length === 0 ? (
            <p className="text-sm text-slate-500">No loadings yet.</p>
          ) : (
            <ul className="space-y-2">
              {loadings.map((l) => (
                <li key={l.finding_id} className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-ink">{l.pattern_id}</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs ${l.produced ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{l.produced ? "produced" : "not produced"}</span>
                  </div>
                  <p className="text-slate-600">{l.basis} · {l.formula}</p>
                  {l.produced && l.amount_minor !== undefined && l.amount_minor !== null && (
                    <p className="mt-1 font-semibold">{rupees(l.amount_minor, l.currency)}</p>
                  )}
                  {l.reason && <p className="mt-1 text-xs text-slate-500">{l.reason}</p>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {subTab === "benchmark" && (
        <div className="space-y-4">
          <form onSubmit={runBenchmark} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="space-y-1 sm:col-span-2">
                <label htmlFor="bench-csv" className="text-sm font-medium text-slate-700">BOQ CSV</label>
                <textarea
                  id="bench-csv"
                  value={benchForm.csv}
                  onChange={(e) => setBenchForm({ ...benchForm, csv: e.target.value })}
                  className="h-32 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                  placeholder="description,unit,qty,rate,..."
                  required
                />
              </div>
              <div className="space-y-2">
                <div className="space-y-1">
                  <label htmlFor="bench-authority" className="text-sm font-medium text-slate-700">Authority</label>
                  <input id="bench-authority" value={benchForm.authority} onChange={(e) => setBenchForm({ ...benchForm, authority: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
                </div>
                <div className="space-y-1">
                  <label htmlFor="bench-year" className="text-sm font-medium text-slate-700">Year</label>
                  <input id="bench-year" value={benchForm.year} onChange={(e) => setBenchForm({ ...benchForm, year: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
                </div>
              </div>
            </div>
            <button type="submit" disabled={busy} className="mt-3 rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40">Run benchmark</button>
          </form>

          {benchmark && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-sm"><span className="font-medium">Schedule:</span> {benchmark.schedule_id || "—"} · <span className="font-medium">Headline variance:</span> {benchmark.headline_variance_pct?.toFixed(2) ?? "—"}%</p>
              {[...benchmark.code_matched, ...benchmark.description_matched, ...benchmark.unmatched].length > 0 && (
                <table className="mt-3 w-full text-sm">
                  <thead className="bg-slate-50 text-left text-slate-700">
                    <tr>
                      <th className="px-2 py-1">BOQ description</th>
                      <th className="px-2 py-1">Unit</th>
                      <th className="px-2 py-1">BOQ rate</th>
                      <th className="px-2 py-1">Schedule rate</th>
                      <th className="px-2 py-1">Variance</th>
                      <th className="px-2 py-1">Match</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...benchmark.code_matched, ...benchmark.description_matched, ...benchmark.unmatched].map((m, i) => (
                      <tr key={i} className="border-b border-slate-100">
                        <td className="px-2 py-1">{m.boq_description}</td>
                        <td className="px-2 py-1">{m.boq_unit}</td>
                        <td className="px-2 py-1">{rupees(m.boq_rate_minor, "INR")}</td>
                        <td className="px-2 py-1">{m.schedule_rate_minor ? rupees(m.schedule_rate_minor, "INR") : "—"}</td>
                        <td className="px-2 py-1">{m.variance_pct !== undefined && m.variance_pct !== null ? `${m.variance_pct.toFixed(1)}%` : "—"}</td>
                        <td className="px-2 py-1 capitalize">{m.matched_by.replace(/_/g, " ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      )}

      {subTab === "cashflow" && (
        <div className="space-y-4">
          <form onSubmit={runCashflow} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="grid gap-3 sm:grid-cols-4">
              <div className="space-y-1">
                <label htmlFor="cf-contract" className="text-sm font-medium text-slate-700">Contract value</label>
                <input id="cf-contract" type="number" value={cfForm.contract_value_minor} onChange={(e) => setCfForm({ ...cfForm, contract_value_minor: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" placeholder="minor" required />
              </div>
              <div className="space-y-1">
                <label htmlFor="cf-duration" className="text-sm font-medium text-slate-700">Duration (months)</label>
                <input id="cf-duration" type="number" value={cfForm.duration_months} onChange={(e) => setCfForm({ ...cfForm, duration_months: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" required />
              </div>
              <div className="space-y-1">
                <label htmlFor="cf-coc" className="text-sm font-medium text-slate-700">Cost of capital</label>
                <input id="cf-coc" type="number" step="0.01" value={cfForm.cost_of_capital_pa} onChange={(e) => setCfForm({ ...cfForm, cost_of_capital_pa: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" required />
              </div>
              <div className="space-y-1">
                <label htmlFor="cf-currency" className="text-sm font-medium text-slate-700">Currency</label>
                <input id="cf-currency" value={cfForm.currency} onChange={(e) => setCfForm({ ...cfForm, currency: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" required />
              </div>
              <div className="space-y-1">
                <label htmlFor="cf-payment" className="text-sm font-medium text-slate-700">Payment days</label>
                <input id="cf-payment" type="number" value={cfForm.payment_days} onChange={(e) => setCfForm({ ...cfForm, payment_days: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
              </div>
              <div className="space-y-1">
                <label htmlFor="cf-retention" className="text-sm font-medium text-slate-700">Retention %</label>
                <input id="cf-retention" type="number" value={cfForm.retention_pct} onChange={(e) => setCfForm({ ...cfForm, retention_pct: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
              </div>
              <div className="space-y-1">
                <label htmlFor="cf-ret-rel" className="text-sm font-medium text-slate-700">Retention release month</label>
                <input id="cf-ret-rel" type="number" value={cfForm.retention_release_month} onChange={(e) => setCfForm({ ...cfForm, retention_release_month: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
              </div>
              <div className="space-y-1">
                <label htmlFor="cf-mob" className="text-sm font-medium text-slate-700">Mobilization %</label>
                <input id="cf-mob" type="number" value={cfForm.mobilization_advance_pct} onChange={(e) => setCfForm({ ...cfForm, mobilization_advance_pct: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
              </div>
            </div>
            <button type="submit" disabled={busy} className="mt-3 rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40">Run cashflow</button>
          </form>

          {cashflow && (
            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="rounded-xl border border-slate-200 bg-white p-4">
                  <p className="text-xs text-slate-500 uppercase">Peak requirement</p>
                  <p className="mt-1 text-xl font-semibold">{rupees(cashflow.peak_requirement_minor, cashflow.currency)}</p>
                  <p className="text-xs text-slate-500">month {cashflow.peak_month}</p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-4">
                  <p className="text-xs text-slate-500 uppercase">Total financing cost</p>
                  <p className="mt-1 text-xl font-semibold">{rupees(cashflow.total_financing_cost_minor, cashflow.currency)}</p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-4">
                  <p className="text-xs text-slate-500 uppercase">Duration</p>
                  <p className="mt-1 text-xl font-semibold">{cashflow.monthly.length} months</p>
                </div>
              </div>
              {cashflow.assumptions.length > 0 && (
                <ul className="list-disc pl-5 text-sm text-slate-600">
                  {cashflow.assumptions.map((a, i) => <li key={i}>{a}</li>)}
                </ul>
              )}
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-700">
                  <tr>
                    <th className="px-2 py-1">Month</th>
                    <th className="px-2 py-1">Billed</th>
                    <th className="px-2 py-1">Incurred</th>
                    <th className="px-2 py-1">Received</th>
                    <th className="px-2 py-1">Cumulative net</th>
                  </tr>
                </thead>
                <tbody>
                  {cashflow.monthly.map((m) => (
                    <tr key={m.month} className="border-b border-slate-100">
                      <td className="px-2 py-1">{m.month}</td>
                      <td className="px-2 py-1">{rupees(m.billed_minor, cashflow.currency)}</td>
                      <td className="px-2 py-1">{rupees(m.incurred_minor, cashflow.currency)}</td>
                      <td className="px-2 py-1">{rupees(m.received_minor, cashflow.currency)}</td>
                      <td className={`px-2 py-1 font-medium ${m.cumulative_net_minor < 0 ? "text-rose-600" : "text-emerald-600"}`}>{rupees(m.cumulative_net_minor, cashflow.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {subTab === "buildup" && (
        <div className="space-y-4">
          <form onSubmit={runBuildup} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="grid gap-3 sm:grid-cols-6">
              <div className="space-y-1 sm:col-span-2">
                <label htmlFor="bu-csv" className="text-sm font-medium text-slate-700">BOQ CSV</label>
                <textarea id="bu-csv" value={buildupForm.csv} onChange={(e) => setBuildupForm({ ...buildupForm, csv: e.target.value })} className="h-24 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" placeholder="description,unit,qty,rate,..." required />
              </div>
              <div className="space-y-1"><label htmlFor="bu-material" className="text-sm font-medium text-slate-700">Material %</label><input id="bu-material" type="number" step="0.1" value={buildupForm.material_pct} onChange={(e) => setBuildupForm({ ...buildupForm, material_pct: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" /></div>
              <div className="space-y-1"><label htmlFor="bu-labour" className="text-sm font-medium text-slate-700">Labour %</label><input id="bu-labour" type="number" step="0.1" value={buildupForm.labour_pct} onChange={(e) => setBuildupForm({ ...buildupForm, labour_pct: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" /></div>
              <div className="space-y-1"><label htmlFor="bu-equipment" className="text-sm font-medium text-slate-700">Equipment %</label><input id="bu-equipment" type="number" step="0.1" value={buildupForm.equipment_pct} onChange={(e) => setBuildupForm({ ...buildupForm, equipment_pct: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" /></div>
              <div className="space-y-1"><label htmlFor="bu-overhead" className="text-sm font-medium text-slate-700">Overhead %</label><input id="bu-overhead" type="number" step="0.1" value={buildupForm.overhead_pct} onChange={(e) => setBuildupForm({ ...buildupForm, overhead_pct: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" /></div>
              <div className="space-y-1"><label htmlFor="bu-profit" className="text-sm font-medium text-slate-700">Profit %</label><input id="bu-profit" type="number" step="0.1" value={buildupForm.profit_pct} onChange={(e) => setBuildupForm({ ...buildupForm, profit_pct: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" /></div>
            </div>
            <button type="submit" disabled={busy} className="mt-3 rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40">Run build-up</button>
          </form>
          {buildup && (
            <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <div><p className="text-xs text-slate-500 uppercase">Total amount</p><p className="text-xl font-semibold">{rupees(buildup.total_amount_minor, buildup.currency)}</p></div>
                <div><p className="text-xs text-slate-500 uppercase">Total profit</p><p className="text-xl font-semibold">{rupees(buildup.total_profit_minor, buildup.currency)}</p></div>
                <div><p className="text-xs text-slate-500 uppercase">Items</p><p className="text-xl font-semibold">{buildup.items.length}</p></div>
              </div>
              {buildup.assumptions.length > 0 && (
                <ul className="list-disc pl-5 text-sm text-slate-600">{buildup.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul>
              )}
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-700">
                  <tr>
                    <th className="px-2 py-1">Description</th>
                    <th className="px-2 py-1">Unit</th>
                    <th className="px-2 py-1">Qty</th>
                    <th className="px-2 py-1">Rate</th>
                    <th className="px-2 py-1">M/L/E/O/P</th>
                  </tr>
                </thead>
                <tbody>
                  {buildup.items.map((it) => (
                    <tr key={it.src_row} className="border-b border-slate-100">
                      <td className="px-2 py-1">{it.description}</td>
                      <td className="px-2 py-1">{it.unit}</td>
                      <td className="px-2 py-1">{it.qty}</td>
                      <td className="px-2 py-1">{rupees(it.rate_minor, buildup.currency)}</td>
                      <td className="px-2 py-1">{rupees(it.material_rate_minor, buildup.currency)} / {rupees(it.labour_rate_minor, buildup.currency)} / {rupees(it.equipment_rate_minor, buildup.currency)} / {rupees(it.overhead_rate_minor, buildup.currency)} / {rupees(it.profit_rate_minor, buildup.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {subTab === "sensitivity" && (
        <div className="space-y-4">
          <form onSubmit={runSensitivity} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="space-y-1 sm:col-span-3">
                <label htmlFor="sens-csv" className="text-sm font-medium text-slate-700">BOQ CSV</label>
                <textarea id="sens-csv" value={sensForm.csv} onChange={(e) => setSensForm({ ...sensForm, csv: e.target.value })} className="h-24 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" placeholder="description,unit,qty,rate,..." required />
              </div>
            </div>
            <button type="submit" disabled={busy} className="mt-3 rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40">Run sensitivity</button>
          </form>
          {sensitivity && (
            <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <div><p className="text-xs text-slate-500 uppercase">Base total</p><p className="text-xl font-semibold">{rupees(sensitivity.base_total_minor, sensitivity.currency)}</p></div>
              </div>
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-700">
                  <tr>
                    <th className="px-2 py-1">Scenario</th>
                    <th className="px-2 py-1">Param</th>
                    <th className="px-2 py-1">Delta %</th>
                    <th className="px-2 py-1">Total</th>
                    <th className="px-2 py-1">Delta</th>
                    <th className="px-2 py-1">Delta % total</th>
                  </tr>
                </thead>
                <tbody>
                  {sensitivity.scenarios.map((s, i) => (
                    <tr key={i} className="border-b border-slate-100">
                      <td className="px-2 py-1">{s.name}</td>
                      <td className="px-2 py-1">{s.param}</td>
                      <td className="px-2 py-1">{s.delta_pct}%</td>
                      <td className="px-2 py-1">{rupees(s.total_amount_minor, sensitivity.currency)}</td>
                      <td className="px-2 py-1">{rupees(s.delta_minor, sensitivity.currency)}</td>
                      <td className="px-2 py-1">{s.delta_pct_total}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
