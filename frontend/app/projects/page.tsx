"use client";

import { useEffect, useId, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type ProjectState, type Workspace } from "@/lib/api";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import { cn } from "@/lib/utils";

const HEALTH_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  healthy: { bg: "bg-success-bg", text: "text-success-text", dot: "bg-success" },
  at_risk: { bg: "bg-warning-bg", text: "text-warning-text", dot: "bg-warning" },
  poor: { bg: "bg-error-bg", text: "text-error-text", dot: "bg-error" },
  completed: { bg: "bg-bg-secondary", text: "text-text-secondary", dot: "bg-text-muted" },
};

const HEALTH_LABEL: Record<string, string> = {
  healthy: "Healthy",
  at_risk: "At risk",
  poor: "Poor",
  completed: "Completed",
};

export default function ProjectsPage() {
  const { session } = useSession();
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectState[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const baseId = useId();

  useEffect(() => {
    if (!session) return;
    api.listWorkspaces(session.token).then((res) => setWorkspaces(res));
  }, [session]);

  useEffect(() => {
    if (!session) return;
    setLoading(true);
    setError(null);
    api.listProjectStates(session.token, {
      ...Object.fromEntries(
        Object.entries(filters).map(([k, v]) => [k, v === "all" ? "" : v])
      ),
    })
      .then((res) => setProjects(res.opportunities))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load projects"))
      .finally(() => setLoading(false));
  }, [session, filters]);

  const counts = useMemo(() => {
    const byState: Record<string, number> = {};
    const byHealth: Record<string, number> = {};
    projects.forEach((p) => {
      byState[p.state] = (byState[p.state] || 0) + 1;
      byHealth[p.health] = (byHealth[p.health] || 0) + 1;
    });
    return { byState, byHealth };
  }, [projects]);

  function updateFilter(key: string, value: string) {
    setFilters((f) => ({ ...f, [key]: value }));
  }

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold text-text-primary">All Projects</h1>
          <p className="text-text-secondary">
            Track every tender across your workspaces. Filter by state, health, and deadline.
          </p>
        </div>
        <Link href="/opportunities" className="flex-shrink-0">
          <Button variant="primary" size="md">
            + New opportunity
          </Button>
        </Link>
      </div>

      {/* State Summary Cards */}
      {Object.keys(counts.byState).length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {Object.entries(counts.byState).map(([state, count]) => (
            <button
              key={state}
              type="button"
              onClick={() => updateFilter("status", state)}
              className={cn(
                "text-left p-4 rounded-lg border transition-all duration-base",
                filters.status === state
                  ? "border-ink bg-bg-primary ring-2 ring-ink"
                  : "border-border-default bg-white hover:border-ink"
              )}
            >
              <p className="text-2xl font-bold text-ink">{count}</p>
              <p className="text-xs text-text-muted mt-1 capitalize">{state.replace(/_/g, " ")}</p>
            </button>
          ))}
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Workspace Filter */}
            <div className="space-y-2">
              <label htmlFor={`${baseId}-workspace`} className="text-sm font-medium text-text-primary">
                Workspace
              </label>
              <select
                id={`${baseId}-workspace`}
                value={filters.workspace_id || "all"}
                onChange={(e) => updateFilter("workspace_id", e.target.value)}
                className="w-full rounded-md border border-border-default bg-white px-3 py-2 text-sm text-text-primary focus:border-ink focus:ring-1 focus:ring-ink outline-none"
              >
                <option value="all">All workspaces</option>
                {workspaces.map((w) => (
                  <option key={w.workspace_id} value={w.workspace_id}>
                    {w.name}
                  </option>
                ))}
              </select>
            </div>

            {/* State Filter */}
            <div className="space-y-2">
              <label htmlFor={`${baseId}-status`} className="text-sm font-medium text-text-primary">
                State
              </label>
              <select
                id={`${baseId}-status`}
                value={filters.status || "all"}
                onChange={(e) => updateFilter("status", e.target.value)}
                className="w-full rounded-md border border-border-default bg-white px-3 py-2 text-sm text-text-primary focus:border-ink focus:ring-1 focus:ring-ink outline-none"
              >
                <option value="all">All states</option>
                <option value="draft">Draft</option>
                <option value="ingesting">Ingesting</option>
                <option value="ingested">Ingested</option>
                <option value="reviewing">Reviewing</option>
                <option value="reviewed">Reviewed</option>
                <option value="baseline_locked">Baseline locked</option>
                <option value="submitted">Submitted</option>
                <option value="awarded">Awarded</option>
                <option value="rejected">Rejected</option>
                <option value="withdrawn">Withdrawn</option>
              </select>
            </div>

            {/* Health Filter */}
            <div className="space-y-2">
              <label htmlFor={`${baseId}-health`} className="text-sm font-medium text-text-primary">
                Health
              </label>
              <select
                id={`${baseId}-health`}
                value={filters.health || "all"}
                onChange={(e) => updateFilter("health", e.target.value)}
                className="w-full rounded-md border border-border-default bg-white px-3 py-2 text-sm text-text-primary focus:border-ink focus:ring-1 focus:ring-ink outline-none"
              >
                <option value="all">All health</option>
                <option value="healthy">Healthy</option>
                <option value="at_risk">At risk</option>
                <option value="poor">Poor</option>
                <option value="completed">Completed</option>
              </select>
            </div>

            {/* Jurisdiction Filter */}
            <div className="space-y-2">
              <label htmlFor={`${baseId}-jurisdiction`} className="text-sm font-medium text-text-primary">
                Jurisdiction
              </label>
              <Input
                id={`${baseId}-jurisdiction`}
                type="text"
                value={filters.jurisdiction || ""}
                onChange={(e) => updateFilter("jurisdiction", e.target.value)}
                placeholder="IN, AE, GB…"
              />
            </div>

            {/* Min Value Filter */}
            <div className="space-y-2">
              <label htmlFor={`${baseId}-min-value`} className="text-sm font-medium text-text-primary">
                Min value
              </label>
              <Input
                id={`${baseId}-min-value`}
                type="number"
                value={filters.min_value || ""}
                onChange={(e) => updateFilter("min_value", e.target.value)}
                placeholder="0"
              />
            </div>

            {/* Max Value Filter */}
            <div className="space-y-2">
              <label htmlFor={`${baseId}-max-value`} className="text-sm font-medium text-text-primary">
                Max value
              </label>
              <Input
                id={`${baseId}-max-value`}
                type="number"
                value={filters.max_value || ""}
                onChange={(e) => updateFilter("max_value", e.target.value)}
                placeholder="0"
              />
            </div>

            {/* Deadline After Filter */}
            <div className="space-y-2">
              <label htmlFor={`${baseId}-deadline-after`} className="text-sm font-medium text-text-primary">
                Deadline after
              </label>
              <Input
                id={`${baseId}-deadline-after`}
                type="date"
                value={filters.deadline_after || ""}
                onChange={(e) => updateFilter("deadline_after", e.target.value)}
              />
            </div>

            {/* Deadline Before Filter */}
            <div className="space-y-2">
              <label htmlFor={`${baseId}-deadline-before`} className="text-sm font-medium text-text-primary">
                Deadline before
              </label>
              <Input
                id={`${baseId}-deadline-before`}
                type="date"
                value={filters.deadline_before || ""}
                onChange={(e) => updateFilter("deadline_before", e.target.value)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Error Alert */}
      {error && (
        <Alert variant="error" title="Failed to load projects">
          {error}
        </Alert>
      )}

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="text-center space-y-3">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-border-default border-t-ink" />
            <p className="text-sm text-text-muted">Loading projects…</p>
          </div>
        </div>
      )}

      {/* Projects List */}
      {!loading && projects.length === 0 && (
        <Card className="border-dashed">
          <CardContent className="py-12 text-center">
            <h3 className="text-lg font-semibold text-text-primary mb-2">No projects found</h3>
            <p className="text-text-secondary">No projects match the selected filters.</p>
          </CardContent>
        </Card>
      )}

      {!loading && projects.length > 0 && (
        <div className="space-y-3">
          {projects.map((p) => {
            const healthStyle = HEALTH_COLORS[p.health] || HEALTH_COLORS.completed;

            return (
              <Card key={p.opportunity_id} className="hover:shadow-md transition-shadow">
                <CardContent className="pt-6">
                  <div className="space-y-3">
                    {/* Title and Status Row */}
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <h3 className="text-base font-semibold text-text-primary truncate">
                          {p.title}
                        </h3>
                        <div className="flex flex-wrap gap-2 mt-2">
                          <Badge variant="secondary" size="sm">
                            {p.state_label}
                          </Badge>
                          <Badge variant={p.health === "healthy" ? "success" : p.health === "at_risk" ? "warning" : "error"} size="sm">
                            {HEALTH_LABEL[p.health] || p.health}
                          </Badge>
                        </div>
                      </div>

                      <div className="flex gap-2 flex-shrink-0">
                        <Link href={p.next_action.link}>
                          <Button variant="primary" size="sm">
                            {p.next_action.label}
                          </Button>
                        </Link>
                      </div>
                    </div>

                    {/* Project Details */}
                    <div className="border-t border-border-default pt-3 space-y-2 text-sm">
                      <div className="flex flex-wrap gap-4 text-text-secondary">
                        <div>
                          <span className="font-medium text-text-primary">Employer:</span> {p.employer || "—"}
                        </div>
                        <div>
                          <span className="font-medium text-text-primary">Jurisdiction:</span> {p.jurisdiction || "—"}
                        </div>
                        <div>
                          <span className="font-medium text-text-primary">Value:</span>{" "}
                          {p.contract_value_minor ? `${p.contract_value_minor} ${p.currency}` : "—"}
                        </div>
                      </div>

                      <div className="flex flex-wrap gap-4 text-text-muted text-xs">
                        <div>
                          📅{" "}
                          {p.submission_due
                            ? `Deadline ${new Date(p.submission_due).toLocaleDateString("en-IN")} (${p.days_to_deadline}d)`
                            : "No deadline"}
                        </div>
                        <div>📄 {p.document_count} docs</div>
                        <div>⚠️ {p.unreviewed_finding_count} open findings</div>
                      </div>

                      {/* Blockers */}
                      {p.blockers.length > 0 && (
                        <div className="space-y-1 mt-3">
                          {p.blockers.map((b, i) => (
                            <div key={i} className="flex items-center gap-2 text-warning-text">
                              <span className="h-1.5 w-1.5 rounded-full bg-warning flex-shrink-0" />
                              <span className="text-sm">{b.message}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Footer Link */}
                    <div className="border-t border-border-default pt-3">
                      <Link
                        href={`/projects/${p.opportunity_id}/state`}
                        className="text-sm text-ink hover:underline font-medium"
                      >
                        View project state →
                      </Link>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
