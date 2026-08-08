"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type User } from "@/lib/api";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { Dropdown, DropdownItem, DropdownSeparator } from "@/components/ui/dropdown";

export default function AdminUsersPage() {
  const { session } = useSession();
  const [users, setUsers] = useState<User[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createEmail, setCreateEmail] = useState("");
  const [createPassword, setCreatePassword] = useState("");
  const [createMessage, setCreateMessage] = useState<string | null>(null);

  const load = async () => {
    if (!session) return;
    setLoading(true);
    try {
      const r = await api.adminSearchUsers(session.token, query || undefined);
      setUsers(r.items);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load users");
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
    return null;
  }
  if (!session.is_superadmin) {
    return <Alert variant="error" title="Access Denied">Superadmin access required.</Alert>;
  }

  const createUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session) return;
    setLoading(true);
    setError(null);
    setCreateMessage(null);
    try {
      await api.adminCreateUser(session.token, { email: createEmail, password: createPassword });
      setCreateMessage("Superadmin created successfully.");
      setCreateEmail("");
      setCreatePassword("");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create user");
    } finally {
      setLoading(false);
    }
  };

  const suspend = async (id: string) => {
    if (!session) return;
    setLoading(true);
    try {
      await api.adminSuspendUser(session.token, id);
      await load();
    } finally {
      setLoading(false);
    }
  };

  const unsuspend = async (id: string) => {
    if (!session) return;
    setLoading(true);
    try {
      await api.adminUnsuspendUser(session.token, id);
      await load();
    } finally {
      setLoading(false);
    }
  };

  const deleteUser = async (id: string) => {
    if (!session || !confirm("Delete this user and all owned workspaces?")) return;
    setLoading(true);
    try {
      await api.adminDeleteUser(session.token, id);
      await load();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-heading-lg text-text-primary">User Management</h1>
        <p className="text-sm text-text-muted mt-2">Search and manage all users in the system</p>
      </div>

      {/* Alerts */}
      {error && <Alert variant="error" title="Error">{error}</Alert>}

      {/* Search */}
      <Card>
        <CardHeader>
          <CardTitle>Search Users</CardTitle>
          <CardDescription>Find users by email, phone, organization, or workspace</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={(e) => { e.preventDefault(); load(); }} className="flex gap-2">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by email, phone, org, workspace"
              className="flex-1 rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
              disabled={loading}
            />
            <Button variant="primary" size="md" type="submit" disabled={loading}>
              {loading ? "Searching..." : "Search"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Create superadmin */}
      <Card>
        <CardHeader>
          <CardTitle>Create Superadmin</CardTitle>
          <CardDescription>Create a new application-level superadmin user.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={createUser} className="flex flex-wrap gap-2">
            <input
              type="email"
              placeholder="Email"
              value={createEmail}
              onChange={(e) => setCreateEmail(e.target.value)}
              className="flex-1 min-w-[200px] rounded-md border border-border-default px-3 py-2 text-sm"
              required
            />
            <input
              type="password"
              placeholder="Password"
              value={createPassword}
              onChange={(e) => setCreatePassword(e.target.value)}
              className="flex-1 min-w-[200px] rounded-md border border-border-default px-3 py-2 text-sm"
              required
            />
            <Button variant="primary" size="md" type="submit" disabled={loading}>Create</Button>
          </form>
          {createMessage && <p className="mt-2 text-sm text-emerald-600">{createMessage}</p>}
        </CardContent>
      </Card>

      {/* Users List */}
      <Card>
        <CardHeader>
          <CardTitle>Users</CardTitle>
          <CardDescription>{users.length} user{users.length !== 1 ? "s" : ""} found</CardDescription>
        </CardHeader>
        <CardContent>
          {users.length === 0 ? (
            <p className="text-sm text-text-muted py-4">No users found. Try adjusting your search.</p>
          ) : (
            <div className="space-y-3">
              {users.map((u) => (
                <div key={u.user_id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-lg border border-border-default hover:bg-bg-secondary transition-colors">
                  <div className="flex-1">
                    <Link href={`/admin/users/${u.user_id}`} className="font-medium text-ink hover:underline">
                      {u.email}
                    </Link>
                    <p className="text-sm text-text-muted mt-1">{u.org_name || "No organization"}</p>
                    <div className="flex items-center gap-2 mt-2 flex-wrap">
                      {u.email_verified && <Badge variant="success" size="sm">Email verified</Badge>}
                      {u.mobile_verified && <Badge variant="success" size="sm">Mobile verified</Badge>}
                      {u.suspended_at && <Badge variant="warning" size="sm">Suspended</Badge>}
                    </div>
                  </div>
                  <Dropdown trigger={<Button variant="outline" size="sm">Actions ▼</Button>} align="right">
                    {u.suspended_at ? (
                      <DropdownItem onClick={() => unsuspend(u.user_id)} disabled={loading}>
                        Unsuspend
                      </DropdownItem>
                    ) : (
                      <DropdownItem onClick={() => suspend(u.user_id)} disabled={loading}>
                        Suspend
                      </DropdownItem>
                    )}
                    <DropdownSeparator />
                    <DropdownItem destructive onClick={() => deleteUser(u.user_id)} disabled={loading}>
                      Delete
                    </DropdownItem>
                  </Dropdown>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
