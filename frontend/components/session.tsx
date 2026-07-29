"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { api, type Tokens, type Workspace } from "@/lib/api";

// Access token is kept in memory only. Refresh token lives in an httpOnly cookie.
// On reload we call /auth/refresh to get a new access token.
type Session = {
  token: string;
  role: string;
  workspaceId: string;
  is_superadmin?: boolean;
} | null;

type Ctx = {
  session: Session;
  workspaces: Workspace[];
  activeWorkspace: Workspace | null;
  loading: boolean;
  signIn: (t: Tokens) => void;
  signOut: () => void;
  refreshSession: () => Promise<boolean>;
  switchWorkspace: (id: string) => Promise<void>;
};

const SessionContext = createContext<Ctx>({
  session: null,
  workspaces: [],
  activeWorkspace: null,
  loading: true,
  signIn: () => {},
  signOut: () => {},
  refreshSession: async () => false,
  switchWorkspace: async () => {},
});

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);

  const applyTokens = (t: Tokens, all?: Workspace[]) => {
    if (t.mfa_required) return; // handled by login page
    setSession({
      token: t.access_token,
      role: t.role,
      workspaceId: t.workspace_id,
      is_superadmin: t.is_superadmin,
    });
    const match = (all ?? workspaces).find((w) => w.id === t.workspace_id);
    if (match) {
      setWorkspaces((prev) => (prev.length ? prev : all ?? prev));
    }
  };

  const loadWorkspaces = async (token: string) => {
    try {
      const list = await api.listWorkspaces(token);
      setWorkspaces(list);
      return list;
    } catch {
      return [];
    }
  };

  const refreshSession = async () => {
    try {
      const t = await api.refresh();
      const all = await loadWorkspaces(t.access_token);
      applyTokens(t, all);
      return true;
    } catch {
      setSession(null);
      setWorkspaces([]);
      return false;
    }
  };

  useEffect(() => {
    refreshSession().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const signIn = async (t: Tokens) => {
    const all = await loadWorkspaces(t.access_token);
    applyTokens(t, all);
  };

  const signOut = async () => {
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api"}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } catch {
      // ignore
    }
    setSession(null);
    setWorkspaces([]);
  };

  const switchWorkspace = async (workspace_id: string) => {
    if (!session) return;
    const t = await api.switchWorkspace(session.token, workspace_id);
    const all = await loadWorkspaces(t.access_token);
    applyTokens(t, all);
  };

  const activeWorkspace = workspaces.find((w) => w.id === session?.workspaceId) ?? null;

  return (
    <SessionContext.Provider
      value={{
        session,
        workspaces,
        activeWorkspace,
        loading,
        signIn,
        signOut,
        refreshSession,
        switchWorkspace,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export const useSession = () => useContext(SessionContext);
