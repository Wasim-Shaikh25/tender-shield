"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type SupportTicket, type SupportTicketReply } from "@/lib/api";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";

export default function SupportTicketDetailPage() {
  const { session } = useSession();
  const { id } = useParams<{ id: string }>();
  const [ticket, setTicket] = useState<SupportTicket | null>(null);
  const [reply, setReply] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!session || !id) return;
    api.getSupportTicket(session.token, id)
      .then(setTicket)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load ticket"));
  }, [session, id]);

  if (!session) {
    return null;
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session || !ticket) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      await api.replySupportTicket(session.token, id, reply);
      const updated = await api.getSupportTicket(session.token, id);
      setTicket(updated);
      setReply("");
      setMessage("Reply posted successfully.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reply failed");
    } finally {
      setLoading(false);
    }
  };

  if (!ticket) return <p className="p-6 text-sm text-text-muted">Loading...</p>;

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
      <div className="flex flex-col gap-4">
        <div>
          <h1 className="text-heading-lg text-text-primary">{ticket.title}</h1>
          <p className="text-sm text-text-muted mt-2">Support ticket details and conversation</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant={getCategoryColor(ticket.category)} className="capitalize">
            {ticket.category}
          </Badge>
          <Badge variant={getStatusColor(ticket.status)} className="capitalize">
            {ticket.status?.replace("_", " ")}
          </Badge>
        </div>
      </div>

      {/* Alerts */}
      {error && <Alert variant="error" title="Error">{error}</Alert>}
      {message && <Alert variant="success" title="Success">{message}</Alert>}

      {/* Original Ticket */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Original Message</CardTitle>
          <CardDescription className="text-xs">
            {new Date(ticket.created_at || "").toLocaleDateString("en-IN", {
              year: "numeric",
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-text-primary whitespace-pre-wrap">{ticket.body}</p>
        </CardContent>
      </Card>

      {/* Replies Thread */}
      <Card>
        <CardHeader>
          <CardTitle>Conversation</CardTitle>
          <CardDescription>{ticket.replies?.length || 0} reply/replies</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {ticket.replies?.length ? (
            <div className="space-y-4">
              {ticket.replies.map((r: SupportTicketReply) => (
                <div key={r.id} className="border-l-4 border-border-default pl-4 py-2">
                  <p className="text-xs text-text-muted mb-2">
                    {new Date(r.created_at || "").toLocaleDateString("en-IN", {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                  <p className="text-sm text-text-primary whitespace-pre-wrap">{r.body}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-text-muted py-4">No replies yet. Post the first reply.</p>
          )}
        </CardContent>
      </Card>

      {/* Reply Form */}
      {ticket.status !== "closed" && (
        <Card>
          <CardHeader>
            <CardTitle>Add Reply</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={submit} className="space-y-4">
              <textarea
                value={reply}
                onChange={(e) => setReply(e.target.value)}
                placeholder="Type your reply here..."
                className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink resize-none"
                rows={4}
                required
              />
              <Button variant="primary" size="md" type="submit" disabled={loading}>
                {loading ? "Posting..." : "Post Reply"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {ticket.status === "closed" && (
        <Alert variant="info" title="Ticket Closed">
          This ticket is closed. Contact support if you need to reopen it.
        </Alert>
      )}
    </div>
  );
}
