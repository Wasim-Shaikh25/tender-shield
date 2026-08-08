"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, type UserDetail } from "@/lib/api";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";

export default function AdminUserDetailPage() {
  const { session } = useSession();
  const { id } = useParams<{ id: string }>();
  const [user, setUser] = useState<UserDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!session || !id) return;
    api.adminGetUser(session.token, id)
      .then(setUser)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load user"));
  }, [session, id]);

  if (!session) {
    return null;
  }
  if (!session.is_superadmin) {
    return <Alert variant="error" title="Access Denied">Superadmin access required.</Alert>;
  }

  const act = async (fn: () => Promise<unknown>, success: string) => {
    if (!session) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      await fn();
      setMessage(success);
      await api.adminGetUser(session.token, id).then(setUser);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setLoading(false);
    }
  };

  if (!user) return <p className="p-6 text-sm text-text-muted">Loading user details…</p>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="flex-1">
          <h1 className="text-heading-lg text-text-primary">{user.email}</h1>
          <p className="text-sm text-text-muted mt-2">User profile and account details</p>
        </div>
        <Link href="/admin/users" className="inline-flex items-center justify-center gap-2 font-medium transition-colors duration-base focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 whitespace-nowrap h-8 px-3 text-sm rounded-md border border-border-default text-text-primary hover:bg-bg-secondary active:bg-bg-tertiary">
          Back
        </Link>
      </div>

      {/* Alerts */}
      {error && <Alert variant="error" title="Error">{error}</Alert>}
      {message && <Alert variant="success" title="Success">{message}</Alert>}

      {/* User Details */}
      <Card>
        <CardHeader>
          <CardTitle>Account Information</CardTitle>
          <CardDescription>Personal and account details</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <p className="text-xs font-medium text-text-muted uppercase">Email</p>
              <div className="flex items-center gap-2 mt-2">
                <p className="text-sm text-text-primary">{user.email}</p>
                {user.email_verified && <Badge variant="success" size="sm">Verified</Badge>}
              </div>
            </div>
            <div>
              <p className="text-xs font-medium text-text-muted uppercase">Phone</p>
              <div className="flex items-center gap-2 mt-2">
                <p className="text-sm text-text-primary">{user.phone || "—"}</p>
                {user.mobile_verified && <Badge variant="success" size="sm">Verified</Badge>}
              </div>
            </div>
            <div>
              <p className="text-xs font-medium text-text-muted uppercase">Organization</p>
              <p className="text-sm text-text-primary mt-2">{user.org_name || "—"}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-text-muted uppercase">City</p>
              <p className="text-sm text-text-primary mt-2">{user.city || "—"}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-text-muted uppercase">Plan</p>
              <p className="text-sm text-text-primary capitalize mt-2">{user.plan || "free"}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-text-muted uppercase">Date of Birth</p>
              <p className="text-sm text-text-primary mt-2">{user.dob || "—"}</p>
            </div>
            <div className="sm:col-span-2">
              <p className="text-xs font-medium text-text-muted uppercase">Created</p>
              <p className="text-sm text-text-primary mt-2">{user.created_at || "—"}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Account Actions</CardTitle>
          <CardDescription>Manage this user account</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3 flex-wrap">
            {user.suspended_at ? (
              <Button
                variant="primary"
                size="md"
                onClick={() => act(() => api.adminUnsuspendUser(session.token, id), "User unsuspended")}
                disabled={loading}
              >
                {loading ? "Processing..." : "Unsuspend User"}
              </Button>
            ) : (
              <Button
                variant="outline"
                size="md"
                onClick={() => act(() => api.adminSuspendUser(session.token, id), "User suspended")}
                disabled={loading}
              >
                {loading ? "Processing..." : "Suspend User"}
              </Button>
            )}
            <Button
              variant="destructive"
              size="md"
              onClick={() => act(() => api.adminDeleteUser(session.token, id), "User deleted")}
              disabled={loading}
            >
              {loading ? "Processing..." : "Delete User"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Workspaces */}
      <Card>
        <CardHeader>
          <CardTitle>Workspaces</CardTitle>
          <CardDescription>{user.workspaces?.length || 0} workspace{(user.workspaces?.length ?? 0) !== 1 ? "s" : ""}</CardDescription>
        </CardHeader>
        <CardContent>
          {user.workspaces?.length ? (
            <div className="space-y-3">
              {user.workspaces.map((w) => (
                <div key={w.workspace_id} className="flex items-center justify-between p-3 rounded-lg border border-border-default hover:bg-bg-secondary transition-colors">
                  <div>
                    <p className="text-sm font-medium text-text-primary">{w.name}</p>
                    <p className="text-xs text-text-muted mt-1">ID: {w.workspace_id}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" size="sm" className="capitalize">
                      {w.plan || "free"}
                    </Badge>
                    <Badge variant="info" size="sm" className="capitalize">
                      {w.role}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-text-muted">No workspaces.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
