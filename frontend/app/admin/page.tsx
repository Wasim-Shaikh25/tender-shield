"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type AdminDashboard, type User, type Workspace } from "@/lib/api";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";

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
    return <Alert variant="error" title="Access Denied">Superadmin access required.</Alert>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-heading-lg text-text-primary">Admin Dashboard</h1>
        <p className="text-sm text-text-muted mt-2">Manage users, workspaces, and platform settings</p>
      </div>

      {/* Alerts */}
      {error && <Alert variant="error" title="Error">{error}</Alert>}

      {/* Metrics */}
      {dashboard && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {([
            ["Total Users", dashboard.total_users, "info"],
            ["Suspended Users", dashboard.suspended_users, "warning"],
            ["Active Workspaces", dashboard.active_workspaces, "success"],
            ["Pending Verifications", dashboard.pending_verifications, "warning"],
          ] as Array<[string, number, string]>).map(([label, value, color]) => (
            <Card key={label}>
              <CardContent className="pt-6">
                <p className="text-sm text-text-muted mb-2">{label}</p>
                <p className="text-3xl font-bold text-text-primary">{value}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Recent Users */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Users</CardTitle>
          <CardDescription>Latest {Math.min(users.length, 10)} user registrations</CardDescription>
        </CardHeader>
        <CardContent>
          {users.length === 0 ? (
            <p className="text-sm text-text-muted">No users yet.</p>
          ) : (
            <div className="space-y-3">
              {users.slice(0, 10).map((u) => (
                <div key={u.user_id} className="flex items-center justify-between p-3 rounded-lg border border-border-default hover:bg-bg-secondary transition-colors">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-text-primary">{u.email}</p>
                    <p className="text-xs text-text-muted mt-1">{u.org_name || "No organization"}</p>
                  </div>
                  <Button variant="outline" size="sm" asChild>
                    <Link href={`/admin/users/${u.user_id}`}>View</Link>
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Workspaces */}
      <Card>
        <CardHeader>
          <CardTitle>Workspaces</CardTitle>
          <CardDescription>{Math.min(workspaces.length, 10)} of {workspaces.length} workspaces</CardDescription>
        </CardHeader>
        <CardContent>
          {workspaces.length === 0 ? (
            <p className="text-sm text-text-muted">No workspaces yet.</p>
          ) : (
            <div className="space-y-3">
              {workspaces.slice(0, 10).map((w) => (
                <div key={w.workspace_id} className="flex items-center justify-between p-3 rounded-lg border border-border-default hover:bg-bg-secondary transition-colors">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-text-primary">{w.name}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant="secondary" size="sm" className="capitalize">
                        {w.plan || "free"}
                      </Badge>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" asChild>
                    <Link href={`/admin/workspaces/${w.workspace_id}`}>View</Link>
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Navigation */}
      <Card>
        <CardHeader>
          <CardTitle>Admin Tools</CardTitle>
          <CardDescription>Access admin management pages</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button variant="primary" size="md" asChild>
              <Link href="/admin/users">All Users</Link>
            </Button>
            <Button variant="outline" size="md" asChild>
              <Link href="/admin/audit-log">Audit Log</Link>
            </Button>
            <Button variant="outline" size="md" asChild>
              <Link href="/admin/coupons">Coupons</Link>
            </Button>
            <Button variant="outline" size="md" asChild>
              <Link href="/admin/support">Support</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
