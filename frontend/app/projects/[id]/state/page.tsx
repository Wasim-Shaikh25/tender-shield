"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api, type ProjectState } from "@/lib/api";
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

export default function ProjectStatePage() {
  const { session } = useSession();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [state, setState] = useState<ProjectState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session || !id) return;
    api.getProjectState(session.token, id)
      .then(setState)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load state"))
      .finally(() => setLoading(false));
  }, [session, id]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  if (loading) return <p className="text-sm text-slate-500">Loading state…</p>;
  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!state) return <p className="text-sm text-slate-500">Not found.</p>;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Link href="/projects" className="hover:text-ink">All Projects</Link>
        <span>/</span>
        <span>State</span>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-ink">{state.title}</h1>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700">
            {state.state_label}
          </span>
          <span className={`rounded-full px-3 py-1 text-sm font-medium ${HEALTH_CLASS[state.health] || ""}`}>
            {HEALTH_LABEL[state.health] || state.health}
          </span>
        </div>
        <p className="mt-2 text-sm text-slate-600">
          {state.employer || "No employer"} · {state.jurisdiction} ·{" "}
          {state.contract_value_minor ? `${state.contract_value_minor} ${state.currency}` : "No value"} ·{" "}
          {state.submission_due
            ? `Deadline ${new Date(state.submission_due).toLocaleDateString()} (${state.days_to_deadline}d)`
            : "No deadline"}
        </p>

        <div className="mt-6">
          <h2 className="text-sm font-semibold text-slate-700">Next action</h2>
          <div className="mt-2 flex items-center gap-3">
            <Link
              href={state.next_action.link}
              className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              {state.next_action.label}
            </Link>
            <Link
              href={`/opportunities/${id}`}
              className="text-sm text-blue-600 hover:underline"
            >
              Open opportunity
            </Link>
          </div>
        </div>

        {state.blockers.length > 0 && (
          <div className="mt-6">
            <h2 className="text-sm font-semibold text-slate-700">Blockers</h2>
            <ul className="mt-2 space-y-2">
              {state.blockers.map((b, i) => (
                <li key={i} className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
                  {b.message}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-6">
          <h2 className="text-sm font-semibold text-slate-700">Completed gates</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            {state.completed_gates.length === 0 && (
              <span className="text-sm text-slate-500">None yet.</span>
            )}
            {state.completed_gates.map((g) => (
              <span
                key={g}
                className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700"
              >
                {g.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-lg bg-slate-50 p-3">
            <p className="text-lg font-bold text-ink">{state.document_count}</p>
            <p className="text-xs text-slate-500">Documents</p>
          </div>
          <div className="rounded-lg bg-slate-50 p-3">
            <p className="text-lg font-bold text-ink">{state.finding_count}</p>
            <p className="text-xs text-slate-500">Findings</p>
          </div>
          <div className="rounded-lg bg-slate-50 p-3">
            <p className="text-lg font-bold text-ink">{state.unreviewed_finding_count}</p>
            <p className="text-xs text-slate-500">Open findings</p>
          </div>
          <div className="rounded-lg bg-slate-50 p-3">
            <p className="text-lg font-bold text-ink">{state.baseline_count}</p>
            <p className="text-xs text-slate-500">Baselines</p>
          </div>
        </div>
      </div>
    </div>
  );
}
