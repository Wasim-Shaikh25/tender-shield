"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api, type WorkspaceDetail } from "@/lib/api";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";

export default function AdminWorkspaceDetailPage() {
  const { session } = useSession();
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [ws, setWs] = useState<WorkspaceDetail | null>(null);
  const [plan, setPlan] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!session || !id) return;
    api.adminGetWorkspace(session.token, id)
      .then((w) => { setWs(w); setPlan(w.plan || "free"); })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load workspace"));
  }, [session, id]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }
  if (!session.is_superadmin) {
    return <Alert variant="error" title="Access Denied">Superadmin access required.</Alert>;
  }

  const savePlan = async () => {
    if (!session || !ws) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await api.adminSetWorkspacePlan(session.token, id, plan);
      setWs(updated);
      setMessage("Plan updated successfully.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update plan");
    } finally {
      setLoading(false);
    }
  };

  if (!ws) return <p className="p-6 text-sm text-text-muted">Loading workspace details…</p>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="flex-1">
          <h1 className="text-heading-lg text-text-primary">{ws.name}</h1>
          <p className="text-sm text-text-muted mt-2">Workspace management and configuration</p>
        </div>
        <Link href="/admin" className="inline-flex items-center justify-center gap-2 font-medium transition-colors duration-base focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 whitespace-nowrap h-8 px-3 text-sm rounded-md border border-border-default text-text-primary hover:bg-bg-secondary active:bg-bg-tertiary">
          Back
        </Link>
      </div>

      {/* Alerts */}
      {error && <Alert variant="error" title="Error">{error}</Alert>}
      {message && <Alert variant="success" title="Success">{message}</Alert>}

      {/* Workspace Details */}
      <Card>
        <CardHeader>
          <CardTitle>Workspace Information</CardTitle>
          <CardDescription>Basic workspace details and configuration</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <p className="text-xs font-medium text-text-muted uppercase">Plan</p>
              <p className="text-sm text-text-primary capitalize mt-2">{ws.plan || "free"}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-text-muted uppercase">Country</p>
              <p className="text-sm text-text-primary mt-2">{ws.country || "—"}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-text-muted uppercase">Owner</p>
              <p className="text-sm text-text-primary mt-2">{ws.owner_email}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-text-muted uppercase">Members</p>
              <p className="text-sm text-text-primary mt-2">{ws.member_count}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Plan Management */}
      <Card>
        <CardHeader>
          <CardTitle>Change Plan</CardTitle>
          <CardDescription>Update the workspace subscription plan</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label htmlFor="plan-select" className="block text-sm font-medium text-text-primary mb-2">Select Plan</label>
              <select
                id="plan-select"
                value={plan}
                onChange={(e) => setPlan(e.target.value)}
                disabled={loading}
                className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
              >
                {["free", "pro", "enterprise", "team", "paygo"].map((p) => (
                  <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                ))}
              </select>
            </div>
            <Button variant="primary" size="md" onClick={savePlan} disabled={loading}>
              {loading ? "Saving..." : "Update Plan"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Members */}
      <Card>
        <CardHeader>
          <CardTitle>Members</CardTitle>
          <CardDescription>{ws.members.length} member{ws.members.length !== 1 ? "s" : ""}</CardDescription>
        </CardHeader>
        <CardContent>
          {ws.members.length === 0 ? (
            <p className="text-sm text-text-muted">No members.</p>
          ) : (
            <div className="space-y-3">
              {ws.members.map((m) => (
                <div key={m.user_id} className="flex items-center justify-between p-3 rounded-lg border border-border-default">
                  <p className="text-sm font-medium text-text-primary">{m.user_id}</p>
                  <Badge variant="info" size="sm" className="capitalize">
                    {m.role}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
