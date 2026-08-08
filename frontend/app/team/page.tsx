"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type WorkspaceProject, type ProjectMember, type ApprovalMatrixEntry } from "@/lib/api";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";

const ROLES = ["viewer", "reviewer", "estimator", "admin", "owner"];
const ROLE_LABELS: Record<string, string> = {
  viewer: "Viewer",
  reviewer: "Reviewer",
  estimator: "Estimator",
  admin: "Admin",
  owner: "Owner",
};

type Member = { user_id: string; email: string; role: string };
type Invitation = { invitation_id: string; email: string; role: string; project_id?: string | null; expires_at: string };

export default function TeamPage() {
  const { session } = useSession();
  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [invite, setInvite] = useState({ email: "", role: "viewer" });
  const [inviteToken, setInviteToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [approvalActions, setApprovalActions] = useState<string[]>([]);
  const [approvalLimits, setApprovalLimits] = useState<ApprovalMatrixEntry[]>([]);
  const [projects, setProjects] = useState<WorkspaceProject[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [projectMembers, setProjectMembers] = useState<ProjectMember[]>([]);
  const [projectInvite, setProjectInvite] = useState({ email: "", role: "viewer" });
  const [newProjectName, setNewProjectName] = useState("");

  const workspaceId = session?.workspaceId;

  const reload = useCallback(async () => {
    if (!session || !workspaceId) return;
    setError(null);
    try {
      const [m, i, a, p] = await Promise.all([
        api.listWorkspaceMembers(session.token, workspaceId),
        api.listInvitations(session.token),
        api.getApprovalMatrix(session.token, workspaceId),
        api.listWorkspaceProjects(session.token, workspaceId),
      ]);
      setMembers(m);
      setInvitations(i);
      setApprovalActions(a.actions);
      setApprovalLimits(a.limits);
      setProjects(p.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load team");
    }
  }, [session, workspaceId]);

  useEffect(() => {
    if (!session) return;
    if (!workspaceId) {
      setError("Select a workspace to manage the team.");
      return;
    }
    reload();
  }, [session, workspaceId, reload]);

  useEffect(() => {
    if (!session || !selectedProjectId) return;
    api.listProjectMembers(session.token, selectedProjectId)
      .then((r) => setProjectMembers(r.items))
      .catch(() => setProjectMembers([]));
  }, [session, selectedProjectId]);

  if (!session) {
    return null;
  }

  const sendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session || !workspaceId) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    setInviteToken(null);
    try {
      const result = await api.createInvitation(session.token, { email: invite.email, role: invite.role });
      setInvite({ email: "", role: "viewer" });
      setInviteToken(result.token ?? null);
      setMessage("Invitation created." + (result.token ? " Token shown below for dev/test use." : ""));
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Invitation failed");
    } finally {
      setLoading(false);
    }
  };

  const changeRole = async (user_id: string, role: string) => {
    if (!session || !workspaceId) return;
    try {
      await api.changeWorkspaceMemberRole(session.token, workspaceId, user_id, role);
      setMembers((prev) => prev.map((m) => (m.user_id === user_id ? { ...m, role } : m)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Role change failed");
    }
  };

  const removeMember = async (user_id: string) => {
    if (!session || !workspaceId) return;
    if (!confirm("Remove this member from the workspace?")) return;
    try {
      await api.removeWorkspaceMember(session.token, workspaceId, user_id);
      setMembers((prev) => prev.filter((m) => m.user_id !== user_id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Remove failed");
    }
  };

  const revoke = async (invitation_id: string) => {
    if (!session) return;
    try {
      await api.revokeInvitation(session.token, invitation_id);
      setInvitations((prev) => prev.filter((i) => i.invitation_id !== invitation_id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Revoke failed");
    }
  };

  const saveApprovalMatrix = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session || !workspaceId) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.updateApprovalMatrix(session.token, workspaceId, { limits: approvalLimits });
      setApprovalLimits(r.limits);
      setMessage("Approval matrix saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save approval matrix");
    } finally {
      setLoading(false);
    }
  };

  const addProjectMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session || !selectedProjectId) return;
    setLoading(true);
    setError(null);
    try {
      await api.addProjectMember(session.token, selectedProjectId, projectInvite);
      const r = await api.listProjectMembers(session.token, selectedProjectId);
      setProjectMembers(r.items);
      setProjectInvite({ email: "", role: "viewer" });
      setMessage("Project member added.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add project member");
    } finally {
      setLoading(false);
    }
  };

  const createProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session || !workspaceId || !newProjectName) return;
    setLoading(true);
    setError(null);
    try {
      await api.createWorkspaceProject(session.token, workspaceId, { name: newProjectName });
      setNewProjectName("");
      const r = await api.listWorkspaceProjects(session.token, workspaceId);
      setProjects(r.items);
      setMessage("Project created.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create project");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold text-text-primary">Team Management</h1>
        <p className="text-text-secondary">Manage team members, roles, and permissions.</p>
      </div>

      {/* Alerts */}
      {error && <Alert variant="error" title="Error">{error}</Alert>}
      {message && <Alert variant="success" title="Success">{message}</Alert>}

      {/* Invite Token */}
      {inviteToken && (
        <Card className="bg-info-bg border-info">
          <CardContent className="pt-6">
            <p className="text-sm text-info-text font-medium mb-2">Invitation token (for testing):</p>
            <code className="block text-xs bg-white border border-info rounded p-2 font-mono break-all text-text-primary">
              {inviteToken}
            </code>
          </CardContent>
        </Card>
      )}

      {/* Invite Form */}
      <Card>
        <CardHeader>
          <CardTitle>Invite Team Member</CardTitle>
          <CardDescription>Send an invitation to add a new member to your workspace.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={sendInvite} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="sm:col-span-2">
                <Input
                  type="email"
                  label="Email address"
                  placeholder="team@example.com"
                  value={invite.email}
                  onChange={(e) => setInvite({ ...invite, email: e.target.value })}
                  required
                />
              </div>
              <div>
                <label htmlFor="role" className="block text-sm font-medium text-text-primary mb-1.5">
                  Role
                </label>
                <select
                  id="role"
                  value={invite.role}
                  onChange={(e) => setInvite({ ...invite, role: e.target.value })}
                  className="w-full rounded-md border border-border-default bg-white px-3 py-2 text-sm text-text-primary focus:border-ink focus:ring-1 focus:ring-ink outline-none"
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {ROLE_LABELS[r]}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex justify-end">
              <Button type="submit" variant="primary" size="md" loading={loading}>
                Send Invite
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Members Section */}
      <Card>
        <CardHeader>
          <CardTitle>Team Members ({members.length})</CardTitle>
          <CardDescription>Members with access to this workspace.</CardDescription>
        </CardHeader>
        <CardContent>
          {members.length === 0 ? (
            <p className="text-sm text-text-muted py-8 text-center">No members in this workspace yet.</p>
          ) : (
            <div className="space-y-3">
              {members.map((m) => (
                <div
                  key={m.user_id}
                  className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 border border-border-default rounded-lg"
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-text-primary truncate">{m.email}</p>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <select
                      value={m.role}
                      onChange={(e) => changeRole(m.user_id, e.target.value)}
                      className="rounded-md border border-border-default bg-white px-3 py-2 text-sm text-text-primary focus:border-ink focus:ring-1 focus:ring-ink outline-none"
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {ROLE_LABELS[r]}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => removeMember(m.user_id)}
                      className="text-sm font-medium text-error hover:text-error/80 transition-colors"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pending Invitations Section */}
      <Card>
        <CardHeader>
          <CardTitle>Pending Invitations ({invitations.length})</CardTitle>
          <CardDescription>Invitations awaiting acceptance.</CardDescription>
        </CardHeader>
        <CardContent>
          {invitations.length === 0 ? (
            <p className="text-sm text-text-muted py-8 text-center">No pending invitations.</p>
          ) : (
            <div className="space-y-3">
              {invitations.map((i) => (
                <div
                  key={i.invitation_id}
                  className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 border border-border-default rounded-lg bg-bg-secondary"
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-text-primary truncate">{i.email}</p>
                    <p className="text-xs text-text-muted mt-1">
                      Expires {new Date(i.expires_at).toLocaleDateString("en-IN")}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <Badge variant="info" size="sm">
                      {ROLE_LABELS[i.role]}
                    </Badge>
                    <button
                      onClick={() => revoke(i.invitation_id)}
                      className="text-sm font-medium text-error hover:text-error/80 transition-colors"
                    >
                      Revoke
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Approval Matrix */}
      <Card>
        <CardHeader>
          <CardTitle>Approval Matrix</CardTitle>
          <CardDescription>Financial thresholds that require additional roles.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={saveApprovalMatrix} className="space-y-3">
            {approvalActions.length === 0 && approvalLimits.length === 0 && <p className="text-sm text-text-muted">No actions configured.</p>}
            {approvalLimits.map((limit, idx) => (
              <div key={limit.action} className="grid grid-cols-1 sm:grid-cols-3 gap-2 items-end">
                <div>
                  <label htmlFor={`am-action-${idx}`} className="text-xs text-text-muted">Action</label>
                  <input
                    id={`am-action-${idx}`}
                    value={limit.action}
                    readOnly
                    className="w-full rounded-md border border-border-default bg-bg-secondary px-3 py-2 text-sm text-text-muted"
                  />
                </div>
                <div>
                  <label htmlFor={`am-threshold-${idx}`} className="text-xs text-text-muted">Threshold (minor)</label>
                  <input
                    id={`am-threshold-${idx}`}
                    type="number"
                    value={limit.threshold_minor}
                    onChange={(e) => setApprovalLimits((prev) => prev.map((l, i) => i === idx ? { ...l, threshold_minor: Number(e.target.value) } : l))}
                    className="w-full rounded-md border border-border-default px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label htmlFor={`am-currency-${idx}`} className="text-xs text-text-muted">Currency</label>
                  <input
                    id={`am-currency-${idx}`}
                    value={limit.currency}
                    onChange={(e) => setApprovalLimits((prev) => prev.map((l, i) => i === idx ? { ...l, currency: e.target.value } : l))}
                    className="w-full rounded-md border border-border-default px-3 py-2 text-sm"
                  />
                </div>
              </div>
            ))}
            <Button type="submit" variant="primary" size="md" disabled={loading || approvalLimits.length === 0}>Save matrix</Button>
          </form>
        </CardContent>
      </Card>

      {/* Workspace Projects */}
      <Card>
        <CardHeader>
          <CardTitle>Workspace Projects</CardTitle>
          <CardDescription>Create and manage projects inside this workspace.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={createProject} className="flex flex-wrap gap-2">
            <input
              placeholder="Project name"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              className="flex-1 min-w-[200px] rounded-md border border-border-default px-3 py-2 text-sm"
              required
            />
            <Button type="submit" variant="primary" size="md" disabled={loading}>Create project</Button>
          </form>
          {projects.length === 0 ? (
            <p className="text-sm text-text-muted">No projects in this workspace.</p>
          ) : (
            <ul className="space-y-2">
              {projects.map((p) => (
                <li key={p.id}>
                  <button
                    onClick={() => setSelectedProjectId(p.id)}
                    className={`w-full text-left rounded-md border px-3 py-2 text-sm ${selectedProjectId === p.id ? "border-ink bg-bg-primary" : "border-border-default hover:border-ink"}`}
                  >
                    {p.name} <span className="text-xs text-text-muted">({p.status})</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {selectedProjectId && (
        <Card>
          <CardHeader>
            <CardTitle>Project Members</CardTitle>
            <CardDescription>Add and view members of the selected project.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={addProjectMember} className="flex flex-wrap gap-2">
              <input
                type="email"
                placeholder="Member email"
                value={projectInvite.email}
                onChange={(e) => setProjectInvite({ ...projectInvite, email: e.target.value })}
                className="flex-1 min-w-[200px] rounded-md border border-border-default px-3 py-2 text-sm"
                required
              />
              <select
                value={projectInvite.role}
                onChange={(e) => setProjectInvite({ ...projectInvite, role: e.target.value })}
                className="rounded-md border border-border-default px-3 py-2 text-sm"
              >
                {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
              </select>
              <Button type="submit" variant="primary" size="md" disabled={loading}>Add member</Button>
            </form>
            {projectMembers.length === 0 ? (
              <p className="text-sm text-text-muted">No members in this project.</p>
            ) : (
              <ul className="space-y-2">
                {projectMembers.map((m) => (
                  <li key={m.user_id} className="flex justify-between rounded-md border border-border-default px-3 py-2 text-sm">
                    <span>{m.email}</span>
                    <Badge variant="info" size="sm">{ROLE_LABELS[m.role] ?? m.role}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
