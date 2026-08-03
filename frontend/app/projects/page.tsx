"use client";

import { useEffect, useId, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type ProjectState, type Workspace } from "@/lib/api";
import { useSession } from "@/components/session";

const HEALTH_CLASS: Record<string, string> = {
  healthy: "bg-emerald-100 text-emerald-700",
  at_risk: "bg-amber-100 text-amber-700",
  poor: "bg-rose-100 text-rose-700",
  completed: "bg-slate-100 text-slate-600",
};

const HEALTH_LABEL: Record<string, string> = {
  healthy: "Healthy",
  at_risk: "At risk",
  poor: "Poor",
  completed: "Completed",
};

export default function ProjectsPage() {
  const { session } = useSession();
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectState[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const baseId = useId();

  useEffect(() => {
    if (!session) return;
    api.listWorkspaces(session.token).then((res) => setWorkspaces(res));
  }, [session]);

  useEffect(() => {
    if (!session) return;
    setLoading(true);
    setError(null);
    api.listProjectStates(session.token, {
      ...Object.fromEntries(
        Object.entries(filters).map(([k, v]) => [k, v === "all" ? "" : v])
      ),
    })
      .then((res) => setProjects(res.opportunities))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load projects"))
      .finally(() => setLoading(false));
  }, [session, filters]);

  const counts = useMemo(() => {
    const byState: Record<string, number> = {};
    const byHealth: Record<string, number> = {};
    projects.forEach((p) => {
      byState[p.state] = (byState[p.state] || 0) + 1;
      byHealth[p.health] = (byHealth[p.health] || 0) + 1;
    });
    return { byState, byHealth };
  }, [projects]);

  function updateFilter(key: string, value: string) {
    setFilters((f) => ({ ...f, [key]: value }));
  }

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">All Projects</h1>
          <p className="text-sm text-slate-600">
            Track every tender across your workspaces, filtered by state, health, and deadline.
          </p>
        </div>
        <Link
          href="/opportunities"
          className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          + New opportunity
        </Link>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
        {Object.entries(counts.byState).map(([state, count]) => (
          <button
            key={state}
            type="button"
            onClick={() => updateFilter("status", state)}
            className={`rounded-xl border border-slate-200 bg-white p-3 text-left transition hover:border-ink ${
              filters.status === state ? "ring-2 ring-ink" : ""
            }`}
          >
            <p className="text-2xl font-bold text-ink">{count}</p>
            <p className="text-xs capitalize text-slate-500">{state.replace(/_/g, " ")}</p>
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label htmlFor={`${baseId}-workspace`} className="block text-xs font-medium text-slate-600">Workspace</label>
          <select
            id={`${baseId}-workspace`}
            value={filters.workspace_id || "all"}
            onChange={(e) => updateFilter("workspace_id", e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          >
            <option value="all">All workspaces</option>
            {workspaces.map((w) => (
              <option key={w.workspace_id} value={w.workspace_id}>
                {w.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={`${baseId}-status`} className="block text-xs font-medium text-slate-600">State</label>
          <select
            id={`${baseId}-status`}
            value={filters.status || "all"}
            onChange={(e) => updateFilter("status", e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          >
            <option value="all">All states</option>
            <option value="draft">Draft</option>
            <option value="ingesting">Ingesting</option>
            <option value="ingested">Ingested</option>
            <option value="reviewing">Reviewing</option>
            <option value="reviewed">Reviewed</option>
            <option value="baseline_locked">Baseline locked</option>
            <option value="submitted">Submitted</option>
            <option value="awarded">Awarded</option>
            <option value="rejected">Rejected</option>
            <option value="withdrawn">Withdrawn</option>
          </select>
        </div>
        <div>
          <label htmlFor={`${baseId}-health`} className="block text-xs font-medium text-slate-600">Health</label>
          <select
            id={`${baseId}-health`}
            value={filters.health || "all"}
            onChange={(e) => updateFilter("health", e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          >
            <option value="all">All health</option>
            <option value="healthy">Healthy</option>
            <option value="at_risk">At risk</option>
            <option value="poor">Poor</option>
            <option value="completed">Completed</option>
          </select>
        </div>
        <div>
          <label htmlFor={`${baseId}-jurisdiction`} className="block text-xs font-medium text-slate-600">Jurisdiction</label>
          <input
            id={`${baseId}-jurisdiction`}
            type="text"
            value={filters.jurisdiction || ""}
            onChange={(e) => updateFilter("jurisdiction", e.target.value)}
            placeholder="IN, AE, GB…"
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label htmlFor={`${baseId}-min-value`} className="block text-xs font-medium text-slate-600">Min value</label>
          <input
            id={`${baseId}-min-value`}
            type="number"
            value={filters.min_value || ""}
            onChange={(e) => updateFilter("min_value", e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label htmlFor={`${baseId}-max-value`} className="block text-xs font-medium text-slate-600">Max value</label>
          <input
            id={`${baseId}-max-value`}
            type="number"
            value={filters.max_value || ""}
            onChange={(e) => updateFilter("max_value", e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label htmlFor={`${baseId}-deadline-after`} className="block text-xs font-medium text-slate-600">Deadline after</label>
          <input
            id={`${baseId}-deadline-after`}
            type="date"
            value={filters.deadline_after || ""}
            onChange={(e) => updateFilter("deadline_after", e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label htmlFor={`${baseId}-deadline-before`} className="block text-xs font-medium text-slate-600">Deadline before</label>
          <input
            id={`${baseId}-deadline-before`}
            type="date"
            value={filters.deadline_before || ""}
            onChange={(e) => updateFilter("deadline_before", e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      {/* Project list */}
      <div className="space-y-3">
        {loading && <p className="text-sm text-slate-500">Loading…</p>}
        {!loading && projects.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
            No projects match the selected filters.
          </div>
        )}
        {projects.map((p) => (
          <div
            key={p.opportunity_id}
            className="rounded-xl border border-slate-200 bg-white p-4 transition hover:shadow-sm"
          >
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div className="flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-base font-semibold text-ink">{p.title}</h2>
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                    {p.state_label}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${HEALTH_CLASS[p.health] || "bg-slate-100 text-slate-600"}`}>
                    {HEALTH_LABEL[p.health] || p.health}
                  </span>
                </div>
                <p className="mt-1 text-sm text-slate-600">
                  {p.employer || "No employer"} · {p.jurisdiction} ·{" "}
                  {p.contract_value_minor ? `${p.contract_value_minor} ${p.currency}` : "No value"}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {p.submission_due
                    ? `Deadline ${new Date(p.submission_due).toLocaleDateString()} (${p.days_to_deadline}d)`
                    : "No deadline"}
                  {" · "}
                  {p.document_count} docs · {p.unreviewed_finding_count} open findings
                </p>
                {p.blockers.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {p.blockers.map((b, i) => (
                      <li key={i} className="flex items-center gap-1.5 text-xs text-amber-700">
                        <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                        {b.message}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="flex shrink-0 flex-col gap-2 md:items-end">
                <Link
                  href={p.next_action.link}
                  className="rounded-md bg-ink px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
                >
                  {p.next_action.label}
                </Link>
                <Link
                  href={`/projects/${p.opportunity_id}/state`}
                  className="text-xs text-blue-600 hover:underline"
                >
                  View state
                </Link>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
