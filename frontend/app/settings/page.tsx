"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type AccountSettings, type ReportTemplate } from "@/lib/api";
import { useSession } from "@/components/session";

export default function SettingsPage() {
  const { session, signOut } = useSession();
  const router = useRouter();
  const [settings, setSettings] = useState<AccountSettings | null>(null);
  const [form, setForm] = useState({ org_name: "", city: "", phone: "", dob: "" });
  const [password, setPassword] = useState({ current: "", new: "", confirm: "" });
  const [emailChange, setEmailChange] = useState({ new_email: "", token: "", step: "form" as "form" | "verify" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [aclRules, setAclRules] = useState<{ id: string; document_class: string; min_role: string }[]>([]);
  const [aclForm, setAclForm] = useState({ document_class: "tender", min_role: "viewer" });
  const DOCUMENT_CLASSES = ["tender", "contract", "drawing", "boq", "schedule", "specification", "claim", "evidence", "general"];
  const ROLES = ["viewer", "reviewer", "estimator", "admin", "owner"];
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [templateForm, setTemplateForm] = useState<Partial<ReportTemplate>>({ name: "", report_title: "", footer_text: "", watermark_text: "", primary_color: "", logo_url: "" });
  const [editingTemplate, setEditingTemplate] = useState<string | null>(null);
  const [governance, setGovernance] = useState({ data_region: "", retention_days: "", archive_after_days: "", legal_hold: false, encryption_at_rest: "none" });
  const [retentionCandidates, setRetentionCandidates] = useState<{ id: string; filename: string; kind: string; opportunity_id: string; created_at: string }[]>([]);

  useEffect(() => {
    if (!session) return;
    api.getSettings(session.token)
      .then((s) => {
        setSettings(s);
        setForm({
          org_name: s.org_name ?? "",
          city: s.city ?? "",
          phone: s.phone ?? "",
          dob: s.dob ?? "",
        });
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load settings"));
    api.listDocumentClassAcls(session.token)
      .then((r) => setAclRules(r.rules))
      .catch(() => setAclRules([]));
    api.listReportTemplates(session.token)
      .then((r) => setTemplates(r.templates))
      .catch(() => setTemplates([]));
    if (session.workspaceId) {
      api.getDataGovernance(session.token, session.workspaceId)
        .then((r) => setGovernance({
          data_region: r.data_region || "",
          retention_days: r.retention_days != null ? String(r.retention_days) : "",
          archive_after_days: r.archive_after_days != null ? String(r.archive_after_days) : "",
          legal_hold: r.legal_hold || false,
          encryption_at_rest: r.encryption_at_rest || "none",
        }))
        .catch(() => {});
      api.listRetentionCandidates(session.token, session.workspaceId)
        .then((r) => setRetentionCandidates(r.candidates))
        .catch(() => setRetentionCandidates([]));
    }
  }, [session]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  const updateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const body: Parameters<typeof api.updateSettings>[1] = {};
      if (form.org_name !== (settings?.org_name ?? "")) body.org_name = form.org_name;
      if (form.city !== (settings?.city ?? "")) body.city = form.city;
      if (form.phone !== (settings?.phone ?? "")) body.phone = form.phone;
      if (form.dob !== (settings?.dob ?? "")) body.dob = form.dob || undefined;
      const updated = await api.updateSettings(session.token, body);
      setSettings(updated);
      setMessage("Profile updated." + (body.phone ? " A mobile verification code has been sent." : ""));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    } finally {
      setLoading(false);
    }
  };

  const requestEmailChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const r = await api.requestEmailChange(session.token, emailChange.new_email);
      setEmailChange({ ...emailChange, token: r.token, step: "verify" });
      setMessage("Verification code sent to new email.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Email change request failed");
    } finally {
      setLoading(false);
    }
  };

  const verifyEmailChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      await api.verifyEmailChange(session.token, emailChange.token);
      setEmailChange({ new_email: "", token: "", step: "form" });
      const updated = await api.getSettings(session.token);
      setSettings(updated);
      setMessage("Email updated.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Email verification failed");
    } finally {
      setLoading(false);
    }
  };

  const changePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session) return;
    if (password.new !== password.confirm) {
      setError("New password and confirmation do not match.");
      return;
    }
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      await api.changePassword(session.token, {
        current_password: password.current,
        new_password: password.new,
        confirm_password: password.confirm,
      });
      setPassword({ current: "", new: "", confirm: "" });
      setMessage("Password changed.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Password change failed");
    } finally {
      setLoading(false);
    }
  };

  const exportData = async () => {
    if (!session) return;
    setError(null);
    setMessage(null);
    try {
      const data = await api.exportAccount(session.token);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "account-export.json";
      a.click();
      window.URL.revokeObjectURL(url);
      setMessage("Account export downloaded.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    }
  };

  const deleteAccount = async () => {
    if (!session) return;
    const current = prompt("Enter your current password to delete your account:");
    if (!current) return;
    if (!confirm("This permanently deletes your account and workspaces. Continue?")) return;
    setError(null);
    setMessage(null);
    try {
      await api.deleteAccount(session.token, { password: current, confirm: true });
      signOut();
      router.push("/login");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Account deletion failed");
    }
  };

  const saveAcl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      await api.setDocumentClassAcl(session.token, aclForm);
      const r = await api.listDocumentClassAcls(session.token);
      setAclRules(r.rules);
      setMessage("Document class ACL updated.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update ACL");
    } finally {
      setLoading(false);
    }
  };

  const removeAcl = async (documentClass: string) => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      await api.deleteDocumentClassAcl(session.token, documentClass);
      const r = await api.listDocumentClassAcls(session.token);
      setAclRules(r.rules);
      setMessage("ACL removed.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove ACL");
    } finally {
      setLoading(false);
    }
  };

  const saveTemplate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      if (editingTemplate) {
        await api.updateReportTemplate(session.token, editingTemplate, templateForm);
      } else {
        await api.createReportTemplate(session.token, templateForm);
      }
      const r = await api.listReportTemplates(session.token);
      setTemplates(r.templates);
      setTemplateForm({ name: "", report_title: "", footer_text: "", watermark_text: "", primary_color: "", logo_url: "" });
      setEditingTemplate(null);
      setMessage("Report template saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save template");
    } finally {
      setLoading(false);
    }
  };

  const editTemplate = (t: ReportTemplate) => {
    setEditingTemplate(t.id);
    setTemplateForm({
      name: t.name,
      report_title: t.report_title ?? "",
      footer_text: t.footer_text ?? "",
      watermark_text: t.watermark_text ?? "",
      primary_color: t.primary_color ?? "",
      logo_url: t.logo_url ?? "",
    });
  };

  const deleteTemplate = async (id: string) => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      await api.deleteReportTemplate(session.token, id);
      const r = await api.listReportTemplates(session.token);
      setTemplates(r.templates);
      setMessage("Template deleted.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete template");
    } finally {
      setLoading(false);
    }
  };

  const setDefaultTemplate = async (id: string) => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      await api.setDefaultReportTemplate(session.token, id);
      const r = await api.listReportTemplates(session.token);
      setTemplates(r.templates);
      setMessage("Default template updated.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update default");
    } finally {
      setLoading(false);
    }
  };

  const saveGovernance = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session?.workspaceId) return;
    setLoading(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        data_region: governance.data_region,
        legal_hold: governance.legal_hold,
        encryption_at_rest: governance.encryption_at_rest,
      };
      if (governance.retention_days !== "") body.retention_days = Number(governance.retention_days);
      if (governance.archive_after_days !== "") body.archive_after_days = Number(governance.archive_after_days);
      await api.updateDataGovernance(session.token, session.workspaceId, body);
      setMessage("Data governance settings saved.");
      const c = await api.listRetentionCandidates(session.token, session.workspaceId);
      setRetentionCandidates(c.candidates);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save governance settings");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-ink">Account & Security</h1>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {message && <p className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">{message}</p>}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink">Profile</h2>
        {settings ? (
          <form onSubmit={updateProfile} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="settings-email" className="mb-1 block text-sm font-medium text-slate-700">Email</label>
                <input id="settings-email" readOnly value={settings.email} className="w-full rounded-md border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-500" />
                {settings.email_verified && <span className="text-xs text-green-600">Verified</span>}
              </div>
              <div>
                <label htmlFor="settings-phone" className="mb-1 block text-sm font-medium text-slate-700">Phone</label>
                <input
                  id="settings-phone"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
                {settings.mobile_verified ? (
                  <span className="text-xs text-green-600">Verified</span>
                ) : (
                  <span className="text-xs text-amber-600">Unverified</span>
                )}
              </div>
              <div>
                <label htmlFor="settings-org" className="mb-1 block text-sm font-medium text-slate-700">Organisation / Firm</label>
                <input
                  id="settings-org"
                  value={form.org_name}
                  onChange={(e) => setForm({ ...form, org_name: e.target.value })}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label htmlFor="settings-city" className="mb-1 block text-sm font-medium text-slate-700">City</label>
                <input
                  id="settings-city"
                  value={form.city}
                  onChange={(e) => setForm({ ...form, city: e.target.value })}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label htmlFor="settings-dob" className="mb-1 block text-sm font-medium text-slate-700">Date of Birth</label>
                <input
                  id="settings-dob"
                  type="date"
                  value={form.dob}
                  onChange={(e) => setForm({ ...form, dob: e.target.value })}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              Save profile
            </button>
          </form>
        ) : (
          <p className="text-sm text-slate-500">Loading profile...</p>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-ink">Notification preferences</h2>
          <Link href="/settings/notifications" className="text-sm text-indigo-600 hover:underline">Edit preferences</Link>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink">Email</h2>
        {emailChange.step === "form" ? (
          <form onSubmit={requestEmailChange} className="space-y-4">
            <div>
              <label htmlFor="settings-new-email" className="mb-1 block text-sm font-medium text-slate-700">New email</label>
              <input
                id="settings-new-email"
                type="email"
                value={emailChange.new_email}
                onChange={(e) => setEmailChange({ ...emailChange, new_email: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                required
              />
            </div>
            <button type="submit" disabled={loading} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
              Request email change
            </button>
          </form>
        ) : (
          <form onSubmit={verifyEmailChange} className="space-y-4">
            <p className="text-sm text-slate-600">A verification code was sent to {emailChange.new_email}.</p>
            <div>
              <label htmlFor="settings-email-token" className="mb-1 block text-sm font-medium text-slate-700">Verification code</label>
              <input
                id="settings-email-token"
                value={emailChange.token}
                onChange={(e) => setEmailChange({ ...emailChange, token: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                required
              />
            </div>
            <button type="submit" disabled={loading} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
              Verify new email
            </button>
          </form>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink">Document class access</h2>
        <p className="mb-4 text-sm text-slate-600">Set the minimum role required to upload or view each document class. No rule means everyone in the workspace has access.</p>
        <form onSubmit={saveAcl} className="mb-4 grid gap-3 sm:grid-cols-4">
          <select className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={aclForm.document_class} onChange={(e) => setAclForm({ ...aclForm, document_class: e.target.value })}>
            {DOCUMENT_CLASSES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={aclForm.min_role} onChange={(e) => setAclForm({ ...aclForm, min_role: e.target.value })}>
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <button type="submit" disabled={loading} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50 sm:col-span-2">Save rule</button>
        </form>
        {aclRules.length > 0 && (
          <ul className="space-y-2">
            {aclRules.map((r) => (
              <li key={r.id} className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
                <span className="capitalize">{r.document_class}</span>
                <span className="text-slate-600">min role: {r.min_role}</span>
                <button onClick={() => removeAcl(r.document_class)} disabled={loading} className="text-sm text-red-600 hover:underline disabled:opacity-50">Remove</button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink">Report templates</h2>
        <p className="mb-4 text-sm text-slate-600">Customise the title, footer and watermark for exported reports. The default template is applied automatically.</p>
        <form onSubmit={saveTemplate} className="mb-4 grid gap-3 sm:grid-cols-2">
          <input placeholder="Template name" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={templateForm.name || ""} onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })} required />
          <input placeholder="Report title (e.g. Bid Review Pack)" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={templateForm.report_title || ""} onChange={(e) => setTemplateForm({ ...templateForm, report_title: e.target.value })} />
          <input placeholder="Footer text" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={templateForm.footer_text || ""} onChange={(e) => setTemplateForm({ ...templateForm, footer_text: e.target.value })} />
          <input placeholder="Watermark text" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={templateForm.watermark_text || ""} onChange={(e) => setTemplateForm({ ...templateForm, watermark_text: e.target.value })} />
          <input placeholder="Primary colour (hex)" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={templateForm.primary_color || ""} onChange={(e) => setTemplateForm({ ...templateForm, primary_color: e.target.value })} />
          <input placeholder="Logo URL" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={templateForm.logo_url || ""} onChange={(e) => setTemplateForm({ ...templateForm, logo_url: e.target.value })} />
          <button type="submit" disabled={loading} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50 sm:col-span-2">{editingTemplate ? "Update template" : "Create template"}</button>
        </form>
        {templates.length > 0 && (
          <ul className="space-y-2">
            {templates.map((t) => (
              <li key={t.id} className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
                <span>{t.name} {t.is_default && <span className="ml-2 rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-700">default</span>}</span>
                <div className="flex gap-3">
                  <button onClick={() => editTemplate(t)} disabled={loading} className="text-indigo-600 hover:underline disabled:opacity-50">Edit</button>
                  {!t.is_default && <button onClick={() => setDefaultTemplate(t.id)} disabled={loading} className="text-indigo-600 hover:underline disabled:opacity-50">Set default</button>}
                  <button onClick={() => deleteTemplate(t.id)} disabled={loading} className="text-red-600 hover:underline disabled:opacity-50">Delete</button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink">Data governance</h2>
        <form onSubmit={saveGovernance} className="mb-4 grid gap-3 sm:grid-cols-2">
          <input placeholder="Data region (e.g. IN, EU, US)" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={governance.data_region} onChange={(e) => setGovernance({ ...governance, data_region: e.target.value })} />
          <select className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={governance.encryption_at_rest} onChange={(e) => setGovernance({ ...governance, encryption_at_rest: e.target.value })}>
            <option value="none">No encryption at rest (default)</option>
            <option value="sse-s3">SSE-S3</option>
            <option value="aws:kms">AWS KMS</option>
          </select>
          <input type="number" min={1} placeholder="Retention days" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={governance.retention_days} onChange={(e) => setGovernance({ ...governance, retention_days: e.target.value })} />
          <input type="number" min={1} placeholder="Archive after days" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={governance.archive_after_days} onChange={(e) => setGovernance({ ...governance, archive_after_days: e.target.value })} />
          <label className="flex items-center gap-2 text-sm text-slate-700 sm:col-span-2">
            <input type="checkbox" checked={governance.legal_hold} onChange={(e) => setGovernance({ ...governance, legal_hold: e.target.checked })} />
            Legal hold (blocks retention actions)
          </label>
          <button type="submit" disabled={loading} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50 sm:col-span-2">Save data governance</button>
        </form>
        {retentionCandidates.length > 0 && (
          <div className="mt-4">
            <h3 className="text-sm font-semibold text-slate-700">Retention candidates ({retentionCandidates.length})</h3>
            <ul className="mt-2 space-y-2">
              {retentionCandidates.map((d) => (
                <li key={d.id} className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
                  <span>{d.filename} <span className="text-slate-500">({d.kind})</span></span>
                  <span className="text-slate-500">{new Date(d.created_at).toLocaleDateString()}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink">Security</h2>
        <form onSubmit={changePassword} className="space-y-4">
          <div>
            <label htmlFor="settings-current-password" className="mb-1 block text-sm font-medium text-slate-700">Current password</label>
            <input
              id="settings-current-password"
              type="password"
              value={password.current}
              onChange={(e) => setPassword({ ...password, current: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              required
            />
          </div>
          <div>
            <label htmlFor="settings-new-password" className="mb-1 block text-sm font-medium text-slate-700">New password</label>
            <input
              id="settings-new-password"
              type="password"
              value={password.new}
              onChange={(e) => setPassword({ ...password, new: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              required
              minLength={8}
            />
          </div>
          <div>
            <label htmlFor="settings-confirm-password" className="mb-1 block text-sm font-medium text-slate-700">Confirm new password</label>
            <input
              id="settings-confirm-password"
              type="password"
              value={password.confirm}
              onChange={(e) => setPassword({ ...password, confirm: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              required
              minLength={8}
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Change password
          </button>
        </form>

        <div className="mt-6 flex flex-wrap gap-3 border-t border-slate-100 pt-4">
          <button
            onClick={signOut}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Sign out
          </button>
          <button
            onClick={exportData}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Export account data
          </button>
          <button
            onClick={deleteAccount}
            className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            Delete account
          </button>
        </div>
      </section>
    </div>
  );
}
