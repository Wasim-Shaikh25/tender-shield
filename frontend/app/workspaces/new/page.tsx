"use client";

// R-011 §B.5/B.6: a user with zero workspace memberships (e.g. their last
// membership was removed, or a workspace-less signup path) holds a
// workspace-less token rather than being locked out — RequireAuth routes
// them here instead of a dead-end 401. Creating a workspace makes them its
// owner (AuthService._create_workspace_and_owner); switching into it right
// after re-issues real tokens, since the create response itself carries no
// tokens.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useSession } from "@/components/session";
import { RequireAuth } from "@/components/require-auth";
import { loadRefreshToken } from "@/lib/auth-client";

export default function NewWorkspacePage() {
  return (
    <RequireAuth>
      <NewWorkspaceForm />
    </RequireAuth>
  );
}

function NewWorkspaceForm() {
  const { session, signIn } = useSession();
  const router = useRouter();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!session || !name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const workspace = await api.createWorkspace(session.token, name.trim());
      const refreshToken = loadRefreshToken();
      if (refreshToken) {
        const tokens = await api.switchWorkspace(session.token, workspace.workspace_id, refreshToken);
        signIn(tokens);
      }
      router.replace("/opportunities");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create the workspace");
    } finally {
      setBusy(false);
    }
  }

  if (!session) return null;

  return (
    <div className="mx-auto max-w-md">
      <div className="rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-ink">Create a workspace</h1>
        <p className="mt-1 text-sm text-slate-500">
          You&rsquo;re not a member of any workspace yet. Create one to get started, or ask a
          colleague for an invitation link.
        </p>

        <form onSubmit={submit} className="mt-6 space-y-4">
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700">Workspace name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Acme Infra Pvt Ltd"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-ink focus:ring-1 focus:ring-ink"
            />
          </label>

          {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

          <button
            disabled={busy || !name.trim()}
            className="w-full rounded-md bg-ink py-2.5 font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Creating…" : "Create workspace"}
          </button>
        </form>
      </div>
    </div>
  );
}
