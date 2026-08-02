"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/components/session";
import { api, type Workspace } from "@/lib/api";

export default function AdvisorPage() {
  const { session, workspaces, switchWorkspace, activeWorkspace } = useSession();
  const router = useRouter();
  const [clientWorkspaces, setClientWorkspaces] = useState<Workspace[]>([]);
  const [allWorkspaces, setAllWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) {
      if (typeof window !== "undefined") router.replace("/login");
      return;
    }
    api.listWorkspaces(session.token)
      .then((r) => setClientWorkspaces(r))
      .catch(() => setClientWorkspaces([]));
    if (session.is_superadmin) {
      api.adminWorkspaces(session.token)
        .then((r) => setAllWorkspaces(r))
        .catch(() => setAllWorkspaces([]));
    }
  }, [session, router]);

  const switchTo = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      await switchWorkspace(id);
      router.push("/opportunities");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to switch workspace");
    } finally {
      setLoading(false);
    }
  };

  if (!session) return null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-ink">Advisor workspace switcher</h1>
      {activeWorkspace && (
        <p className="text-sm text-slate-600">Active workspace: <span className="font-medium text-ink">{activeWorkspace.name}</span></p>
      )}
      {error && <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink">Your client workspaces</h2>
        {clientWorkspaces.length === 0 ? (
          <p className="text-sm text-slate-500">No workspaces assigned.</p>
        ) : (
          <ul className="space-y-2">
            {clientWorkspaces.map((w) => (
              <li key={w.workspace_id} className="flex items-center justify-between rounded-md border border-slate-200 bg-slate-50 p-3">
                <div>
                  <p className="font-medium text-ink">{w.name}</p>
                  <p className="text-xs text-slate-500">{w.role} · {w.country ?? "-"}</p>
                </div>
                <button
                  onClick={() => switchTo(w.workspace_id)}
                  disabled={loading || (activeWorkspace?.workspace_id === w.workspace_id)}
                  className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
                >
                  {activeWorkspace?.workspace_id === w.workspace_id ? "Active" : "Switch"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {session.is_superadmin && (
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-ink">Admin workspace switcher</h2>
          {allWorkspaces.length === 0 ? (
            <p className="text-sm text-slate-500">No workspaces found.</p>
          ) : (
            <ul className="space-y-2">
              {allWorkspaces.map((w) => (
                <li key={w.workspace_id} className="flex items-center justify-between rounded-md border border-slate-200 bg-slate-50 p-3">
                  <div>
                    <p className="font-medium text-ink">{w.name}</p>
                    <p className="text-xs text-slate-500">{w.country ?? "-"}</p>
                  </div>
                  <button
                    onClick={() => switchTo(w.workspace_id)}
                    disabled={loading || (activeWorkspace?.workspace_id === w.workspace_id)}
                    className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
                  >
                    {activeWorkspace?.workspace_id === w.workspace_id ? "Active" : "Switch"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
