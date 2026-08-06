"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/components/session";
import { api, type DynamicConnectorConfig } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import IntegrationSourcesPanel from "./integration-sources";

const DEFAULT_COST_LINE_MAPPING = JSON.stringify(
  {
    cost_lines: {
      items: "data.items",
      fields: {
        cost_code: "costCode",
        description: "description",
        committed_cost_minor: "committedCost",
        certified_value_minor: "certifiedValue",
        currency: "currency",
      },
    },
  },
  null,
  2
);

type FormState = {
  name: string;
  base_url: string;
  auth_type: "none" | "bearer" | "basic" | "api_key";
  auth_config: string;
  headers: string;
  pagination: string;
  mappings: string;
  enabled: boolean;
};

const emptyForm: FormState = {
  name: "",
  base_url: "",
  auth_type: "none",
  auth_config: "{}",
  headers: "{}",
  pagination: "{}",
  mappings: DEFAULT_COST_LINE_MAPPING,
  enabled: true,
};

export default function IntegrationsSettingsPage() {
  const { session } = useSession();
  const router = useRouter();
  const [connectors, setConnectors] = useState<DynamicConnectorConfig[]>([]);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [editing, setEditing] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ status: string; http_status: number | null; latency_ms: number; preview: string } | null>(null);

  const isAdmin = session && ["admin", "owner", "superadmin"].includes(session.role);

  useEffect(() => {
    if (!session) {
      if (typeof window !== "undefined") router.replace("/login");
      return;
    }
    api.listDynamicConnectors(session.token)
      .then((r) => setConnectors(r.connectors))
      .catch(() => setConnectors([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  const parseJson = (value: string) => {
    const trimmed = value.trim();
    return trimmed ? JSON.parse(trimmed) : {};
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session || !isAdmin) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const body = {
        name: form.name,
        base_url: form.base_url,
        auth_type: form.auth_type,
        auth_config: parseJson(form.auth_config),
        headers: parseJson(form.headers),
        pagination: parseJson(form.pagination),
        mappings: parseJson(form.mappings),
        enabled: form.enabled,
      };
      if (editing) {
        await api.updateDynamicConnector(session.token, editing, body);
      } else {
        await api.createDynamicConnector(session.token, body);
      }
      setForm(emptyForm);
      setEditing(null);
      setMessage("Connector saved successfully.");
      api.listDynamicConnectors(session.token)
        .then((r) => setConnectors(r.connectors))
        .catch(() => setConnectors([]));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save connector");
    } finally {
      setLoading(false);
    }
  };

  const test = async (id: string) => {
    if (!session) return;
    setLoading(true);
    setError(null);
    setTestResult(null);
    try {
      const r = await api.testDynamicConnector(session.token, id);
      setTestResult(r);
      setMessage(`Test ${r.status} (${r.http_status ?? "-"}) in ${r.latency_ms}ms`);
      api.listDynamicConnectors(session.token)
        .then((resp) => setConnectors(resp.connectors))
        .catch(() => setConnectors([]));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test failed");
    } finally {
      setLoading(false);
    }
  };

  const poll = async (id: string) => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      await api.pollDynamicConnector(session.token, id);
      setMessage("Poll completed. Check sync jobs for details.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Poll failed");
    } finally {
      setLoading(false);
    }
  };

  const remove = async (id: string) => {
    if (!session || !confirm("Delete this connector?")) return;
    setLoading(true);
    setError(null);
    try {
      await api.deleteDynamicConnector(session.token, id);
      api.listDynamicConnectors(session.token)
        .then((r) => setConnectors(r.connectors))
        .catch(() => setConnectors([]));
      setMessage("Connector deleted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setLoading(false);
    }
  };

  const edit = (c: DynamicConnectorConfig) => {
    setEditing(c.id!);
    setForm({
      name: c.name,
      base_url: c.base_url,
      auth_type: c.auth_type,
      auth_config: JSON.stringify(c.auth_config || {}, null, 2),
      headers: JSON.stringify(c.headers || {}, null, 2),
      pagination: JSON.stringify(c.pagination || {}, null, 2),
      mappings: JSON.stringify(c.mappings || {}, null, 2),
      enabled: c.enabled ?? true,
    });
    setTestResult(null);
  };

  const cancelEdit = () => {
    setEditing(null);
    setForm(emptyForm);
  };

  if (!session) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-heading-lg text-text-primary">Integrations</h1>
        <p className="text-sm text-text-muted mt-2">Connect external systems and configure data sources</p>
      </div>

      {/* Alerts */}
      {error && <Alert variant="error" title="Error">{error}</Alert>}
      {message && <Alert variant="success" title="Success">{message}</Alert>}

      {/* Create/Edit Connector Form */}
      {isAdmin && (
        <Card>
          <CardHeader>
            <CardTitle>{editing ? "Edit Connector" : "Create Connector"}</CardTitle>
            <CardDescription>
              {editing ? "Update connector configuration" : "Set up a new REST API connector"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-text-primary mb-2">Name <span className="text-error">*</span></label>
                  <input
                    type="text"
                    placeholder="Connector name"
                    className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    disabled={loading}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-text-primary mb-2">Base URL <span className="text-error">*</span></label>
                  <input
                    type="text"
                    placeholder="https://api.example.com"
                    className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                    value={form.base_url}
                    onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                    disabled={loading}
                    required
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label htmlFor="auth-type" className="block text-sm font-medium text-text-primary mb-2">Auth Type</label>
                  <select
                    id="auth-type"
                    className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                    value={form.auth_type}
                    onChange={(e) => setForm({ ...form, auth_type: e.target.value as FormState["auth_type"] })}
                    disabled={loading}
                  >
                    <option value="none">None</option>
                    <option value="bearer">Bearer Token</option>
                    <option value="basic">Basic Auth</option>
                    <option value="api_key">API Key Header</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <label className="flex items-center gap-2 text-sm text-text-primary">
                    <input
                      type="checkbox"
                      checked={form.enabled}
                      onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                      className="h-4 w-4 accent-ink"
                    />
                    Enabled
                  </label>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-text-primary mb-2">Auth Config (JSON)</label>
                <textarea
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm font-mono text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink resize-none"
                  rows={3}
                  placeholder={`{"token":"..."}  or  {"username":"...","password":"..."}`}
                  value={form.auth_config}
                  onChange={(e) => setForm({ ...form, auth_config: e.target.value })}
                  disabled={loading}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-text-primary mb-2">Headers (JSON)</label>
                <textarea
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm font-mono text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink resize-none"
                  rows={2}
                  placeholder={`{"Accept":"application/json"}`}
                  value={form.headers}
                  onChange={(e) => setForm({ ...form, headers: e.target.value })}
                  disabled={loading}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-text-primary mb-2">Pagination (JSON)</label>
                <textarea
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm font-mono text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink resize-none"
                  rows={3}
                  placeholder={`{"type":"offset","offset_param":"offset","limit_param":"limit","limit":100}`}
                  value={form.pagination}
                  onChange={(e) => setForm({ ...form, pagination: e.target.value })}
                  disabled={loading}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-text-primary mb-2">Field Mappings (JSON)</label>
                <textarea
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm font-mono text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink resize-none"
                  rows={4}
                  value={form.mappings}
                  onChange={(e) => setForm({ ...form, mappings: e.target.value })}
                  disabled={loading}
                />
              </div>

              <div className="flex gap-3">
                <Button variant="primary" size="md" type="submit" disabled={loading}>
                  {loading ? "Saving..." : editing ? "Update Connector" : "Create Connector"}
                </Button>
                {editing && (
                  <Button variant="outline" size="md" type="button" onClick={cancelEdit} disabled={loading}>
                    Cancel
                  </Button>
                )}
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Test Result */}
      {testResult && (
        <Card>
          <CardHeader>
            <CardTitle>Test Result</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-sm text-text-muted">Status:</span>
              <Badge variant={testResult.status === "ok" ? "success" : "error"}>
                {testResult.status}
              </Badge>
            </div>
            <p className="text-sm text-text-muted">HTTP: {testResult.http_status ?? "-"}</p>
            <p className="text-sm text-text-muted">Latency: {testResult.latency_ms}ms</p>
            {testResult.preview && (
              <pre className="mt-3 max-h-48 overflow-auto rounded-md bg-bg-secondary p-3 text-xs font-mono text-text-primary break-words">
                {testResult.preview}
              </pre>
            )}
          </CardContent>
        </Card>
      )}

      {/* Connectors List */}
      <Card>
        <CardHeader>
          <CardTitle>Dynamic Connectors</CardTitle>
          <CardDescription>{connectors.length} connector{connectors.length !== 1 ? "s" : ""} configured</CardDescription>
        </CardHeader>
        <CardContent>
          {connectors.length === 0 ? (
            <p className="text-sm text-text-muted py-4">No connectors configured yet.</p>
          ) : (
            <div className="space-y-3">
              {connectors.map((c) => (
                <div key={c.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-lg border border-border-default hover:bg-bg-secondary transition-colors">
                  <div className="flex-1">
                    <h3 className="font-medium text-text-primary">{c.name}</h3>
                    <p className="text-sm text-text-muted mt-1">{c.base_url}</p>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {c.enabled ? (
                        <Badge variant="success" size="sm">Enabled</Badge>
                      ) : (
                        <Badge variant="secondary" size="sm">Disabled</Badge>
                      )}
                      {c.last_test_status && (
                        <Badge variant={c.last_test_status === "ok" ? "success" : "warning"} size="sm">
                          Last test: {c.last_test_status}
                        </Badge>
                      )}
                    </div>
                  </div>
                  {isAdmin && (
                    <div className="flex gap-2 flex-wrap justify-end">
                      <Button variant="outline" size="sm" onClick={() => test(c.id!)} disabled={loading}>
                        Test
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => poll(c.id!)} disabled={loading}>
                        Poll
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => edit(c)} disabled={loading}>
                        Edit
                      </Button>
                      <Button variant="destructive" size="sm" onClick={() => remove(c.id!)} disabled={loading}>
                        Delete
                      </Button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Integration Sources Panel */}
      {session && <IntegrationSourcesPanel token={session.token} isAdmin={!!isAdmin} />}
    </div>
  );
}
