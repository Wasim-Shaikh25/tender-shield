"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useSession } from "@/components/session";

const ROLES = ["viewer", "reviewer", "estimator", "admin", "owner"];

type Member = { user_id: string; email: string; role: string };
type Invitation = { invitation_id: string; email: string; role: string; project_id?: string | null; expires_at: string };

export default function TeamPage() {
  const { session } = useSession();
  const router = useRouter();
  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [invite, setInvite] = useState({ email: "", role: "viewer" });
  const [inviteToken, setInviteToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const workspaceId = session?.workspaceId;

  const reload = useCallback(async () => {
    if (!session || !workspaceId) return;
    setError(null);
    try {
      const [m, i] = await Promise.all([
        api.listWorkspaceMembers(session.token, workspaceId),
        api.listInvitations(session.token),
      ]);
      setMembers(m);
      setInvitations(i);
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

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
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

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-ink">Team</h1>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {message && <p className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">{message}</p>}
      {inviteToken && (
        <div className="rounded-md bg-slate-50 p-3 text-sm break-all font-mono text-slate-700">
          Invitation token: {inviteToken}
        </div>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink">Invite member</h2>
        <form onSubmit={sendInvite} className="flex flex-col gap-4 sm:flex-row">
          <input
            type="email"
            placeholder="Email"
            value={invite.email}
            onChange={(e) => setInvite({ ...invite, email: e.target.value })}
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
            required
          />
          <select
            value={invite.role}
            onChange={(e) => setInvite({ ...invite, role: e.target.value })}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Invite
          </button>
        </form>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink">Members</h2>
        {members.length === 0 ? (
          <p className="text-sm text-slate-500">No members found.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 text-left text-slate-500">
              <tr>
                <th className="py-2">Email</th>
                <th className="py-2">Role</th>
                <th className="py-2"></th>
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.user_id} className="border-b border-slate-100">
                  <td className="py-2">{m.email}</td>
                  <td className="py-2">
                    <select
                      value={m.role}
                      onChange={(e) => changeRole(m.user_id, e.target.value)}
                      className="rounded-md border border-slate-300 px-2 py-1 text-sm"
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="py-2 text-right">
                    <button
                      onClick={() => removeMember(m.user_id)}
                      className="text-sm text-red-600 hover:underline"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink">Pending invitations</h2>
        {invitations.length === 0 ? (
          <p className="text-sm text-slate-500">No pending invitations.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 text-left text-slate-500">
              <tr>
                <th className="py-2">Email</th>
                <th className="py-2">Role</th>
                <th className="py-2">Expires</th>
                <th className="py-2"></th>
              </tr>
            </thead>
            <tbody>
              {invitations.map((i) => (
                <tr key={i.invitation_id} className="border-b border-slate-100">
                  <td className="py-2">{i.email}</td>
                  <td className="py-2 capitalize">{i.role}</td>
                  <td className="py-2">{new Date(i.expires_at).toLocaleDateString()}</td>
                  <td className="py-2 text-right">
                    <button
                      onClick={() => revoke(i.invitation_id)}
                      className="text-sm text-red-600 hover:underline"
                    >
                      Revoke
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
