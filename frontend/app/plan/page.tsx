"use client";

import { useCallback, useEffect, useState } from "react";
import { api, Opportunity, PlanDashboard, PlanSnapshot } from "@/lib/api";
import { useSession } from "@/components/session";
import { DashboardView } from "@/components/plan-dashboard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import { cn } from "@/lib/utils";

type PlanTemplate = { id: string; name: string; query: string };

export default function PlanPage() {
  const { session } = useSession();
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [opportunityId, setOpportunityId] = useState("");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<PlanDashboard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<PlanTemplate[]>([]);
  const [snapshots, setSnapshots] = useState<PlanSnapshot[]>([]);
  const [snapshotTitle, setSnapshotTitle] = useState("");
  const [saving, setSaving] = useState(false);

  const loadSnapshots = useCallback(() => {
    if (!session) return;
    api.listPlanSnapshots(session.token)
      .then((res) => setSnapshots(res.snapshots))
      .catch(() => {});
  }, [session]);

  useEffect(() => {
    if (!session) return;
    api.listOpportunities(session.token)
      .then((res) => setOpportunities(res.opportunities))
      .catch(() => {});
    api.planTemplates().then(setTemplates).catch(() => {});
    loadSnapshots();
  }, [session, loadSnapshots]);

  if (!session) {
    return null;
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!opportunityId || !query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await api.planDashboard(session.token, opportunityId, query.trim());
      setResult(data);
      setSnapshotTitle(data.title || "Plan snapshot");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate dashboard");
    } finally {
      setLoading(false);
    }
  };

  const saveSnapshot = async () => {
    if (!session || !opportunityId || !result || !snapshotTitle.trim()) return;
    setSaving(true);
    try {
      await api.savePlanSnapshot(session.token, {
        opportunity_id: opportunityId,
        title: snapshotTitle.trim(),
        query: query.trim(),
        dashboard: result as unknown as Record<string, unknown>,
      });
      loadSnapshots();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save snapshot");
    } finally {
      setSaving(false);
    }
  };

  const loadSnapshot = async (snapshotId: string) => {
    if (!session) return;
    try {
      const data = await api.getPlanSnapshot(session.token, snapshotId);
      setOpportunityId(data.opportunity_id);
      setQuery(data.query);
      setSnapshotTitle(data.title);
      setResult(data.dashboard as unknown as PlanDashboard);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load snapshot");
    }
  };

  const exportSnapshot = async (snapshotId: string, format: string) => {
    if (!session) return;
    try {
      const blob = await api.exportPlanSnapshot(session.token, snapshotId, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `plan-${snapshotId}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-heading-lg text-text-primary">Tender Plan Dashboard</h1>
        <p className="text-sm text-text-muted mt-2">
          Ask a question about a tender. The AI builds a structured dashboard with KPIs, tables, charts, and diagrams.
        </p>
      </div>

      {/* Form Card */}
      <form onSubmit={submit}>
        <Card>
          <CardHeader>
            <CardTitle>Generate Dashboard</CardTitle>
            <CardDescription>Select an opportunity and describe what you want to see</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label htmlFor="opportunity" className="block text-sm font-medium text-text-primary mb-2">
                Opportunity <span className="text-error">*</span>
              </label>
              <select
                id="opportunity"
                value={opportunityId}
                onChange={(e) => setOpportunityId(e.target.value)}
                className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
              >
                <option value="">Select an opportunity</option>
                {opportunities.map((opp) => (
                  <option key={opp.id} value={opp.id}>{opp.title}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="template" className="block text-sm font-medium text-text-primary mb-2">
                Template <span className="text-text-muted">(optional)</span>
              </label>
              <select
                id="template"
                value=""
                onChange={(e) => {
                  const t = templates.find((x) => x.id === e.target.value);
                  if (t) setQuery(t.query);
                }}
                className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
              >
                <option value="">Pick a template (optional)</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="query" className="block text-sm font-medium text-text-primary mb-2">
                What do you want to see? <span className="text-error">*</span>
              </label>
              <input
                id="query"
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. Show risk severity distribution and deadline timeline"
                className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
              />
            </div>

            <Button
              variant="primary"
              size="md"
              type="submit"
              disabled={loading || !opportunityId || !query.trim()}
            >
              {loading ? "Generating..." : "Generate Dashboard"}
            </Button>
          </CardContent>
        </Card>
      </form>

      {/* Save Snapshot */}
      {result && (
        <Card>
          <CardHeader>
            <CardTitle>Save Dashboard</CardTitle>
            <CardDescription>Save this dashboard as a snapshot for later reference</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label htmlFor="snapshot-title" className="block text-sm font-medium text-text-primary mb-2">
                Snapshot Title
              </label>
              <input
                id="snapshot-title"
                type="text"
                value={snapshotTitle}
                onChange={(e) => setSnapshotTitle(e.target.value)}
                placeholder="e.g. Q3 Risk Analysis"
                className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
              />
            </div>
            <Button
              variant="primary"
              size="md"
              onClick={saveSnapshot}
              disabled={saving || !snapshotTitle.trim()}
            >
              {saving ? "Saving..." : "Save Snapshot"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Saved Snapshots */}
      {snapshots.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Saved Snapshots</CardTitle>
            <CardDescription>Load, export, or delete previously saved dashboards</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {snapshots.map((s) => (
                <div
                  key={s.id || s.title}
                  className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-3 rounded-lg border border-border-default hover:bg-bg-secondary transition-colors"
                >
                  <div className="flex-1">
                    <p className="font-medium text-text-primary">{s.title}</p>
                    {s.created_at && (
                      <p className="text-xs text-text-muted mt-1">
                        {new Date(s.created_at).toLocaleDateString("en-IN")}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2 mt-3 sm:mt-0 flex-wrap justify-end">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => s.id && loadSnapshot(s.id)}
                    >
                      Load
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => s.id && exportSnapshot(s.id, "pdf")}
                    >
                      PDF
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => s.id && exportSnapshot(s.id, "pptx")}
                    >
                      PPTX
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => s.id && api.deletePlanSnapshot(session!.token, s.id).then(loadSnapshots)}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Error Alert */}
      {error && (
        <Alert variant="error" title="Error">
          {error}
        </Alert>
      )}

      {result && <DashboardView dashboard={result} />}
    </div>
  );
}
