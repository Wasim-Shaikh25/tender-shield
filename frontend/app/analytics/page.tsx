"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useSession } from "@/components/session";

type RiskSummary = {
  total: number;
  by_severity: Record<string, number>;
  by_category: Record<string, number>;
  total_exposure_minor: number;
};

type DeadlineDashboard = {
  now: string;
  buckets: Record<string, string[]>;
};

type BoqSummary = {
  total: number;
  by_trade: Record<string, Record<string, number>>;
};

function rupees(minor: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(minor / 100);
}

function CountCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs text-slate-500 uppercase">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-ink">{value}</p>
    </div>
  );
}

function Distribution({ title, data }: { title: string; data: Record<string, number> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold text-ink">{title}</h3>
      {entries.length === 0 ? (
        <p className="text-sm text-slate-500">No data yet.</p>
      ) : (
        <div className="space-y-2">
          {entries.map(([key, count]) => (
            <div key={key} className="flex items-center justify-between text-sm">
              <span className="capitalize text-slate-700">{key.replace(/_/g, " ")}</span>
              <span className="rounded-md bg-slate-100 px-2 py-0.5 font-medium text-slate-900">{count}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AnalyticsPage() {
  const { session } = useSession();
  const router = useRouter();
  const [risk, setRisk] = useState<RiskSummary | null>(null);
  const [deadline, setDeadline] = useState<DeadlineDashboard | null>(null);
  const [boq, setBoq] = useState<BoqSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (!session) return;
    api.riskSummary(session.token).then((d) => setRisk(d as RiskSummary)).catch(() => {});
    api.deadlineDashboard(session.token).then((d) => setDeadline(d as DeadlineDashboard)).catch(() => {});
    api.boqDefectSummary(session.token).then((d) => setBoq(d as BoqSummary)).catch(() => {});
  }, [session]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  const exportReport = async (format: string) => {
    if (!session) return;
    setExporting(true);
    setError(null);
    try {
      const blob = await api.exportReport(session.token, format, "all");
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report.${format === "xlsx" ? "xlsx" : format}`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(false);
    }
  };

  const deadlineLabels: Record<string, string> = {
    overdue: "Overdue",
    "7_days": "≤ 7 days",
    "15_days": "≤ 15 days",
    "30_days": "≤ 30 days",
    later: "> 30 days",
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink">Analysis & reports</h1>
        <div className="flex gap-2">
          <button onClick={() => exportReport("csv")} disabled={exporting} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50">CSV</button>
          <button onClick={() => exportReport("xlsx")} disabled={exporting} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50">XLSX</button>
          <button onClick={() => exportReport("pdf")} disabled={exporting} className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50">PDF</button>
        </div>
      </div>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink">Risk summary</h2>
        {risk ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <CountCard label="Total risk findings" value={risk.total} />
            <CountCard label="Total exposure" value={risk.total_exposure_minor / 100} />
            <Distribution title="By severity" data={risk.by_severity} />
            <Distribution title="By category" data={risk.by_category} />
          </div>
        ) : (
          <p className="text-sm text-slate-500">Loading risk summary…</p>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink">Deadline dashboard</h2>
        {deadline ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {Object.entries(deadline.buckets).map(([key, ids]) => (
              <CountCard key={key} label={deadlineLabels[key] ?? key} value={ids.length} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">Loading deadlines…</p>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink">BOQ defect summary</h2>
        {boq ? (
          <>
            <p className="mb-4 text-sm text-slate-600">Total defects: <strong>{boq.total}</strong></p>
            {Object.keys(boq.by_trade).length === 0 ? (
              <p className="text-sm text-slate-500">No BOQ defects found.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left">
                      <th className="py-2 font-medium text-slate-700">Trade</th>
                      <th className="py-2 font-medium text-slate-700">Category</th>
                      <th className="py-2 text-right font-medium text-slate-700">Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(boq.by_trade).flatMap(([trade, categories]) =>
                      Object.entries(categories).map(([category, count], idx) => (
                        <tr key={`${trade}-${category}`} className="border-b border-slate-100 last:border-0">
                          {idx === 0 ? (
                            <td className="py-2 font-medium text-slate-900" rowSpan={Object.keys(categories).length}>{trade}</td>
                          ) : null}
                          <td className="py-2 text-slate-700">{category.replace(/_/g, " ")}</td>
                          <td className="py-2 text-right font-medium text-slate-900">{count}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : (
          <p className="text-sm text-slate-500">Loading BOQ summary…</p>
        )}
      </section>
    </div>
  );
}
