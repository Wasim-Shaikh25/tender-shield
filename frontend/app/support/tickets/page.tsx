"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type SupportTicket } from "@/lib/api";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";

export default function SupportTicketsPage() {
  const { session } = useSession();
  const router = useRouter();
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [newTicket, setNewTicket] = useState({ title: "", body: "", category: "technical" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = async () => {
    if (!session) return;
    try {
      const list = await api.listSupportTickets(session.token);
      setTickets(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load tickets");
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

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      await api.createSupportTicket(session.token, newTicket);
      setNewTicket({ title: "", body: "", category: "technical" });
      setMessage("Ticket created successfully.");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create ticket");
    } finally {
      setLoading(false);
    }
  };

  const getCategoryColor = (category: string): "primary" | "secondary" | "success" | "warning" | "error" | "info" => {
    switch (category) {
      case "billing": return "warning";
      case "technical": return "error";
      case "feature": return "info";
      default: return "secondary";
    }
  };

  const getStatusColor = (status: string): "primary" | "secondary" | "success" | "warning" | "error" | "info" => {
    switch (status) {
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
        <p className="text-sm text-text-muted mt-2">Get help from our support team or track your tickets</p>
      </div>

      {/* Alerts */}
      {error && <Alert variant="error" title="Error">{error}</Alert>}
      {message && <Alert variant="success" title="Success">{message}</Alert>}

      {/* Create Ticket Form */}
      <Card>
        <CardHeader>
          <CardTitle>Create Ticket</CardTitle>
          <CardDescription>Open a new support ticket to get help</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={create} className="space-y-4">
            <div>
              <label htmlFor="ticket-category" className="block text-sm font-medium text-text-primary mb-2">Category <span className="text-error">*</span></label>
              <select
                id="ticket-category"
                value={newTicket.category}
                onChange={(e) => setNewTicket({ ...newTicket, category: e.target.value })}
                className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
              >
                <option value="billing">Billing</option>
                <option value="technical">Technical Issue</option>
                <option value="feature">Feature Request</option>
              </select>
            </div>

            <div>
              <label htmlFor="ticket-title" className="block text-sm font-medium text-text-primary mb-2">Title <span className="text-error">*</span></label>
              <input
                id="ticket-title"
                type="text"
                placeholder="Brief description of your issue"
                value={newTicket.title}
                onChange={(e) => setNewTicket({ ...newTicket, title: e.target.value })}
                className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                required
              />
            </div>

            <div>
              <label htmlFor="ticket-body" className="block text-sm font-medium text-text-primary mb-2">Description <span className="text-error">*</span></label>
              <textarea
                id="ticket-body"
                placeholder="Provide detailed information about your issue"
                value={newTicket.body}
                onChange={(e) => setNewTicket({ ...newTicket, body: e.target.value })}
                className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink resize-none"
                rows={4}
                required
              />
            </div>

            <Button variant="primary" size="md" type="submit" disabled={loading}>
              {loading ? "Creating..." : "Create Ticket"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Tickets List */}
      <Card>
        <CardHeader>
          <CardTitle>Your Tickets</CardTitle>
          <CardDescription>{tickets.length} ticket{tickets.length !== 1 ? "s" : ""} total</CardDescription>
        </CardHeader>
        <CardContent>
          {tickets.length === 0 ? (
            <p className="text-sm text-text-muted py-8 text-center">No tickets yet. Create one to get started.</p>
          ) : (
            <div className="space-y-3">
              {tickets.map((t) => (
                <Link
                  key={t.id}
                  href={`/support/tickets/${t.id}`}
                  className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-lg border border-border-default hover:bg-bg-secondary transition-colors"
                >
                  <div className="flex-1">
                    <h3 className="font-medium text-text-primary">{t.title}</h3>
                    <div className="flex flex-wrap gap-2 mt-2">
                      <Badge variant={getCategoryColor(t.category)} size="sm" className="capitalize">
                        {t.category}
                      </Badge>
                      <Badge variant={getStatusColor(t.status)} size="sm" className="capitalize">
                        {t.status?.replace("_", " ")}
                      </Badge>
                    </div>
                  </div>
                  <Button variant="outline" size="sm">
                    Open
                  </Button>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
