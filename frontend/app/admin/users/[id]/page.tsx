"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, type UserDetail } from "@/lib/api";
import { useSession } from "@/components/session";

export default function AdminUserDetailPage() {
  const { session } = useSession();
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [user, setUser] = useState<UserDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!session || !id) return;
    api.adminGetUser(session.token, id)
      .then(setUser)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load user"));
  }, [session, id]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }
  if (!session.is_superadmin) {
    return <p className="p-6 text-sm text-red-600">Superadmin access required.</p>;
  }

  const act = async (fn: () => Promise<unknown>, success: string) => {
    if (!session) return;
    setError(null);
    setMessage(null);
    try {
      await fn();
      setMessage(success);
      api.adminGetUser(session.token, id).then(setUser);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    }
  };

  if (!user) return <p className="p-6 text-sm text-slate-500">Loading...</p>;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold text-ink">{user.email}</h1>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {message && <p className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">{message}</p>}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <div><p className="text-xs text-slate-500">Email</p><p className="text-sm font-medium">{user.email} {user.email_verified && "(verified)"}</p></div>
          <div><p className="text-xs text-slate-500">Phone</p><p className="text-sm font-medium">{user.phone} {user.mobile_verified && "(verified)"}</p></div>
          <div><p className="text-xs text-slate-500">Organisation</p><p className="text-sm font-medium">{user.org_name}</p></div>
          <div><p className="text-xs text-slate-500">City</p><p className="text-sm font-medium">{user.city}</p></div>
          <div><p className="text-xs text-slate-500">Plan</p><p className="text-sm font-medium capitalize">{user.plan || "free"}</p></div>
          <div><p className="text-xs text-slate-500">DOB</p><p className="text-sm font-medium">{user.dob ?? "—"}</p></div>
          <div><p className="text-xs text-slate-500">Created</p><p className="text-sm font-medium">{user.created_at ?? "—"}</p></div>
        </div>

        <div className="mt-6 flex gap-3">
          {user.suspended_at ? (
            <button onClick={() => act(() => api.adminUnsuspendUser(session.token, id), "User unsuspended")} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white">Unsuspend</button>
          ) : (
            <button onClick={() => act(() => api.adminSuspendUser(session.token, id), "User suspended")} className="rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white">Suspend</button>
          )}
          <button onClick={() => act(() => api.adminDeleteUser(session.token, id), "User deleted")} className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white">Delete</button>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-lg font-semibold text-ink">Workspaces</h2>
        {user.workspaces?.length ? (
          <ul className="divide-y divide-slate-100">
            {user.workspaces.map((w) => (
              <li key={w.workspace_id} className="flex items-center justify-between py-2">
                <span className="text-sm font-medium text-slate-900">{w.name}</span>
                <div className="flex items-center gap-3">
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs capitalize text-slate-600">{w.plan || "free"}</span>
                  <span className="text-xs text-slate-500">{w.role}</span>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">No workspaces.</p>
        )}
      </section>
    </div>
  );
}
