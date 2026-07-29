"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useSession } from "@/components/session";

export default function AnalyticsPage() {
  const { session } = useSession();
  const [rows, setRows] = useState<{
    id: string;
    title: string;
    submission_due: string | null;
    days_to_submission: number | null;
    risk_counts: Record<string, number>;
    qualification_gaps: number;
    boq_defects: number;
    export_ready: boolean;
  }[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    api.listComparison(session.token)
      .then((d) => setRows(d.opportunities))
      .catch((e) => setError(e.message));
  }, [session]);

  if (!session) return <p className="text-sm text-slate-500">Sign in to view analytics.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-ink">Analytics</h1>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {rows.length === 0 ? (
        <p className="text-sm text-slate-500">No opportunities to compare.</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {rows.map((o) => (
            <div key={o.id} className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="mb-2 flex items-center justify-between">
                <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${o.export_ready ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-800"}`}>
                  {o.export_ready ? "Export ready" : "Review pending"}
                </span>
                <span className="text-xs text-slate-400">
                  {o.days_to_submission != null ? `${o.days_to_submission}d to submission` : "—"}
                </span>
              </div>
              <h3 className="font-semibold text-ink">{o.title}</h3>
              <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                <div className="rounded bg-slate-50 p-2">
                  <p className="text-xs text-slate-500">Critical/High</p>
                  <p className="font-semibold">{(o.risk_counts.critical ?? 0) + (o.risk_counts.high ?? 0)}</p>
                </div>
                <div className="rounded bg-slate-50 p-2">
                  <p className="text-xs text-slate-500">BOQ defects</p>
                  <p className="font-semibold">{o.boq_defects}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
