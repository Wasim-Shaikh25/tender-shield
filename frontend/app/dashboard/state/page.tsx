"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, type WorkspaceStateSummary } from "@/lib/api";
import { useSession } from "@/components/session";

export default function DashboardStatePage() {
  const { session } = useSession();
  const router = useRouter();
  const [summaries, setSummaries] = useState<WorkspaceStateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    api.listWorkspaceStateSummaries(session.token)
      .then((res) => setSummaries(res.workspaces))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load summaries"))
      .finally(() => setLoading(false));
  }, [session]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  if (loading) return <p className="text-sm text-slate-500">Loading…</p>;
  if (error) return <p className="text-sm text-red-600">{error}</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">State dashboard</h1>
        <p className="text-sm text-slate-600">Opportunity counts and upcoming deadlines per workspace.</p>
      </div>

      {summaries.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          No workspaces found.
        </div>
      )}

      {summaries.map((ws) => (
        <div key={ws.workspace_id} className="rounded-xl border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-ink">{ws.workspace_name || "Workspace"}</h2>
            <span className="text-sm text-slate-500">{ws.opportunity_count} projects</span>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-5">
            {Object.entries(ws.state_counts).map(([state, count]) =>
              count > 0 ? (
                <div key={state} className="rounded-lg bg-slate-50 p-3">
                  <p className="text-xl font-bold text-ink">{count}</p>
                  <p className="text-xs capitalize text-slate-500">{state.replace(/_/g, " ")}</p>
                </div>
              ) : null
            )}
          </div>

          {ws.upcoming_deadlines.length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-semibold text-slate-700">Upcoming deadlines (≤7 days)</h3>
              <ul className="mt-2 space-y-2">
                {ws.upcoming_deadlines.map((d) => (
                  <li key={d.opportunity_id} className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2 text-sm">
                    <Link href={`/opportunities/${d.opportunity_id}`} className="font-medium text-ink hover:text-blue-600">
                      {d.title}
                    </Link>
                    <span className="text-xs text-slate-500">
                      {d.submission_due ? `${new Date(d.submission_due).toLocaleDateString()} (${d.days_to_deadline}d)` : "No date"} · {d.state}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
