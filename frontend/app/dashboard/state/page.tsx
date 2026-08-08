"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, type WorkspaceStateSummary } from "@/lib/api";
import { useSession } from "@/components/session";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";

export default function DashboardStatePage() {
  const { session } = useSession();
  const router = useRouter();
  const [summaries, setSummaries] = useState<WorkspaceStateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    api
      .listWorkspaceStateSummaries(session.token)
      .then((res) => setSummaries(res.workspaces))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load summaries"))
      .finally(() => setLoading(false));
  }, [session]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold text-text-primary">Dashboard</h1>
        <p className="text-text-secondary">
          View opportunity counts, states, and upcoming deadlines across all workspaces.
        </p>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="error" title="Failed to load dashboard">
          {error}
        </Alert>
      )}

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="text-center space-y-3">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-border-default border-t-ink" />
            <p className="text-sm text-text-muted">Loading dashboard…</p>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!loading && summaries.length === 0 && (
        <Card className="border-dashed">
          <CardContent className="py-12 text-center">
            <h3 className="text-lg font-semibold text-text-primary mb-2">No workspaces found</h3>
            <p className="text-text-secondary mb-4">
              Create your first workspace to get started tracking opportunities.
            </p>
            <Link href="/settings" className="text-ink hover:underline font-medium">
              Go to Settings →
            </Link>
          </CardContent>
        </Card>
      )}

      {/* Workspace Cards */}
      {!loading && summaries.length > 0 && (
        <div className="space-y-6">
          {summaries.map((ws) => (
            <div key={ws.workspace_id} className="space-y-4">
              {/* Workspace Header */}
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-text-primary">
                    {ws.workspace_name || "Workspace"}
                  </h2>
                  <p className="text-sm text-text-muted mt-1">
                    {ws.opportunity_count} {ws.opportunity_count === 1 ? "project" : "projects"}
                  </p>
                </div>
              </div>

              {/* State Metrics */}
              {Object.entries(ws.state_counts).some(([_, count]) => count > 0) && (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
                  {Object.entries(ws.state_counts).map(([state, count]) =>
                    count > 0 ? (
                      <Card key={state} variant="outlined" className="text-center">
                        <CardContent className="py-4">
                          <p className="text-2xl font-bold text-ink">{count}</p>
                          <p className="text-xs text-text-muted mt-1 capitalize">
                            {state.replace(/_/g, " ")}
                          </p>
                        </CardContent>
                      </Card>
                    ) : null
                  )}
                </div>
              )}

              {/* Upcoming Deadlines */}
              {ws.upcoming_deadlines.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Upcoming Deadlines</CardTitle>
                    <CardDescription>
                      Opportunities with submission deadlines in the next 7 days
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {ws.upcoming_deadlines.map((d) => {
                        const daysLeft = d.days_to_deadline ?? 0;
                        let urgencyVariant: "error" | "warning" | "info" = "info";
                        if (daysLeft <= 3) urgencyVariant = "error";
                        else if (daysLeft <= 7) urgencyVariant = "warning";

                        return (
                          <Link
                            key={d.opportunity_id}
                            href={`/opportunities/${d.opportunity_id}`}
                            className="flex items-center justify-between p-3 rounded-lg border border-border-default hover:bg-bg-secondary transition-colors duration-base group"
                          >
                            <div className="min-w-0 flex-1">
                              <h4 className="font-medium text-text-primary group-hover:text-ink truncate">
                                {d.title}
                              </h4>
                              <p className="text-xs text-text-muted mt-1">
                                {d.submission_due
                                  ? new Date(d.submission_due).toLocaleDateString("en-IN", {
                                    year: "numeric",
                                    month: "short",
                                    day: "numeric",
                                  })
                                  : "No date"}{" "}
                                · {d.state}
                              </p>
                            </div>

                            <div className="flex items-center gap-2 ml-4 flex-shrink-0">
                              <Badge variant={urgencyVariant} size="sm">
                                {daysLeft}d left
                              </Badge>
                            </div>
                          </Link>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
