// Typed client for the TenderShield API. Base URL from env; every mutating call
// is workspace-scoped server-side (RLS) — the client just carries the bearer token.
//
// Auth contract types are generated from the backend OpenAPI spec (`lib/api-types.ts`)
// so the frontend cannot drift from the backend response shape.
import type { components } from "./api-types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

export type Tokens = components["schemas"]["TokenResponse"];
export type LoginResponse = components["schemas"]["LoginResponse"];
export type Workspace = components["schemas"]["WorkspaceResponse"];
export type AccountSettings = components["schemas"]["AccountSettingsResponse"];
export type User = {
  user_id: string;
  email: string;
  phone?: string;
  org_name?: string;
  city?: string;
  role?: string;
  is_superadmin?: boolean;
  email_verified?: boolean;
  mobile_verified?: boolean;
  suspended_at?: string | null;
  created_at?: string | null;
  dob?: string | null;
  workspaces?: Array<{ workspace_id: string; name: string; role: string }>;
};
export type Opportunity = { id: string; title: string; status: string; submission_due?: string | null };
export type MissingDocs = { present: string[]; missing: string[]; expected: string[] };
export type Clause = { id: string; clause_ref: string | null; heading: string | null; page_from: number | null };
export type Deadline = {
  id: string;
  kind: string;
  due_at: string | null;
  description: string | null;
  source_page: number | null;
  source_quote: string | null;
  confirmed: boolean;
};
export type Finding = {
  id?: string;
  producer?: string;
  category: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  title: string;
  detail: string;
  source?: string;
  source_page: number | null;
  source_quote: string | null;
  pattern_id?: string | null;
  review_status?: string;
  disclaimer?: string | null;
};

type SignupResponse = components["schemas"]["SignupResponse"];
type ForgotPasswordResponse = components["schemas"]["ForgotPasswordResponse"];
type OkResponse = components["schemas"]["OkResponse"];
type MeResponse = components["schemas"]["MeResponse"];
type WorkspaceCreateResponse = components["schemas"]["WorkspaceCreateResponse"];
type MemberResponse = components["schemas"]["MemberResponse"];
type ChangeRoleResponse = components["schemas"]["ChangeRoleResponse"];
type InvitationResponse = components["schemas"]["InvitationResponse"];
type InvitationCreateResponse = components["schemas"]["InvitationCreateResponse"];
type AcceptInvitationResponse = components["schemas"]["AcceptInvitationResponse"];

