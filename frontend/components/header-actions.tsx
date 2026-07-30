"use client";

import Link from "next/link";
import { useSession } from "@/components/session";

export function HeaderActions() {
  const { session, workspaces, activeWorkspace, switchWorkspace, signOut, loading } = useSession();

  if (loading) return <span className="text-slate-400">…</span>;

  if (!session) {
    return (
      <Link href="/login" className="rounded-md bg-ink px-3 py-1.5 text-white hover:opacity-90">
        Sign in
      </Link>
    );
  }

  return (
    <div className="flex items-center gap-3">
      {workspaces.length > 1 ? (
        <select
          value={activeWorkspace?.workspace_id ?? ""}
          onChange={(e) => switchWorkspace(e.target.value)}
          className="rounded-md border border-slate-300 px-2 py-1 text-sm outline-none focus:border-ink"
        >
          {workspaces.map((w) => (
            <option key={w.workspace_id} value={w.workspace_id}>
              {w.name} · {w.plan}
            </option>
          ))}
        </select>
      ) : activeWorkspace ? (
        <span className="text-slate-700">{activeWorkspace.name}</span>
      ) : null}
      {session.is_superadmin && (
        <Link href="/admin" className="text-slate-600 hover:text-ink">Admin</Link>
      )}
      <Link href="/settings" className="text-slate-600 hover:text-ink">Settings</Link>
      <Link href="/billing" className="text-slate-600 hover:text-ink">Billing</Link>
      <button
        onClick={signOut}
        className="rounded-md border border-slate-300 px-3 py-1.5 text-slate-700 hover:bg-white"
      >
        Sign out
      </button>
    </div>
  );
}
