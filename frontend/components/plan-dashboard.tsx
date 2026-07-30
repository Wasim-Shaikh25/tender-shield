"use client";

import { useEffect, useRef } from "react";
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

export type PlanSection = {
  type: "kpi" | "table" | "chart" | "mermaid" | "text";
  title: string;
  data: Record<string, unknown>;
};

export type PlanDashboard = {
  title: string;
  summary: string;
  sections: PlanSection[];
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

export function SectionCard({ section, index }: { section: PlanSection; index: number }) {
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

export function DashboardView({ dashboard }: { dashboard: PlanDashboard }) {
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="text-lg font-semibold text-ink">{dashboard.title}</h2>
        <p className="mt-1 text-sm text-slate-600">{dashboard.summary}</p>
        {dashboard.citations && dashboard.citations.length > 0 && (
          <p className="mt-2 text-xs text-slate-400">Citations: {dashboard.citations.join(", ")}</p>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {dashboard.sections.map((section, idx) => (
          <SectionCard key={idx} section={section} index={idx} />
        ))}
      </div>
    </div>
  );
}
