"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useSession } from "@/components/session";

export default function AnalyticsPage() {
  const { session } = useSession();
  const router = useRouter();
  const [risk, setRisk] = useState<Record<string, unknown> | null>(null);
  const [deadline, setDeadline] = useState<Record<string, unknown> | null>(null);
  const [boq, setBoq] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (!session) return;
    api.riskSummary(session.token).then(setRisk).catch(() => {});
    api.deadlineDashboard(session.token).then(setDeadline).catch(() => {});
    api.boqDefectSummary(session.token).then(setBoq).catch(() => {});
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
        <h2 className="mb-3 text-lg font-semibold text-ink">Risk summary</h2>
        <pre className="max-h-60 overflow-auto rounded-md bg-slate-50 p-3 text-xs">{JSON.stringify(risk, null, 2) ?? "Loading..."}</pre>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-lg font-semibold text-ink">Deadline dashboard</h2>
        <pre className="max-h-60 overflow-auto rounded-md bg-slate-50 p-3 text-xs">{JSON.stringify(deadline, null, 2) ?? "Loading..."}</pre>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-lg font-semibold text-ink">BOQ defect summary</h2>
        <pre className="max-h-60 overflow-auto rounded-md bg-slate-50 p-3 text-xs">{JSON.stringify(boq, null, 2) ?? "Loading..."}</pre>
      </section>
    </div>
  );
}
