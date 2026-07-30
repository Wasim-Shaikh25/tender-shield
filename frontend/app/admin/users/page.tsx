"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type User } from "@/lib/api";
import { useSession } from "@/components/session";

export default function AdminUsersPage() {
  const { session } = useSession();
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    if (!session) return;
    try {
      const r = await api.adminSearchUsers(session.token, query || undefined);
      setUsers(r.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load users");
    }
  };

  useEffect(() => {
    if (!session) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }
  if (!session.is_superadmin) {
    return <p className="p-6 text-sm text-red-600">Superadmin access required.</p>;
  }

  const suspend = async (id: string) => {
    if (!session) return;
    await api.adminSuspendUser(session.token, id);
    load();
  };

  const unsuspend = async (id: string) => {
    if (!session) return;
    await api.adminUnsuspendUser(session.token, id);
    load();
  };

  const deleteUser = async (id: string) => {
    if (!session || !confirm("Delete this user and all owned workspaces?")) return;
    await api.adminDeleteUser(session.token, id);
    load();
  };

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold text-ink">Users</h1>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <form onSubmit={(e) => { e.preventDefault(); load(); }} className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by email, phone, org, workspace"
          className="w-full max-w-md rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <button type="submit" className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white">Search</button>
      </form>

      <table className="w-full text-sm">
        <thead className="border-b border-slate-200 text-left text-slate-500">
          <tr>
            <th className="py-2">Email</th>
            <th className="py-2">Org</th>
            <th className="py-2">Verified</th>
            <th className="py-2">Status</th>
            <th className="py-2">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {users.map((u) => (
            <tr key={u.user_id}>
              <td className="py-2"><Link href={`/admin/users/${u.user_id}`} className="text-indigo-600 hover:underline">{u.email}</Link></td>
              <td className="py-2">{u.org_name || "—"}</td>
              <td className="py-2">{u.email_verified ? "E" : "—"}/{u.mobile_verified ? "M" : "—"}</td>
              <td className="py-2">{u.suspended_at ? "Suspended" : "Active"}</td>
              <td className="py-2 space-x-2">
                {u.suspended_at ? (
                  <button onClick={() => unsuspend(u.user_id)} className="text-indigo-600 hover:underline">Unsuspend</button>
                ) : (
                  <button onClick={() => suspend(u.user_id)} className="text-amber-600 hover:underline">Suspend</button>
                )}
                <button onClick={() => deleteUser(u.user_id)} className="text-red-600 hover:underline">Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