async function req<T>(path: string, opts: RequestInit = {}, token?: string): Promise<T> {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string> ?? {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const bodyIsJson =
    opts.body && typeof opts.body === "string" &&
    !headers["Content-Type"] &&
    (opts.body.startsWith("{") || opts.body.startsWith("["));
  if (bodyIsJson && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...opts,
    credentials: "include",
    headers,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  signup: (body: {
    email: string;
    phone: string;
    password: string;
    confirm_password: string;
    org_name: string;
    city: string;
    dob?: string;
  }) =>
    req<SignupResponse>("/auth/signup", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  login: (email: string, password: string) =>
    req<LoginResponse>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  forgotPassword: (email: string) =>
    req<ForgotPasswordResponse>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  resetPassword: (token: string, new_password: string) =>
    req<OkResponse>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password }),
    }),
  refresh: () => req<Tokens>("/auth/refresh", { method: "POST" }),
  mfaChallenge: (mfa_token: string, code: string) =>
    req<Tokens>("/auth/mfa/challenge", {
      method: "POST",
      body: JSON.stringify({ mfa_token, code }),
    }),
  verifyEmail: (token: string) =>
    req<boolean>("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  verifyMobile: (token: string) =>
    req<boolean>("/auth/verify-mobile", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  me: (token: string) => req<MeResponse>("/auth/me", {}, token),
  listWorkspaces: (token: string) => req<Workspace[]>("/auth/workspaces", {}, token),
  switchWorkspace: (token: string, workspace_id: string) =>
    req<Tokens>(`/auth/workspaces/${workspace_id}/switch`, { method: "POST" }, token),
  getSettings: (token: string) => req<AccountSettings>("/auth/settings", {}, token),
  updateSettings: (token: string, body: Partial<Omit<AccountSettings, "email" | "email_verified" | "mobile_verified">>) =>
    req<AccountSettings>("/auth/settings", { method: "PUT", body: JSON.stringify(body) }, token),
  changePassword: (token: string, body: { current_password: string; new_password: string; confirm_password: string }) =>
    req<OkResponse>("/auth/settings/password", { method: "POST", body: JSON.stringify(body) }, token),
  listWorkspaceMembers: (token: string, workspace_id: string) =>
    req<MemberResponse[]>(`/auth/workspaces/${workspace_id}/members`, {}, token),
  addWorkspaceMember: (token: string, workspace_id: string, body: { email: string; role: string }) =>
    req<MemberResponse>(`/auth/workspaces/${workspace_id}/members`, { method: "POST", body: JSON.stringify(body) }, token),
  changeWorkspaceMemberRole: (token: string, workspace_id: string, user_id: string, role: string) =>
    req<ChangeRoleResponse>(`/auth/workspaces/${workspace_id}/members/${user_id}`, { method: "PUT", body: JSON.stringify({ role }) }, token),
  removeWorkspaceMember: (token: string, workspace_id: string, user_id: string) =>
    req<OkResponse>(`/auth/workspaces/${workspace_id}/members/${user_id}`, { method: "DELETE" }, token),
  listInvitations: (token: string) =>
    req<InvitationResponse[]>("/auth/invitations", {}, token),
  createInvitation: (token: string, body: { email: string; role: string; project_id?: string }) =>
    req<InvitationCreateResponse>("/auth/invitations", { method: "POST", body: JSON.stringify(body) }, token),
  revokeInvitation: (token: string, invitation_id: string) =>
    req<OkResponse>(`/auth/invitations/${invitation_id}`, { method: "DELETE" }, token),
  acceptInvitation: (token: string, tokenStr: string) =>
    req<AcceptInvitationResponse>(`/auth/invitations/${tokenStr}/accept`, { method: "POST" }, token),
  createWorkspace: (token: string, body: { name: string; country?: string }) =>
    req<WorkspaceCreateResponse>("/auth/workspaces", {
      method: "POST",
      body: JSON.stringify(body),
    }, token),
  billingStatus: (token: string) => req<{ plan: string; reviews_used: number; reviews_limit: number | null; seats: number }>("/billing/status", {}, token),
  listInvoices: (token: string) => req<{ invoices: { id: string; invoice_number: string; amount_minor: number; currency: string; status: string; provider: string; paid_at: string | null; created_at: string }[] }>("/billing/invoices", {}, token),
  listPayments: (token: string) => req<{ payments: { id: string; provider: string; provider_event_id: string | null; event_type: string; amount_minor: number | null; currency: string | null; status: string; created_at: string }[] }>("/billing/payments", {}, token),
  listPlanHistory: (token: string) => req<{ history: { id: string; old_plan: string; new_plan: string; changed_by: string | null; reason: string | null; created_at: string }[] }>("/billing/plan-history", {}, token),
  checkout: (token: string, body: { provider?: string; kind: string; plan?: string; amount_minor?: number; coupon_code?: string }) =>
    req<{ provider: string; order_id?: string; session_id?: string; mock: boolean; note: string }>("/billing/checkout", { method: "POST", body: JSON.stringify(body) }, token),
  listCoupons: (token: string) => req<{ coupons: { id: string; code: string; discount_type: string; discount_value: number; currency: string | null; max_uses: number | null; uses_count: number; valid_from: string | null; valid_until: string | null; active: boolean; created_at: string }[] }>("/billing/coupons", {}, token),
  createCoupon: (token: string, body: Record<string, unknown>) => req<{ id: string; code: string }>("/billing/coupons", { method: "POST", body: JSON.stringify(body) }, token),
  deleteCoupon: (token: string, code: string) => req<OkResponse>(`/billing/coupons/${code}`, { method: "DELETE" }, token),
  adminUsers: (token: string) => req<User[]>("/auth/admin/users", {}, token),
  adminWorkspaces: (token: string) => req<Workspace[]>("/auth/admin/workspaces", {}, token),
  adminSetSuperadmin: (token: string, user_id: string, is_superadmin: boolean) =>
    req<User>(`/auth/admin/users/${user_id}/superadmin`, { method: "POST", body: JSON.stringify({ is_superadmin }) }, token),
  listOpportunities: (token: string) =>
    req<{ opportunities: Opportunity[] }>("/ingestion/opportunities", {}, token).catch(
      // list endpoint may 404 until implemented; treat as empty
      () => ({ opportunities: [] as Opportunity[] })
    ),
  createOpportunity: (token: string, title: string) =>
    req<Opportunity>(
      "/ingestion/opportunities",
      { method: "POST", body: JSON.stringify({ title }) },
      token
    ),
  getOpportunity: (token: string, id: string) =>
    req<Opportunity>(`/ingestion/opportunities/${id}`, {}, token),
  registerDocument: (token: string, id: string, filename: string, sample_text: string) =>
    req<{ id: string; kind: string }>(
      `/ingestion/opportunities/${id}/documents`,
      { method: "POST", body: JSON.stringify({ filename, sample_text }) },
      token
    ),
  uploadDocument: (token: string, id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return req<{ id: string; filename: string; kind: string; chars: number; ocr_status: string }>(
      `/ingestion/opportunities/${id}/upload`,
      { method: "POST", body: form, headers: {} },
      token
    );
  },
  missingDocs: (token: string, id: string) =>
    req<MissingDocs>(`/ingestion/opportunities/${id}/missing-docs`, {}, token),
  deadlines: (token: string, id: string) =>
    req<{ deadlines: Deadline[] }>(`/ingestion/opportunities/${id}/deadlines`, {}, token),
  confirmDeadline: (token: string, id: string, deadlineId: string) =>
    req<{ id: string; confirmed: boolean }>(
      `/ingestion/opportunities/${id}/deadlines/${deadlineId}/confirm`,
      { method: "POST" },
      token
    ),
  clauses: (token: string, id: string) =>
    req<{ clauses: Clause[] }>(`/ingestion/opportunities/${id}/clauses`, {}, token),
  runRisk: (token: string, id: string) =>
    req<{ count: number; findings: Finding[] }>(
      `/risk/opportunities/${id}/run`,
      { method: "POST" },
      token
    ),
  listFindings: (token: string, id: string) =>
    req<{ findings: Finding[] }>(`/findings/opportunities/${id}`, {}, token),
  runBoq: (token: string, id: string, csv: string) =>
    req<{ count: number; findings: Finding[] }>(
      `/boq/opportunities/${id}/run`,
      { method: "POST", body: JSON.stringify({ csv }) },
      token
    ),
  askAssistant: (token: string, opportunityId: string, message: string) =>
    req<{ answer: string; source: string }>(
      `/assistant/chat`,
      { method: "POST", body: JSON.stringify({ opportunity_id: opportunityId, message }) },
      token
    ),
  reviewFinding: (token: string, opportunityId: string, findingId: string, decision: string, note?: string) =>
    req<{ id: string; review_status: string }>(
      `/review/findings/${findingId}`,
      { method: "POST", body: JSON.stringify({ opportunity_id: opportunityId, decision, note }) },
      token
    ),
  gate: (token: string, id: string) =>
    req<Gate>(`/review/opportunities/${id}/gate`, {}, token),
  auditTrail: (token: string, id: string) =>
    req<{ audit: { id: string; action: string; actor_email: string | null; created_at: string; meta: Record<string, unknown> }[] }>(`/review/opportunities/${id}/audit`, {}, token),
  listComparison: (token: string) =>
    req<{ opportunities: { id: string; title: string; submission_due: string | null; days_to_submission: number | null; risk_counts: Record<string, number>; qualification_gaps: number; boq_defects: number; export_ready: boolean }[] }>("/comparison/opportunities", {}, token),
  generateArtifact: (token: string, id: string, kind: string) =>
    req<Artifact>(
      `/drafting/opportunities/${id}/artifacts`,
      { method: "POST", body: JSON.stringify({ kind }) },
      token
    ),
  listArtifacts: (token: string, id: string) =>
    req<{ artifacts: Artifact[] }>(`/drafting/opportunities/${id}/artifacts`, {}, token),
  // Baseline lock (Phase 2)
  freezeBaseline: (token: string, id: string, source: "tender" | "award", note?: string) =>
    req<Baseline>(
      `/baseline/opportunities/${id}/freeze`,
      { method: "POST", body: JSON.stringify({ source, note }) },
      token
    ),
  listBaselines: (token: string, id: string) =>
    req<{ baselines: Baseline[] }>(`/baseline/opportunities/${id}/baselines`, {}, token),
  noticeRegister: (token: string, id: string) =>
    req<{
      source: string;
      version: number | null;
      region: string | null;
      rules: NoticeRule[];
      gaps: NoticeGap[];
    }>(`/baseline/opportunities/${id}/notice-register`, {}, token),
  handover: (token: string, id: string) =>
    req<HandoverPack>(`/baseline/opportunities/${id}/handover`, {}, token),
  compareBaselines: (token: string, id: string) =>
    req<BaselineCompare>(`/baseline/opportunities/${id}/compare`, {}, token),
  // Org custom notice standards (Phase 2)
  getOrgStandard: (token: string) =>
    req<OrgStandard>(`/standards/notice`, {}, token),
  setOrgStandard: (token: string, body: OrgStandard) =>
    req<OrgStandard>(`/standards/notice`, { method: "PUT", body: JSON.stringify(body) }, token),
  clearOrgStandard: (token: string) =>
    req<{ cleared: boolean }>(`/standards/notice`, { method: "DELETE" }, token),
  // Account settings
  deleteAccount: (token: string, body: { password: string; confirm: boolean }) =>
    req<OkResponse>("/auth/account", { method: "DELETE", body: JSON.stringify(body) }, token),
  exportAccount: (token: string) =>
    req<Record<string, unknown>>("/auth/export", {}, token),
  requestEmailChange: (token: string, new_email: string) =>
    req<{ ok: boolean; token: string }>("/auth/settings/email", { method: "POST", body: JSON.stringify({ new_email }) }, token),
  verifyEmailChange: (token: string, code: string) =>
    req<{ ok: boolean }>("/auth/settings/email/verify", { method: "POST", body: JSON.stringify({ token: code }) }, token),
  // Notification preferences
  getNotificationPreferences: (token: string) =>
    req<NotificationPreferences>("/notifications/preferences", {}, token),
  updateNotificationPreferences: (token: string, body: Partial<NotificationPreferences>) =>
    req<NotificationPreferences>("/notifications/preferences", { method: "PUT", body: JSON.stringify(body) }, token),
  // Admin
  adminDashboard: (token: string) =>
    req<AdminDashboard>("/auth/admin/dashboard", {}, token),
  adminSearchUsers: (token: string, q?: string) =>
    req<{ total: number; items: User[] }>(`/auth/admin/users/search${q ? `?q=${encodeURIComponent(q)}` : ""}`, {}, token),
  adminGetUser: (token: string, user_id: string) =>
    req<UserDetail>(`/auth/admin/users/${user_id}`, {}, token),
  adminSuspendUser: (token: string, user_id: string) =>
    req<UserDetail>(`/auth/admin/users/${user_id}/suspend`, { method: "POST" }, token),
  adminUnsuspendUser: (token: string, user_id: string) =>
    req<UserDetail>(`/auth/admin/users/${user_id}/unsuspend`, { method: "POST" }, token),
  adminDeleteUser: (token: string, user_id: string) =>
    req<OkResponse>(`/auth/admin/users/${user_id}`, { method: "DELETE" }, token),
  adminGetWorkspace: (token: string, workspace_id: string) =>
    req<WorkspaceDetail>(`/auth/admin/workspaces/${workspace_id}`, {}, token),
  adminSetWorkspacePlan: (token: string, workspace_id: string, plan: string) =>
    req<WorkspaceDetail>(`/auth/admin/workspaces/${workspace_id}/plan`, { method: "POST", body: JSON.stringify({ plan }) }, token),
  adminAuditLog: (token: string, workspace_id: string) =>
    req<AuditLogEntry[]>(`/auth/admin/audit-log?workspace_id=${encodeURIComponent(workspace_id)}`, {}, token),
  // Billing self-service
  getBillingSettings: (token: string) =>
    req<Record<string, unknown>>("/billing/settings", {}, token),
  updateBillingSettings: (token: string, body: Record<string, unknown>) =>
    req<Record<string, unknown>>("/billing/settings", { method: "PUT", body: JSON.stringify(body) }, token),
  cancelSubscription: (token: string) =>
    req<{ plan: string; previous_plan: string }>("/billing/cancel", { method: "POST" }, token),
  // Support
  listSupportTickets: (token: string) =>
    req<SupportTicket[]>("/support/tickets", {}, token),
  getSupportTicket: (token: string, ticket_id: string) =>
    req<SupportTicket>(`/support/tickets/${ticket_id}`, {}, token),
  createSupportTicket: (token: string, body: { title: string; body: string; category?: string }) =>
    req<SupportTicket>("/support/tickets", { method: "POST", body: JSON.stringify(body) }, token),
  replySupportTicket: (token: string, ticket_id: string, body: string) =>
    req<SupportTicketReply>(`/support/tickets/${ticket_id}/replies`, { method: "POST", body: JSON.stringify({ body }) }, token),
  // Support admin
  adminListSupportTickets: (token: string, workspace_id: string, category?: string, status?: string) =>
    req<SupportTicket[]>(`/support/admin/tickets?workspace_id=${encodeURIComponent(workspace_id)}${category ? `&category=${category}` : ""}${status ? `&status=${status}` : ""}`, {}, token),
  adminGetSupportTicket: (token: string, workspace_id: string, ticket_id: string) =>
    req<SupportTicket>(`/support/admin/tickets/${ticket_id}?workspace_id=${encodeURIComponent(workspace_id)}`, {}, token),
  adminSetSupportTicketStatus: (token: string, workspace_id: string, ticket_id: string, status: string) =>
    req<SupportTicket>(`/support/admin/tickets/${ticket_id}/status?workspace_id=${encodeURIComponent(workspace_id)}`, { method: "POST", body: JSON.stringify({ status }) }, token),
  // Analytics
  riskSummary: (token: string) =>
    req<Record<string, unknown>>("/analytics/risk-summary", {}, token),
  deadlineDashboard: (token: string) =>
    req<Record<string, unknown>>("/analytics/deadline-dashboard", {}, token),
  boqDefectSummary: (token: string) =>
    req<Record<string, unknown>>("/analytics/boq-defect-summary", {}, token),
  exportReport: async (token: string, format: string, filter: string) => {
    const params = new URLSearchParams({ format, filter });
    const res = await fetch(`${API_BASE}/analytics/reports/export?${params.toString()}`, {
      method: "POST",
      credentials: "include",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!res.ok) throw new Error("Export failed");
    return res.blob();
  },
};

export type NotificationPreferences = {
  email_deadlines: boolean;
  sms_deadlines: boolean;
  email_digest: boolean;
  sms_alerts: boolean;
  marketing: boolean;
  quiet_hours_start: number | null;
  quiet_hours_end: number | null;
};

export type AdminDashboard = {
  total_users: number;
  suspended_users: number;
  active_workspaces: number;
  pending_verifications: number;
  recent_signups: number;
};

export type UserDetail = {
  user_id: string;
  email: string;
  phone: string;
  org_name: string;
  city: string;
  email_verified: boolean;
  mobile_verified: boolean;
  is_superadmin: boolean;
  suspended_at: string | null;
  created_at: string | null;
  dob: string | null;
  workspaces: Array<{ workspace_id: string; name: string; role: string; plan: string | null }>;
};

export type WorkspaceDetail = {
  workspace_id: string;
  name: string;
  slug: string;
  owner_id: string;
  owner_email: string | null;
  plan: string | null;
  country: string | null;
  billing_provider: string | null;
  member_count: number;
  members: Array<{ user_id: string; role: string }>;
};

export type AuditLogEntry = {
  id: number;
  actor_user_id: string | null;
  action: string;
  object_type: string;
  object_id: string | null;
  detail: Record<string, unknown>;
  at: string | null;
};

export type SupportTicket = {
  id: string;
  workspace_id: string;
  user_id: string;
  title: string;
  body: string;
  category: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
  replies?: SupportTicketReply[];
};

export type SupportTicketReply = {
  id: string;
  ticket_id: string;
  user_id: string;
  body: string;
  created_at: string | null;
};

export type OrgStandardCategory = {
  key: string;
  label: string;
  typical_days: number | null;
  expected: boolean;
  keywords: string[];
  note?: string | null;
};

export type OrgStandard = {
  mode: "prevail" | "side_by_side";
  categories: OrgStandardCategory[];
};

export type Baseline = {
  id: string;
  version: number;
  source: string;
  content_sha256: string;
  note: string | null;
  sealed_at: string | null;
  counts: { findings?: number; deadlines?: number; notice_rules?: number };
};

export type NoticeRule = {
  days: number;
  unit_raw: string;
  trigger: string;
  category: string;
  source_page: number | null;
  source_quote: string | null;
};

export type NoticeGap = {
  key: string;
  label: string;
  typical_days: number | null;
  note: string | null;
  origin?: string;
};

export type HandoverPack = {
  version: number;
  source: string;
  sealed_hash: string;
  sealed_at: string | null;
  opportunity: Record<string, string | null>;
  key_obligations: Finding[];
  notice_register: NoticeRule[];
  notice_gaps: NoticeGap[];
  deadline_calendar: Array<{ kind: string; due_at: string | null; source_page: number | null }>;
  counts: Record<string, number>;
};

export type BaselineCompare = {
  tender_version: number;
  award_version: number;
  added: Finding[];
  removed: Finding[];
  changed: Array<{ category: string; title: string; changes: Record<string, unknown> }>;
};

export type Gate = {
  export_allowed: boolean;
  total: number;
  pending: number;
  by_status: Record<string, number>;
};

export type Artifact = {
  id: string;
  kind: string;
  version: number;
  status: string;
  body: {
    title: string;
    preamble?: string;
    items: Array<Record<string, unknown>>;
  };
};
