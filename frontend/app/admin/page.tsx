"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type AdminDashboard, type User, type Workspace } from "@/lib/api";
import { useSession } from "@/components/session";

export default function AdminDashboardPage() {
  const { session } = useSession();
  const router = useRouter();
  const [dashboard, setDashboard] = useState<AdminDashboard | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    if (!session.is_superadmin) return;
    api.adminDashboard(session.token).then(setDashboard).catch((e) => setError(e.message));
    api.adminSearchUsers(session.token).then((r) => setUsers(r.items)).catch(() => {});
    api.adminWorkspaces(session.token).then(setWorkspaces).catch(() => {});
  }, [session]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }
  if (!session.is_superadmin) {
    return <p className="p-6 text-sm text-red-600">Superadmin access required.</p>;
  }

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold text-ink">Admin dashboard</h1>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {dashboard && (
        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {([
            ["Total users", dashboard.total_users],
            ["Suspended users", dashboard.suspended_users],
            ["Active workspaces", dashboard.active_workspaces],
            ["Pending verifications", dashboard.pending_verifications],
          ] as Array<[string, number]>).map(([label, value]) => (
            <div key={label} className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-sm text-slate-500">{label}</p>
              <p className="text-2xl font-semibold text-ink">{value}</p>
            </div>
          ))}
        </section>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-lg font-semibold text-ink">Recent users</h2>
        <ul className="divide-y divide-slate-100">
          {users.slice(0, 10).map((u) => (
            <li key={u.user_id} className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-medium text-slate-900">{u.email}</p>
                <p className="text-xs text-slate-500">{u.org_name || "—"}</p>
              </div>
              <Link href={`/admin/users/${u.user_id}`} className="text-sm text-indigo-600 hover:underline">
                View
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-lg font-semibold text-ink">Workspaces</h2>
        <ul className="divide-y divide-slate-100">
          {workspaces.slice(0, 10).map((w) => (
            <li key={w.workspace_id} className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-medium text-slate-900">{w.name}</p>
                <p className="text-xs text-slate-500">{w.plan || "free"}</p>
              </div>
              <Link href={`/admin/workspaces/${w.workspace_id}`} className="text-sm text-indigo-600 hover:underline">
                View
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <div className="flex gap-3">
        <Link href="/admin/users" className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white">All users</Link>
        <Link href="/admin/audit-log" className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Audit log</Link>
      </div>
    </div>
  );
}
