"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type AccountSettings, type ReportTemplate } from "@/lib/api";
import { useSession } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { Modal, ModalBody, ModalFooter } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";

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
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");

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
    if (!session || !deletePassword) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      await api.deleteAccount(session.token, { password: deletePassword, confirm: true });
      setDeleteModalOpen(false);
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
      {/* Header */}
      <div>
        <h1 className="text-heading-lg text-text-primary">Account & Security Settings</h1>
        <p className="text-sm text-text-muted mt-2">Manage your profile, security, and preferences</p>
      </div>

      {/* Alerts */}
      {error && <Alert variant="error" title="Error">{error}</Alert>}
      {message && <Alert variant="success" title="Success">{message}</Alert>}

      {/* Profile Section */}
      <Card>
        <CardHeader>
          <CardTitle>Profile Information</CardTitle>
          <CardDescription>Update your personal and organization details</CardDescription>
        </CardHeader>
        <CardContent>
          {settings ? (
            <form onSubmit={updateProfile} className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label htmlFor="settings-email" className="block text-sm font-medium text-text-primary mb-2">Email</label>
                  <div className="flex items-center gap-2">
                    <input
                      id="settings-email"
                      readOnly
                      value={settings.email}
                      className="flex-1 rounded-md border border-border-default bg-bg-secondary px-3 py-2 text-sm text-text-muted"
                    />
                    {settings.email_verified && (
                      <Badge variant="success" size="sm">Verified</Badge>
                    )}
                  </div>
                </div>
                <div>
                  <label htmlFor="settings-phone" className="block text-sm font-medium text-text-primary mb-2">Phone</label>
                  <div className="flex items-center gap-2">
                    <input
                      id="settings-phone"
                      type="tel"
                      value={form.phone}
                      onChange={(e) => setForm({ ...form, phone: e.target.value })}
                      className="flex-1 rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                    />
                    {settings.mobile_verified ? (
                      <Badge variant="success" size="sm">Verified</Badge>
                    ) : (
                      <Badge variant="warning" size="sm">Verify</Badge>
                    )}
                  </div>
                </div>
                <div>
                  <label htmlFor="settings-org" className="block text-sm font-medium text-text-primary mb-2">Organization / Firm</label>
                  <input
                    id="settings-org"
                    type="text"
                    placeholder="Your company name"
                    value={form.org_name}
                    onChange={(e) => setForm({ ...form, org_name: e.target.value })}
                    className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                  />
                </div>
                <div>
                  <label htmlFor="settings-city" className="block text-sm font-medium text-text-primary mb-2">City</label>
                  <input
                    id="settings-city"
                    type="text"
                    placeholder="Your city"
                    value={form.city}
                    onChange={(e) => setForm({ ...form, city: e.target.value })}
                    className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                  />
                </div>
                <div className="md:col-span-2">
                  <label htmlFor="settings-dob" className="block text-sm font-medium text-text-primary mb-2">Date of Birth</label>
                  <input
                    id="settings-dob"
                    type="date"
                    value={form.dob}
                    onChange={(e) => setForm({ ...form, dob: e.target.value })}
                    className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                  />
                </div>
              </div>
              <Button variant="primary" size="md" type="submit" disabled={loading}>
                {loading ? "Saving..." : "Save Profile"}
              </Button>
            </form>
          ) : (
            <p className="text-sm text-text-muted py-4">Loading profile...</p>
          )}
        </CardContent>
      </Card>

      {/* Email Change Section */}
      <Card>
        <CardHeader>
          <CardTitle>Change Email</CardTitle>
          <CardDescription>Update your email address securely</CardDescription>
        </CardHeader>
        <CardContent>
          {emailChange.step === "form" ? (
            <form onSubmit={requestEmailChange} className="space-y-4">
              <div>
                <label htmlFor="settings-new-email" className="block text-sm font-medium text-text-primary mb-2">New Email <span className="text-error">*</span></label>
                <input
                  id="settings-new-email"
                  type="email"
                  placeholder="your.newemail@example.com"
                  value={emailChange.new_email}
                  onChange={(e) => setEmailChange({ ...emailChange, new_email: e.target.value })}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                  required
                />
              </div>
              <Button variant="primary" size="md" type="submit" disabled={loading}>
                {loading ? "Sending..." : "Request Email Change"}
              </Button>
            </form>
          ) : (
            <form onSubmit={verifyEmailChange} className="space-y-4">
              <Alert variant="info" title="Verification Code Sent">
                A verification code was sent to <strong>{emailChange.new_email}</strong>
              </Alert>
              <div>
                <label htmlFor="settings-email-token" className="block text-sm font-medium text-text-primary mb-2">Verification Code <span className="text-error">*</span></label>
                <input
                  id="settings-email-token"
                  type="text"
                  placeholder="Enter code"
                  value={emailChange.token}
                  onChange={(e) => setEmailChange({ ...emailChange, token: e.target.value })}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                  required
                />
              </div>
              <Button variant="primary" size="md" type="submit" disabled={loading}>
                {loading ? "Verifying..." : "Verify & Update Email"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>

      {/* Quick Links */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Notification Preferences</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-text-muted mb-4">Manage how you receive notifications</p>
            <Link href="/settings/notifications">
              <Button variant="outline" size="md" className="w-full">
                Edit Preferences
              </Button>
            </Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">API & Integrations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <Link href="/settings/api-keys">
                <Button variant="outline" size="sm" className="w-full">
                  Manage API Keys
                </Button>
              </Link>
              <Link href="/settings/integrations">
                <Button variant="outline" size="sm" className="w-full">
                  Manage Integrations
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Document Access Control */}
      <Card>
        <CardHeader>
          <CardTitle>Document Access Control</CardTitle>
          <CardDescription>Set minimum role requirements for document classes</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={saveAcl} className="grid gap-3 md:grid-cols-4">
            <select
              value={aclForm.document_class}
              onChange={(e) => setAclForm({ ...aclForm, document_class: e.target.value })}
              className="rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
            >
              {DOCUMENT_CLASSES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <select
              value={aclForm.min_role}
              onChange={(e) => setAclForm({ ...aclForm, min_role: e.target.value })}
              className="rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <Button variant="primary" size="md" type="submit" disabled={loading} className="md:col-span-2">
              {loading ? "Saving..." : "Save Rule"}
            </Button>
          </form>

          {aclRules.length > 0 && (
            <div className="space-y-2 border-t border-border-default pt-4">
              <p className="text-sm font-medium text-text-primary">Active Rules</p>
              {aclRules.map((r) => (
                <div key={r.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 p-3 rounded-lg bg-bg-secondary">
                  <div>
                    <p className="text-sm font-medium text-text-primary capitalize">{r.document_class}</p>
                    <p className="text-xs text-text-muted">min role: {r.min_role}</p>
                  </div>
                  <Button variant="destructive" size="sm" onClick={() => removeAcl(r.document_class)} disabled={loading}>
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Report Templates */}
      <Card>
        <CardHeader>
          <CardTitle>Report Templates</CardTitle>
          <CardDescription>Customize export layouts with your branding</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={saveTemplate} className="grid gap-3 md:grid-cols-2">
            <input
              type="text"
              placeholder="Template name"
              className="rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
              value={templateForm.name || ""}
              onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })}
              required
            />
            <input
              type="text"
              placeholder="Report title"
              className="rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
              value={templateForm.report_title || ""}
              onChange={(e) => setTemplateForm({ ...templateForm, report_title: e.target.value })}
            />
            <input
              type="text"
              placeholder="Footer text"
              className="rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
              value={templateForm.footer_text || ""}
              onChange={(e) => setTemplateForm({ ...templateForm, footer_text: e.target.value })}
            />
            <input
              type="text"
              placeholder="Watermark text"
              className="rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
              value={templateForm.watermark_text || ""}
              onChange={(e) => setTemplateForm({ ...templateForm, watermark_text: e.target.value })}
            />
            <input
              type="text"
              placeholder="Primary color (hex)"
              className="rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
              value={templateForm.primary_color || ""}
              onChange={(e) => setTemplateForm({ ...templateForm, primary_color: e.target.value })}
            />
            <input
              type="url"
              placeholder="Logo URL"
              className="rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
              value={templateForm.logo_url || ""}
              onChange={(e) => setTemplateForm({ ...templateForm, logo_url: e.target.value })}
            />
            <Button variant="primary" size="md" type="submit" disabled={loading} className="md:col-span-2">
              {editingTemplate ? "Update Template" : "Create Template"}
            </Button>
          </form>

          {templates.length > 0 && (
            <div className="space-y-2 border-t border-border-default pt-4">
              <p className="text-sm font-medium text-text-primary">Saved Templates</p>
              {templates.map((t) => (
                <div key={t.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 p-3 rounded-lg bg-bg-secondary">
                  <div>
                    <p className="text-sm font-medium text-text-primary">{t.name}</p>
                    {t.is_default && <Badge variant="success" size="sm" className="mt-1">Default</Badge>}
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => editTemplate(t)} disabled={loading}>
                      Edit
                    </Button>
                    {!t.is_default && (
                      <Button variant="outline" size="sm" onClick={() => setDefaultTemplate(t.id)} disabled={loading}>
                        Set Default
                      </Button>
                    )}
                    <Button variant="destructive" size="sm" onClick={() => deleteTemplate(t.id)} disabled={loading}>
                      Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Data Governance */}
      <Card>
        <CardHeader>
          <CardTitle>Data Governance</CardTitle>
          <CardDescription>Configure data residency, retention, and encryption</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={saveGovernance} className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-text-primary mb-2">Data Region</label>
                <input
                  type="text"
                  placeholder="e.g., IN, EU, US"
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                  value={governance.data_region}
                  onChange={(e) => setGovernance({ ...governance, data_region: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-primary mb-2">Encryption at Rest</label>
                <select
                  value={governance.encryption_at_rest}
                  onChange={(e) => setGovernance({ ...governance, encryption_at_rest: e.target.value })}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                >
                  <option value="none">None (default)</option>
                  <option value="sse-s3">SSE-S3</option>
                  <option value="aws:kms">AWS KMS</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-primary mb-2">Retention Days</label>
                <input
                  type="number"
                  min={1}
                  placeholder="Leave blank for no retention"
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                  value={governance.retention_days}
                  onChange={(e) => setGovernance({ ...governance, retention_days: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-primary mb-2">Archive After Days</label>
                <input
                  type="number"
                  min={1}
                  placeholder="Leave blank for no archival"
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                  value={governance.archive_after_days}
                  onChange={(e) => setGovernance({ ...governance, archive_after_days: e.target.value })}
                />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm text-text-primary">
              <input
                type="checkbox"
                checked={governance.legal_hold}
                onChange={(e) => setGovernance({ ...governance, legal_hold: e.target.checked })}
                className="h-4 w-4 accent-ink"
              />
              Legal Hold (blocks retention actions)
            </label>
            <Button variant="primary" size="md" type="submit" disabled={loading}>
              {loading ? "Saving..." : "Save Governance Settings"}
            </Button>
          </form>

          {retentionCandidates.length > 0 && (
            <div className="mt-6 border-t border-border-default pt-4">
              <p className="text-sm font-medium text-text-primary mb-3">Retention Candidates ({retentionCandidates.length})</p>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {retentionCandidates.map((d) => (
                  <div key={d.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 p-3 rounded-lg bg-bg-secondary text-sm">
                    <div>
                      <p className="font-medium text-text-primary">{d.filename}</p>
                      <p className="text-xs text-text-muted">{d.kind} • {new Date(d.created_at).toLocaleDateString("en-IN")}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Security Section */}
      <Card>
        <CardHeader>
          <CardTitle>Security</CardTitle>
          <CardDescription>Manage passwords and sensitive account actions</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Change Password */}
          <div className="border-b border-border-default pb-6">
            <h3 className="text-sm font-medium text-text-primary mb-4">Change Password</h3>
            <form onSubmit={changePassword} className="space-y-4">
              <div>
                <label htmlFor="settings-current-password" className="block text-sm font-medium text-text-primary mb-2">Current Password <span className="text-error">*</span></label>
                <input
                  id="settings-current-password"
                  type="password"
                  value={password.current}
                  onChange={(e) => setPassword({ ...password, current: e.target.value })}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                  required
                />
              </div>
              <div>
                <label htmlFor="settings-new-password" className="block text-sm font-medium text-text-primary mb-2">New Password <span className="text-error">*</span></label>
                <input
                  id="settings-new-password"
                  type="password"
                  minLength={8}
                  value={password.new}
                  onChange={(e) => setPassword({ ...password, new: e.target.value })}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                  required
                />
              </div>
              <div>
                <label htmlFor="settings-confirm-password" className="block text-sm font-medium text-text-primary mb-2">Confirm Password <span className="text-error">*</span></label>
                <input
                  id="settings-confirm-password"
                  type="password"
                  minLength={8}
                  value={password.confirm}
                  onChange={(e) => setPassword({ ...password, confirm: e.target.value })}
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                  required
                />
              </div>
              <Button variant="primary" size="md" type="submit" disabled={loading}>
                {loading ? "Updating..." : "Change Password"}
              </Button>
            </form>
          </div>

          {/* Account Actions */}
          <div>
            <h3 className="text-sm font-medium text-text-primary mb-4">Account Actions</h3>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="md" onClick={signOut}>
                Sign Out
              </Button>
              <Button variant="outline" size="md" onClick={exportData}>
                Export Data
              </Button>
              <Button variant="destructive" size="md" onClick={() => setDeleteModalOpen(true)}>
                Delete Account
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Delete Account Confirmation Modal */}
      <Modal isOpen={deleteModalOpen} onClose={() => setDeleteModalOpen(false)} title="Delete Account" size="md">
        <ModalBody>
          <div className="space-y-4">
            <Alert variant="error">
              <p className="text-sm font-medium">⚠️ This action cannot be undone.</p>
            </Alert>
            <p className="text-text-secondary text-sm">
              Deleting your account will:
            </p>
            <ul className="list-disc list-inside space-y-1 text-text-secondary text-sm">
              <li>Permanently delete your account and all data</li>
              <li>Remove you from all workspaces</li>
              <li>Delete all your projects and opportunities</li>
            </ul>
            <div>
              <label className="block text-sm font-medium text-text-primary mb-2">
                Enter your password to confirm:
              </label>
              <Input
                type="password"
                value={deletePassword}
                onChange={(e) => setDeletePassword(e.target.value)}
                placeholder="Current password"
                disabled={loading}
              />
            </div>
          </div>
        </ModalBody>
        <ModalFooter>
          <Button
            onClick={() => {
              setDeleteModalOpen(false);
              setDeletePassword("");
            }}
            variant="secondary"
            disabled={loading}
          >
            Cancel
          </Button>
          <Button
            onClick={deleteAccount}
            variant="destructive"
            disabled={!deletePassword || loading}
            loading={loading}
          >
            Delete Account
          </Button>
        </ModalFooter>
      </Modal>
    </div>
  );
}
