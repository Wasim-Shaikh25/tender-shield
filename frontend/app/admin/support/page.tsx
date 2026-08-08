"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type SupportTicket } from "@/lib/api";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";

export default function AdminSupportPage() {
  const { session } = useSession();
  const router = useRouter();
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    if (!session) return;
    setLoading(true);
    try {
      const list = await api.adminListSupportTickets(
        session.token,
        workspaceId || "00000000-0000-0000-0000-000000000000",
        category || undefined,
        status || undefined
      );
      setTickets(list);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load tickets");
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

  const setTicketStatus = async (id: string, newStatus: string) => {
    if (!session) return;
    setLoading(true);
    try {
      await api.adminSetSupportTicketStatus(session.token, workspaceId || "00000000-0000-0000-0000-000000000000", id, newStatus);
      await load();
    } finally {
      setLoading(false);
    }
  };

  const getCategoryColor = (cat: string): "primary" | "secondary" | "success" | "warning" | "error" | "info" => {
    switch (cat) {
      case "billing": return "warning";
      case "technical": return "error";
      case "feature": return "info";
      default: return "secondary";
    }
  };

  const getStatusColor = (stat: string): "primary" | "secondary" | "success" | "warning" | "error" | "info" => {
    switch (stat) {
      case "open": return "info";
      case "in_progress": return "warning";
      case "resolved": return "success";
      case "closed": return "secondary";
      default: return "secondary";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-heading-lg text-text-primary">Support Tickets</h1>
        <p className="text-sm text-text-muted mt-2">View and manage all support tickets</p>
      </div>

      {/* Alerts */}
      {error && <Alert variant="error" title="Error">{error}</Alert>}

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Filter Tickets</CardTitle>
          <CardDescription>Search and filter support tickets</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={(e) => { e.preventDefault(); load(); }} className="flex flex-wrap gap-2">
            <input
              value={workspaceId}
              onChange={(e) => setWorkspaceId(e.target.value)}
              placeholder="Workspace ID (optional)"
              className="rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
              disabled={loading}
            />
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
              disabled={loading}
            >
              <option value="">All categories</option>
              {["billing", "technical", "feature", "other"].map((c) => (
                <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
              ))}
            </select>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
              disabled={loading}
            >
              <option value="">All statuses</option>
              {["open", "in_progress", "resolved", "closed"].map((s) => (
                <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1).replace("_", " ")}</option>
              ))}
            </select>
            <Button variant="primary" size="md" type="submit" disabled={loading}>
              {loading ? "Filtering..." : "Filter"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Tickets List */}
      <Card>
        <CardHeader>
          <CardTitle>Support Tickets</CardTitle>
          <CardDescription>{tickets.length} ticket{tickets.length !== 1 ? "s" : ""}</CardDescription>
        </CardHeader>
        <CardContent>
          {tickets.length === 0 ? (
            <p className="text-sm text-text-muted py-4">No tickets found.</p>
          ) : (
            <div className="space-y-3">
              {tickets.map((t) => (
                <div key={t.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-lg border border-border-default hover:bg-bg-secondary transition-colors">
                  <div className="flex-1">
                    <p className="font-medium text-text-primary">{t.title}</p>
                    <div className="flex items-center gap-2 mt-2 flex-wrap">
                      <Badge variant={getCategoryColor(t.category)} size="sm" className="capitalize">
                        {t.category}
                      </Badge>
                      <Badge variant={getStatusColor(t.status)} size="sm" className="capitalize">
                        {t.status?.replace("_", " ")}
                      </Badge>
                    </div>
                  </div>
                  <select
                    value={t.status}
                    onChange={(e) => setTicketStatus(t.id, e.target.value)}
                    disabled={loading}
                    className="rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                  >
                    {["open", "in_progress", "resolved", "closed"].map((s) => (
                      <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1).replace("_", " ")}</option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
