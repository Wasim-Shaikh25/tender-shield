"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type AuditLogEntry } from "@/lib/api";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { KeyValueSummary } from "@/components/json-summary";

export default function AdminAuditLogPage() {
  const { session } = useSession();
  const router = useRouter();
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    if (!session) return;
    setLoading(true);
    try {
      const r = await api.adminAuditLog(session.token, workspaceId || "00000000-0000-0000-0000-000000000000");
      setLogs(r);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load logs");
    } finally {
      setLoading(false);
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
    return <Alert variant="error" title="Access Denied">Superadmin access required.</Alert>;
  }

  const getActionColor = (action: string): "info" | "warning" | "error" | "success" | "secondary" => {
    if (action.includes("delete") || action.includes("remove")) return "error";
    if (action.includes("create") || action.includes("add")) return "success";
    if (action.includes("update") || action.includes("change")) return "info";
    return "secondary";
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-heading-lg text-text-primary">Audit Log</h1>
        <p className="text-sm text-text-muted mt-2">View system activity and user actions</p>
      </div>

      {/* Alerts */}
      {error && <Alert variant="error" title="Error">{error}</Alert>}

      {/* Search/Filter */}
      <Card>
        <CardHeader>
          <CardTitle>Filter Logs</CardTitle>
          <CardDescription>Search logs by workspace ID (leave empty for global logs)</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={(e) => { e.preventDefault(); load(); }} className="flex gap-2">
            <input
              value={workspaceId}
              onChange={(e) => setWorkspaceId(e.target.value)}
              placeholder="Workspace ID (optional)"
              className="flex-1 rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
              disabled={loading}
            />
            <Button variant="primary" size="md" type="submit" disabled={loading}>
              {loading ? "Searching..." : "Search"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Audit Log Entries */}
      <Card>
        <CardHeader>
          <CardTitle>Activity Log</CardTitle>
          <CardDescription>{logs.length} log entr{logs.length !== 1 ? "ies" : "y"}</CardDescription>
        </CardHeader>
        <CardContent>
          {logs.length === 0 ? (
            <p className="text-sm text-text-muted py-4">No audit log entries found.</p>
          ) : (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {logs.map((l) => (
                <div key={l.id} className="p-3 rounded-lg border border-border-default hover:bg-bg-secondary transition-colors">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <p className="text-sm font-medium text-text-primary">{l.action}</p>
                      <p className="text-xs text-text-muted mt-1">
                        {l.object_type}:{l.object_id ? l.object_id.slice(0, 8) : "unknown"}…
                      </p>
                    </div>
                    <Badge variant={getActionColor(l.action)} size="sm" className="capitalize">
                      {l.action.replace(/_/g, " ")}
                    </Badge>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-text-muted">
                    <span>Actor: {l.actor_user_id ?? "system"}</span>
                    <span>•</span>
                    <span>{l.at ?? "—"}</span>
                  </div>
                  {l.detail && (
                    <KeyValueSummary
                      data={l.detail}
                      title="Details"
                      maxPreviewKeys={4}
                      rawLabel="Raw detail"
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
