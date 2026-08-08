"use client";

import { useEffect, useState } from "react";
import { useSession } from "@/components/session";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";

const SCOPES = ["read", "write", "signature"];

export default function ApiKeysSettingsPage() {
  const { session } = useSession();
  const [keys, setKeys] = useState<{ id: string; name: string; scopes: string[] }[]>([]);
  const [name, setName] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<string[]>(["read"]);
  const [plaintext, setPlaintext] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const isAdmin = session && ["admin", "owner", "superadmin"].includes(session.role);

  const load = () => {
    if (!session) return;
    api.listPublicApiKeys(session.token)
      .then((r) => setKeys(r.keys))
      .catch(() => setKeys([]));
  };

  useEffect(() => {
    if (!session) {
      return;
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session || !isAdmin) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    setPlaintext(null);
    try {
      const r = await api.createPublicApiKey(session.token, { name, scopes: selectedScopes });
      setKeys([...keys, { id: r.id, name: r.name, scopes: r.scopes }]);
      setPlaintext(r.plaintext_key);
      setName("");
      setSelectedScopes(["read"]);
      setMessage("API key created. Copy it now — it will not be shown again.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create key");
    } finally {
      setLoading(false);
    }
  };

  const revoke = async (id: string) => {
    if (!session || !isAdmin || !confirm("Revoke this API key?")) return;
    try {
      await api.revokePublicApiKey(session.token, id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke key");
    }
  };

  const toggleScope = (scope: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]
    );
  };

  if (!session) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-heading-lg text-text-primary">API Keys</h1>
        <p className="text-sm text-text-muted mt-2">Create and manage API keys for programmatic access</p>
      </div>

      {/* Alerts */}
      {error && <Alert variant="error" title="Error">{error}</Alert>}
      {message && <Alert variant="success" title="Success">{message}</Alert>}

      {/* Create Key Form */}
      {isAdmin && (
        <Card>
          <CardHeader>
            <CardTitle>Create API Key</CardTitle>
            <CardDescription>Generate a new API key with specific permissions</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={create} className="space-y-4">
              <div>
                <label htmlFor="key-name" className="block text-sm font-medium text-text-primary mb-2">Key Name <span className="text-error">*</span></label>
                <input
                  id="key-name"
                  type="text"
                  placeholder="e.g., Integration Server, Mobile App"
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={loading}
                  required
                />
              </div>

              <div>
                <p className="block text-sm font-medium text-text-primary mb-3">Scopes</p>
                <div className="flex flex-wrap gap-3">
                  {SCOPES.map((s) => (
                    <label key={s} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedScopes.includes(s)}
                        onChange={() => toggleScope(s)}
                        disabled={loading}
                        className="h-4 w-4 accent-ink"
                      />
                      <span className="text-sm font-medium text-text-primary capitalize">{s}</span>
                    </label>
                  ))}
                </div>
              </div>

              <Button variant="primary" size="md" type="submit" disabled={loading}>
                {loading ? "Creating..." : "Create Key"}
              </Button>
            </form>

            {plaintext && (
              <Alert variant="warning" title="Copy your key now">
                <code className="block break-all bg-bg-secondary rounded px-2 py-1 text-xs font-mono text-text-primary mt-2">
                  {plaintext}
                </code>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {/* Active Keys List */}
      <Card>
        <CardHeader>
          <CardTitle>Active Keys</CardTitle>
          <CardDescription>{keys.length} API key{keys.length !== 1 ? "s" : ""} configured</CardDescription>
        </CardHeader>
        <CardContent>
          {keys.length === 0 ? (
            <p className="text-sm text-text-muted py-4">No API keys yet. Create one to get started.</p>
          ) : (
            <div className="space-y-3">
              {keys.map((k) => (
                <div key={k.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-lg border border-border-default hover:bg-bg-secondary transition-colors">
                  <div className="flex-1">
                    <p className="font-medium text-text-primary">{k.name}</p>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {k.scopes.map((scope) => (
                        <Badge key={scope} variant="secondary" size="sm">{scope}</Badge>
                      ))}
                    </div>
                  </div>
                  {isAdmin && (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => revoke(k.id)}
                    >
                      Revoke
                    </Button>
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
