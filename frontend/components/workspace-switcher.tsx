"use client";

// R-011 §B.4. Hidden entirely for a single-workspace user (A8) — a switcher
// with one option is noise. Switching re-issues tokens scoped to the chosen
// workspace (auth's own membership check, not a client-side selection —
// the workspace claim is what RLS binds to) and calls the SAME `signIn`
// every login flow uses: persists the rotated refresh token and swaps in a
// new `session` object. Every protected page's own data-fetching effect
// already depends on `session` (`useEffect(..., [session])`), so switching
// naturally triggers a refetch under the new workspace — this codebase has
// no shared query cache to separately invalidate.

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type WorkspaceSummary } from "@/lib/api";
import { useSession } from "@/components/session";
import { loadRefreshToken } from "@/lib/auth-client";

export function WorkspaceSwitcher() {
  const { session, signIn } = useSession();
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[] | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!session) {
      setWorkspaces(null);
      return;
    }
    api.listWorkspaces(session.token).then(setWorkspaces).catch(() => setWorkspaces(null));
  }, [session]);

  useEffect(() => {
    function onClickAway(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickAway);
    return () => document.removeEventListener("mousedown", onClickAway);
  }, []);

  if (!session || !workspaces || workspaces.length < 2) return null;

  const current = workspaces.find((w) => w.is_current) ?? workspaces[0];

  async function switchTo(workspaceId: string) {
    if (!session || workspaceId === current.workspace_id) {
      setOpen(false);
      return;
    }
    const refreshToken = loadRefreshToken();
    if (!refreshToken) {
      setOpen(false);
      return;
    }
    setBusy(true);
    try {
      const tokens = await api.switchWorkspace(session.token, workspaceId, refreshToken);
      signIn(tokens);
      setOpen(false);
      router.replace("/opportunities");
    } catch {
      // Left in place — a failed switch (e.g. membership revoked mid-flight)
      // just leaves the caller in their current workspace, no crash.
    } finally {
      setBusy(false);
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        disabled={busy}
        className="flex items-center gap-2 rounded-md border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:border-ink disabled:opacity-50"
      >
        <span className="font-medium text-ink">{current.name}</span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs uppercase text-slate-500">
          {current.plan}
        </span>
        <span className="text-slate-400">▾</span>
      </button>
      {open && (
        <ul className="absolute right-0 z-20 mt-1 w-64 rounded-md border border-slate-200 bg-white py-1 text-sm shadow-lg">
          {workspaces.map((w) => (
            <li key={w.workspace_id}>
              <button
                onClick={() => switchTo(w.workspace_id)}
                className={`flex w-full items-center justify-between px-3 py-2 text-left hover:bg-slate-50 ${
                  w.is_current ? "font-semibold text-ink" : "text-slate-700"
                }`}
              >
                <span>{w.name}</span>
                <span className="text-xs uppercase text-slate-400">{w.role}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
