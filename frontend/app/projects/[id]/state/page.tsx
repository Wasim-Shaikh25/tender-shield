"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api, type ProjectState } from "@/lib/api";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";

const HEALTH_VARIANT: Record<string, "success" | "warning" | "error" | "secondary"> = {
  healthy: "success",
  at_risk: "warning",
  poor: "error",
  completed: "secondary",
};

const HEALTH_LABEL: Record<string, string> = {
  healthy: "Healthy",
  at_risk: "At risk",
  poor: "Poor",
  completed: "Completed",
};

export default function ProjectStatePage() {
  const { session } = useSession();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [state, setState] = useState<ProjectState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session || !id) return;
    api.getProjectState(session.token, id)
      .then(setState)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load project state"))
      .finally(() => setLoading(false));
  }, [session, id]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  if (loading) return <p className="p-6 text-sm text-text-muted">Loading project state…</p>;
  if (error) return <Alert variant="error" title="Error">{error}</Alert>;
  if (!state) return <Alert variant="info" title="Not Found">Project state not found.</Alert>;

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-text-muted">
        <Link href="/projects" className="hover:text-text-primary">All Projects</Link>
        <span>/</span>
        <span>State</span>
      </div>

      {/* Project Header */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-3 mb-2">
            <CardTitle className="flex-1">{state.title}</CardTitle>
            <Badge variant="secondary" size="sm">{state.state_label}</Badge>
            <Badge variant={HEALTH_VARIANT[state.health] || "secondary"} size="sm">
              {HEALTH_LABEL[state.health] || state.health}
            </Badge>
          </div>
          <CardDescription className="space-y-1">
            <div>{state.employer || "No employer"} · {state.jurisdiction}</div>
            <div>
              {state.contract_value_minor ? `${state.contract_value_minor} ${state.currency}` : "No value"} ·{" "}
              {state.submission_due
                ? `Deadline ${new Date(state.submission_due).toLocaleDateString()} (${state.days_to_deadline}d)`
                : "No deadline"}
            </div>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h3 className="text-sm font-medium text-text-primary mb-3">Next Action</h3>
            <div className="flex items-center gap-3">
              <Link
                href={state.next_action.link}
                className="inline-flex items-center justify-center gap-2 font-medium transition-colors duration-base focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap bg-ink text-white hover:bg-ink/90 active:bg-ink h-10 px-4 text-sm rounded-md"
              >
                {state.next_action.label}
              </Link>
              <Link
                href={`/opportunities/${id}`}
                className="inline-flex items-center justify-center gap-2 font-medium transition-colors duration-base focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 whitespace-nowrap h-10 px-4 text-sm rounded-md border border-border-default text-text-primary hover:bg-bg-secondary active:bg-bg-tertiary"
              >
                Open Opportunity
              </Link>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Blockers */}
      {state.blockers.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Blockers</CardTitle>
            <CardDescription>{state.blockers.length} issue{state.blockers.length !== 1 ? "s" : ""}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {state.blockers.map((b, i) => (
                <div key={i} className="flex items-start gap-3 p-3 rounded-lg border border-warning bg-warning/5">
                  <div className="flex-1">
                    <p className="text-sm text-text-primary">{b.message}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Completed Gates */}
      <Card>
        <CardHeader>
          <CardTitle>Completed Gates</CardTitle>
          <CardDescription>{state.completed_gates.length} gate{state.completed_gates.length !== 1 ? "s" : ""}</CardDescription>
        </CardHeader>
        <CardContent>
          {state.completed_gates.length === 0 ? (
            <p className="text-sm text-text-muted">No gates completed yet.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {state.completed_gates.map((g) => (
                <Badge key={g} variant="success" size="sm">
                  {g.replace(/_/g, " ")}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Metrics */}
      <Card>
        <CardHeader>
          <CardTitle>Project Metrics</CardTitle>
          <CardDescription>Overview of project documents and findings</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="rounded-lg bg-bg-secondary p-4 text-center">
              <p className="text-2xl font-bold text-text-primary">{state.document_count}</p>
              <p className="text-xs text-text-muted mt-1">Documents</p>
            </div>
            <div className="rounded-lg bg-bg-secondary p-4 text-center">
              <p className="text-2xl font-bold text-text-primary">{state.finding_count}</p>
              <p className="text-xs text-text-muted mt-1">Findings</p>
            </div>
            <div className="rounded-lg bg-bg-secondary p-4 text-center">
              <p className="text-2xl font-bold text-text-primary">{state.unreviewed_finding_count}</p>
              <p className="text-xs text-text-muted mt-1">Open Findings</p>
            </div>
            <div className="rounded-lg bg-bg-secondary p-4 text-center">
              <p className="text-2xl font-bold text-text-primary">{state.baseline_count}</p>
              <p className="text-xs text-text-muted mt-1">Baselines</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
