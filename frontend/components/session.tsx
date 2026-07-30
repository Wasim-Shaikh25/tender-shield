"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { api, type Tokens, type Workspace } from "@/lib/api";

const NO_WORKSPACE = "00000000-0000-0000-0000-000000000000";

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
  signIn: (t: Tokens) => Promise<Workspace[]>;
  signOut: () => void;
  refreshSession: () => Promise<boolean>;
  switchWorkspace: (id: string) => Promise<void>;
  createWorkspace: (name: string, country?: string) => Promise<string>;
};

const SessionContext = createContext<Ctx>({
  session: null,
  workspaces: [],
  activeWorkspace: null,
  loading: true,
  signIn: async () => [],
  signOut: () => {},
  refreshSession: async () => false,
  switchWorkspace: async () => {},
  createWorkspace: async () => "",
});

function isNoWorkspace(id: string | undefined) {
  return !id || id === NO_WORKSPACE;
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session>(null);
  const tokenRef = useRef<string | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);

  const applyTokens = (t: Tokens, all?: Workspace[]) => {
    if (t.mfa_required) return; // handled by login page
    tokenRef.current = t.access_token;
    setSession({
      token: t.access_token,
      role: t.role,
      workspaceId: t.workspace_id,
      is_superadmin: t.is_superadmin,
    });
    if (all !== undefined) {
      setWorkspaces(all);
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
    return all;
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
    tokenRef.current = null;
    setSession(null);
    setWorkspaces([]);
  };

  const switchWorkspace = async (workspace_id: string) => {
    const token = tokenRef.current;
    if (!token) return;
    const t = await api.switchWorkspace(token, workspace_id);
    const all = await loadWorkspaces(t.access_token);
    applyTokens(t, all);
  };

  const createWorkspace = async (name: string, country = "IN") => {
    const token = tokenRef.current;
    if (!token) throw new Error("not_signed_in");
    const created = await api.createWorkspace(token, { name, country });
    const workspaceId = created.workspace_id;
    await switchWorkspace(workspaceId);
    return workspaceId;
  };

  const activeWorkspace =
    workspaces.find((w) => w.workspace_id === session?.workspaceId) ?? null;

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
        createWorkspace,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export const useSession = () => useContext(SessionContext);
export { isNoWorkspace };
