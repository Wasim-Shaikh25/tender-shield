"use client";

import { useEffect, useState } from "react";
import { api, type User, type Workspace } from "@/lib/api";
import { useSession } from "@/components/session";

export default function AdminPage() {
  const { session } = useSession();
  const [users, setUsers] = useState<User[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    api.adminUsers(session.token).then((d) => setUsers(d.users)).catch((e) => setError(e.message));
    api.adminWorkspaces(session.token).then((d) => setWorkspaces(d.workspaces)).catch((e) => setError(e.message));
  }, [session]);

  async function toggleSuperadmin(user_id: string, is_superadmin: boolean) {
    if (!session) return;
    try {
      await api.adminSetSuperadmin(session.token, user_id, is_superadmin);
      setUsers((prev) => prev.map((u) => (u.id === user_id ? { ...u, is_superadmin } : u)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    }
  }

  if (!session) return <p className="text-sm text-slate-500">Sign in to view admin console.</p>;
  if (!session.is_superadmin) return <p className="text-sm text-red-600">Superadmin access required.</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-ink">Admin console</h1>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-lg font-semibold text-ink">Workspaces</h2>
        {workspaces.length === 0 ? (
          <p className="text-sm text-slate-500">No workspaces found.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 text-left text-slate-500">
              <tr>
                <th className="py-2">Name</th>
                <th className="py-2">Plan</th>
                <th className="py-2">Country</th>
              </tr>
            </thead>
            <tbody>
              {workspaces.map((w) => (
                <tr key={w.id} className="border-b border-slate-100">
                  <td className="py-2">{w.name}</td>
                  <td className="py-2 capitalize">{w.plan}</td>
                  <td className="py-2">{w.country}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-lg font-semibold text-ink">Users</h2>
        {users.length === 0 ? (
          <p className="text-sm text-slate-500">No users found.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 text-left text-slate-500">
              <tr>
                <th className="py-2">Email</th>
                <th className="py-2">Role</th>
                <th className="py-2">Superadmin</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-slate-100">
                  <td className="py-2">{u.email}</td>
                  <td className="py-2 capitalize">{u.role}</td>
                  <td className="py-2">
                    <input
                      type="checkbox"
                      checked={u.is_superadmin}
                      onChange={(e) => toggleSuperadmin(u.id, e.target.checked)}
                      className="accent-ink"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
