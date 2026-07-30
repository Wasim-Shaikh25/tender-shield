"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, Opportunity, PlanSnapshot } from "@/lib/api";
import { useSession } from "@/components/session";

type Section = {
  type: "kpi" | "table" | "chart" | "mermaid" | "text";
  title: string;
  data: Record<string, unknown>;
};

type PlanDashboard = {
  title: string;
  summary: string;
  sections: Section[];
  citations?: string[];
};

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

function KpiSection({ data }: { data: Record<string, unknown> }) {
  const value = typeof data.value === "number" ? data.value : (data.value as string) ?? "-";
  const unit = (data.unit as string) ?? "";
  const trend = (data.trend as string | undefined) ?? undefined;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs text-slate-500 uppercase">{(data.label as string) ?? "Metric"}</p>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-3xl font-semibold text-ink">{value}</span>
        {unit && <span className="text-sm text-slate-500">{unit}</span>}
        {trend && (
          <span
            className={`text-sm font-medium ${
              trend === "up" ? "text-red-600" : trend === "down" ? "text-emerald-600" : "text-slate-600"
            }`}
          >
            {trend === "up" ? "↑" : trend === "down" ? "↓" : "→"}
          </span>
        )}
      </div>
    </div>
  );
}

function TableSection({ data }: { data: Record<string, unknown> }) {
  const columns = (data.columns as Array<{ key: string; label: string }>) ?? [];
  const rows = (data.rows as Array<Record<string, unknown>>) ?? [];
  if (columns.length === 0) return <p className="text-sm text-slate-500">No columns defined.</p>;
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white p-4">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left">
            {columns.map((col) => (
              <th key={col.key} className="py-2 pr-4 font-medium text-slate-700">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx} className="border-b border-slate-100 last:border-0">
              {columns.map((col) => (
                <td key={col.key} className="py-2 pr-4 text-slate-700">
                  {String(row[col.key] ?? "-")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChartSection({ data }: { data: Record<string, unknown> }) {
  const chartType = (data.chart_type as string) ?? "bar";
  const labels = (data.labels as string[]) ?? [];
  const datasets = (data.datasets as Array<{ label?: string; data: number[] }>) ?? [];
  const chartData = labels.map((label, i) => ({
    name: label,
    ...Object.fromEntries(datasets.map((ds) => [ds.label ?? "value", ds.data[i] ?? 0])),
  }));
  const keys = datasets.map((ds) => ds.label ?? "value");

  if (chartType === "pie") {
    const pieData = datasets[0]?.data?.map((v, i) => ({ name: labels[i] ?? i, value: v })) ?? [];
    return (
      <div className="h-64 w-full rounded-xl border border-slate-200 bg-white p-4">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={pieData} dataKey="value" nameKey="name" outerRadius={80} label>
              {pieData.map((_, i) => (
                <Cell key={`cell-${i}`} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  const Chart = chartType === "line" ? LineChart : BarChart;
  return (
    <div className="h-64 w-full rounded-xl border border-slate-200 bg-white p-4">
      <ResponsiveContainer width="100%" height="100%">
        <Chart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          {keys.map((key, i) =>
            chartType === "line" ? (
              <Line key={key} type="monotone" dataKey={key} stroke={COLORS[i % COLORS.length]} />
            ) : (
              <Bar key={key} dataKey={key} fill={COLORS[i % COLORS.length]} />
            )
          )}
        </Chart>
      </ResponsiveContainer>
    </div>
  );
}

function MermaidSection({ data, id }: { data: Record<string, unknown>; id: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const diagram = (data.diagram as string) ?? "";

  useEffect(() => {
    if (!ref.current || !diagram) return;
    let cancelled = false;
    import("mermaid")
      .then((m) => {
        if (cancelled) return;
        const mod = (m as { default?: { initialize: (c: Record<string, unknown>) => void; run: (c?: { nodes?: Iterable<HTMLElement> }) => Promise<void> } }).default;
        if (!mod) return;
        mod.initialize({ startOnLoad: false, theme: "default" });
        void mod.run({ nodes: [ref.current!] });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [diagram, id]);

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white p-4">
      <div ref={ref} className="mermaid">
        {diagram}
      </div>
    </div>
  );
}

function TextSection({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="whitespace-pre-wrap rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
      {String(data.content ?? "")}
    </div>
  );
}

function SectionCard({ section, index }: { section: Section; index: number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold text-ink">{section.title}</h3>
      {section.type === "kpi" && <KpiSection data={section.data} />}
      {section.type === "table" && <TableSection data={section.data} />}
      {section.type === "chart" && <ChartSection data={section.data} />}
      {section.type === "mermaid" && <MermaidSection data={section.data} id={`m-${index}`} />}
      {section.type === "text" && <TextSection data={section.data} />}
    </div>
  );
}

type PlanTemplate = { id: string; name: string; query: string };

export default function PlanPage() {
  const { session } = useSession();
  const router = useRouter();
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [opportunityId, setOpportunityId] = useState("");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<PlanDashboard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<PlanTemplate[]>([]);
  const [snapshots, setSnapshots] = useState<PlanSnapshot[]>([]);
  const [snapshotTitle, setSnapshotTitle] = useState("");
  const [saving, setSaving] = useState(false);

  const loadSnapshots = useCallback(() => {
    if (!session) return;
    api.listPlanSnapshots(session.token)
      .then((res) => setSnapshots(res.snapshots))
      .catch(() => {});
  }, [session]);

  useEffect(() => {
    if (!session) return;
    api.listOpportunities(session.token)
      .then((res) => setOpportunities(res.opportunities))
      .catch(() => {});
    api.planTemplates().then(setTemplates).catch(() => {});
    loadSnapshots();
  }, [session, loadSnapshots]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!opportunityId || !query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = (await api.planDashboard(session!.token, opportunityId, query.trim())) as PlanDashboard;
      setResult(data);
      setSnapshotTitle(data.title || "Plan snapshot");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate dashboard");
    } finally {
      setLoading(false);
    }
  };

  const saveSnapshot = async () => {
    if (!session || !opportunityId || !result || !snapshotTitle.trim()) return;
    setSaving(true);
    try {
      await api.savePlanSnapshot(session.token, {
        opportunity_id: opportunityId,
        title: snapshotTitle.trim(),
        query: query.trim(),
        dashboard: result as unknown as Record<string, unknown>,
      });
      loadSnapshots();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save snapshot");
    } finally {
      setSaving(false);
    }
  };

  const loadSnapshot = async (snapshotId: string) => {
    if (!session) return;
    try {
      const data = await api.getPlanSnapshot(session.token, snapshotId);
      setOpportunityId(data.opportunity_id);
      setQuery(data.query);
      setSnapshotTitle(data.title);
      setResult(data.dashboard as unknown as PlanDashboard);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load snapshot");
    }
  };

  const exportSnapshot = async (snapshotId: string, format: string) => {
    if (!session) return;
    try {
      const blob = await api.exportPlanSnapshot(session.token, snapshotId, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `plan-${snapshotId}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    }
  };

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold text-ink">Tender plan dashboard</h1>
      <p className="text-sm text-slate-600">
        Ask a question about a tender. The AI builds a structured dashboard with KPIs, tables, charts, sequence diagrams, and mind maps.
      </p>

      <form onSubmit={submit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
        <div>
          <label htmlFor="opportunity" className="block text-sm font-medium text-slate-700">Opportunity</label>
          <select
            id="opportunity"
            value={opportunityId}
            onChange={(e) => setOpportunityId(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-ink"
          >
            <option value="">Select an opportunity</option>
            {opportunities.map((opp) => (
              <option key={opp.id} value={opp.id}>{opp.title}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="template" className="block text-sm font-medium text-slate-700">Template</label>
          <select
            id="template"
            value=""
            onChange={(e) => {
              const t = templates.find((x) => x.id === e.target.value);
              if (t) setQuery(t.query);
            }}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-ink"
          >
            <option value="">Pick a template (optional)</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="query" className="block text-sm font-medium text-slate-700">What do you want to see?</label>
          <input
            id="query"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. Show risk severity distribution and deadline timeline as a mindmap"
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-ink"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !opportunityId || !query.trim()}
          className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Generating…" : "Generate dashboard"}
        </button>
      </form>

      {result && (
        <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
          <h3 className="text-sm font-semibold text-slate-700">Save this dashboard</h3>
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              type="text"
              value={snapshotTitle}
              onChange={(e) => setSnapshotTitle(e.target.value)}
              placeholder="Snapshot title"
              className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm text-ink"
            />
            <button
              type="button"
              onClick={saveSnapshot}
              disabled={saving || !snapshotTitle.trim()}
              className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save snapshot"}
            </button>
          </div>
        </div>
      )}

      {snapshots.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-700">Saved snapshots</h3>
          <ul className="divide-y divide-slate-100">
            {snapshots.map((s) => (
              <li key={s.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-medium text-ink">{s.title}</p>
                  <p className="text-xs text-slate-500">{s.created_at}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => s.id && loadSnapshot(s.id)}
                    className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Load
                  </button>
                  <button
                    type="button"
                    onClick={() => s.id && exportSnapshot(s.id, "pdf")}
                    className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    PDF
                  </button>
                  <button
                    type="button"
                    onClick={() => s.id && exportSnapshot(s.id, "pptx")}
                    className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    PPTX
                  </button>
                  <button
                    type="button"
                    onClick={() => s.id && api.deletePlanSnapshot(session!.token, s.id).then(loadSnapshots)}
                    className="rounded-md border border-red-200 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-50"
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {result && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6">
            <h2 className="text-lg font-semibold text-ink">{result.title}</h2>
            <p className="mt-1 text-sm text-slate-600">{result.summary}</p>
            {result.citations && result.citations.length > 0 && (
              <p className="mt-2 text-xs text-slate-400">Citations: {result.citations.join(", ")}</p>
            )}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {result.sections.map((section, idx) => (
              <SectionCard key={idx} section={section} index={idx} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
