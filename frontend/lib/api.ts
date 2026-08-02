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

export type ChangeSource = {
  id?: string;
  source_kind: string;
  document_id?: string | null;
  source_page?: number | null;
  source_quote?: string | null;
  external_ref?: string | null;
  text_preview?: string | null;
  received_at?: string | null;
};

export type ChangeConfirmation = {
  id: string;
  outcome: string;
  confirmed_by: string;
  confirmed_at: string;
  note?: string | null;
  evidence_ids?: string[];
};

export type ChangeEvent = {
  id: string;
  opportunity_id: string;
  baseline_id?: string | null;
  status: "candidate" | "triaged" | "confirmed" | "rejected" | "closed";
  title: string;
  reason: string;
  affected_scope?: string | null;
  confidence_band: string;
  notice_type?: string | null;
  trigger_date?: string | null;
  notice_deadline?: string | null;
  notice_deadline_detail?: Record<string, unknown>;
  impact_links?: Record<string, unknown>;
  created_by?: string | null;
  created_at?: string;
  updated_at?: string;
  sources?: ChangeSource[];
  latest_confirmation?: ChangeConfirmation | null;
  evidence_completeness?: Record<string, unknown> | null;
};

export type ChangeInbox = { events: ChangeEvent[] };

export type NoticeDeadline = {
  notice_type?: string;
  deadline_days?: number;
  deadline_basis?: string;
  trigger_date?: string;
  notice_deadline?: string;
  deadline_unknown?: boolean;
  required_content?: string[];
  correspondence?: Record<string, unknown>;
};

export type NoticeDraft = {
  artifact_id: string;
  kind: string;
  version: number;
  status: string;
};

export type Claim = {
  id: string;
  opportunity_id: string;
  change_event_id?: string | null;
  baseline_id?: string | null;
  claim_type: string;
  claimant_party?: string | null;
  status: "draft" | "submitted" | "under_review" | "negotiating" | "settled" | "rejected" | "withdrawn";
  title: string;
  description?: string | null;
  claim_amount_minor?: number | null;
  recovered_amount_minor?: number | null;
  currency: string;
  submitted_at?: string | null;
  created_at?: string;
  updated_at?: string;
  completeness_score?: number | null;
  chain_integrity?: string | null;
};

export type ClaimChronologyEntry = {
  id: string;
  entry_type: string;
  source_kind?: string | null;
  source_id?: string | null;
  title: string;
  occurred_at: string;
  source_page?: number | null;
  source_quote?: string | null;
  document_id?: string | null;
  custody_chain?: unknown[];
};

export type ClaimChecklistItem = {
  id: string;
  item_type: string;
  required: boolean;
  present: boolean;
  evidence_record_ids?: string[];
  override_note?: string | null;
  updated_at?: string;
};

export type ClaimLineItem = {
  id: string;
  description: string;
  quantity: string;
  unit: string;
  rate_minor: number;
  measured_total_minor: number;
  daywork_days?: number | null;
  daywork_rate_minor?: number | null;
  daywork_total_minor?: number;
  total_minor: number;
  currency: string;
};

export type ClaimQuantum = {
  currency: string;
  measured_total_minor: number;
  daywork_total_minor: number;
  total_minor: number;
  line_items: ClaimLineItem[];
};

export type ClaimResponse = {
  id: string;
  response_kind: string;
  received_at: string;
  due_at?: string | null;
  responder: string;
  notes?: string | null;
  document_id?: string | null;
  created_at?: string;
};

export type ClaimNegotiation = {
  id: string;
  round: number;
  offered_amount_minor: number;
  counter_amount_minor?: number | null;
  status: string;
  recorded_by: string;
  recorded_at?: string;
};

export type ClaimSettlement = {
  id: string;
  outcome: string;
  settled_amount_minor: number;
  currency: string;
  notes?: string | null;
  recorded_by: string;
  recorded_at?: string;
};

export type ClaimDraft = {
  id: string;
  draft_kind: string;
  status: string;
  version: number;
  body?: Record<string, unknown>;
  created_at?: string;
};

export type PlanSection = {
  type: "kpi" | "table" | "chart" | "mermaid" | "text";
  title: string;
  data: Record<string, unknown>;
};

export type PlanDashboard = {
  title: string;
  summary: string;
  sections: PlanSection[];
  citations?: string[];
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
  listPlans: (token: string) => req<{ plans: { id: string; name: string; price_minor: number; currency: string }[] }>("/billing/plans", {}, token),
  changePlan: (token: string, body: { plan: string; provider?: string; coupon_code?: string; amount_minor?: number }) =>
    req<{ action: string; plan: string; previous_plan?: string; provider?: string; order_id?: string; session_id?: string; mock: boolean; note?: string }>("/billing/change-plan", { method: "POST", body: JSON.stringify(body) }, token),
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
  askAssistant: (
    token: string,
    message: string,
    opportunityId?: string
  ) =>
    req<{
      type?: string;
      answer: string;
      source: string;
      dashboard?: PlanDashboard;
    }>(
      `/assistant/chat`,
      { method: "POST", body: JSON.stringify({ ...(opportunityId ? { opportunity_id: opportunityId } : {}), message }) },
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
  planDashboard: (token: string, opportunity_id: string, query: string) =>
    req<PlanDashboard>("/analytics/plan", { method: "POST", body: JSON.stringify({ opportunity_id, query }) }, token),
  planTemplates: () =>
    req<Array<{ id: string; name: string; query: string }>>("/analytics/plan/templates", {}),
  listPlanSnapshots: (token: string) =>
    req<{ snapshots: PlanSnapshot[] }>("/analytics/plan/snapshots", {}, token),
  getPlanSnapshot: (token: string, snapshot_id: string) =>
    req<PlanSnapshot & { dashboard: Record<string, unknown> }>(`/analytics/plan/snapshots/${snapshot_id}`, {}, token),
  savePlanSnapshot: (token: string, body: Omit<PlanSnapshot, "id" | "created_at">) =>
    req<PlanSnapshot>("/analytics/plan/snapshots", { method: "POST", body: JSON.stringify(body) }, token),
  deletePlanSnapshot: (token: string, snapshot_id: string) =>
    req<{ ok: boolean }>(`/analytics/plan/snapshots/${snapshot_id}`, { method: "DELETE" }, token),
  exportPlanSnapshot: async (token: string, snapshot_id: string, format: string) => {
    const res = await fetch(`${API_BASE}/analytics/plan/snapshots/${snapshot_id}/export?format=${format}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      credentials: "include",
    });
    if (!res.ok) throw new Error("Export failed");
    return res.blob();
  },
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
  // Change / variation control (Phase 18)
  listChangeInbox: (token: string, opportunityId: string) =>
    req<ChangeInbox>(`/change/opportunities/${opportunityId}/inbox`, {}, token),
  listChangeEvents: (token: string, opportunityId: string) =>
    req<{ events: ChangeEvent[] }>(`/change/opportunities/${opportunityId}/events`, {}, token),
  getChangeEvent: (token: string, eventId: string) =>
    req<ChangeEvent>(`/change/events/${eventId}`, {}, token),
  createChangeEvent: (token: string, opportunityId: string, body: {
    title: string;
    reason?: string;
    affected_scope?: string;
    confidence_band?: string;
    notice_type?: string;
    trigger_date?: string;
    sources: { source_kind?: string; source_quote: string; source_page?: number | null; document_id?: string | null; external_ref?: string | null }[];
  }) =>
    req<ChangeEvent>(`/change/opportunities/${opportunityId}/events`, { method: "POST", body: JSON.stringify(body) }, token),
  confirmChangeEvent: (token: string, eventId: string, outcome: string, note?: string, evidence_ids?: string[]) =>
    req<ChangeConfirmation>(`/change/events/${eventId}/confirmations`, {
      method: "POST",
      body: JSON.stringify({ outcome, note, evidence_ids }),
    }, token),
  triageChangeEvent: (token: string, eventId: string, decision: string) =>
    req<ChangeEvent>(`/change/events/${eventId}/triage`, { method: "PUT", body: JSON.stringify({ decision }) }, token),
  getNoticeDeadline: (token: string, eventId: string) =>
    req<NoticeDeadline>(`/change/events/${eventId}/notice-deadline`, {}, token),
  requestNoticeDraft: (token: string, eventId: string) =>
    req<NoticeDraft>(`/change/events/${eventId}/notice-draft`, { method: "POST" }, token),
  // Claims workspace (Phase 19)
  listClaims: (token: string, opportunityId: string) =>
    req<{ claims: Claim[] }>(`/claims/opportunities/${opportunityId}/claims`, {}, token),
  createClaim: (token: string, opportunityId: string, body: {
    claim_type: string;
    title: string;
    description?: string;
    claimant_party?: string;
    change_event_id?: string;
    baseline_id?: string;
    claim_amount_minor?: number;
    currency?: string;
  }) =>
    req<Claim>(`/claims/opportunities/${opportunityId}/claims`, { method: "POST", body: JSON.stringify(body) }, token),
  getClaim: (token: string, claimId: string) =>
    req<Claim>(`/claims/${claimId}`, {}, token),
  submitClaim: (token: string, claimId: string) =>
    req<Claim>(`/claims/${claimId}/submit`, { method: "POST" }, token),
  getClaimChronology: (token: string, claimId: string) =>
    req<{ entries: ClaimChronologyEntry[] }>(`/claims/${claimId}/chronology`, {}, token),
  getClaimChecklist: (token: string, claimId: string) =>
    req<{ items: ClaimChecklistItem[] }>(`/claims/${claimId}/checklist`, {}, token),
  overrideChecklistItem: (token: string, claimId: string, itemId: string, override_note: string) =>
    req<ClaimChecklistItem>(`/claims/${claimId}/checklist/${itemId}/override`, { method: "POST", body: JSON.stringify({ override_note }) }, token),
  getClaimQuantum: (token: string, claimId: string) =>
    req<ClaimQuantum>(`/claims/${claimId}/quantum`, {}, token),
  addClaimLineItem: (token: string, claimId: string, body: {
    description: string;
    quantity: string;
    unit: string;
    rate_minor: number;
    daywork_days?: number;
    daywork_rate_minor?: number;
    cost_code_id?: string;
    currency?: string;
  }) =>
    req<ClaimLineItem>(`/claims/${claimId}/quantum/line-items`, { method: "POST", body: JSON.stringify(body) }, token),
  updateClaimLineItem: (token: string, claimId: string, lineId: string, body: Partial<{
    description: string;
    quantity: string;
    unit: string;
    rate_minor: number;
    daywork_days?: number;
    daywork_rate_minor?: number;
  }>) =>
    req<ClaimLineItem>(`/claims/${claimId}/quantum/line-items/${lineId}`, { method: "PUT", body: JSON.stringify(body) }, token),
  deleteClaimLineItem: (token: string, claimId: string, lineId: string) =>
    req<{ ok: boolean }>(`/claims/${claimId}/quantum/line-items/${lineId}`, { method: "DELETE" }, token),
  recordClaimResponse: (token: string, claimId: string, body: {
    response_kind: string;
    received_at: string;
    responder: string;
    due_at?: string;
    notes?: string;
    document_id?: string;
  }) =>
    req<ClaimResponse>(`/claims/${claimId}/responses`, { method: "POST", body: JSON.stringify(body) }, token),
  recordClaimNegotiation: (token: string, claimId: string, body: {
    offered_amount_minor: number;
    counter_amount_minor?: number;
    status?: string;
  }) =>
    req<ClaimNegotiation>(`/claims/${claimId}/negotiations`, { method: "POST", body: JSON.stringify(body) }, token),
  recordClaimSettlement: (token: string, claimId: string, body: {
    outcome: string;
    settled_amount_minor: number;
    notes?: string;
  }) =>
    req<ClaimSettlement>(`/claims/${claimId}/settlement`, { method: "POST", body: JSON.stringify(body) }, token),
  listClaimDrafts: (token: string, claimId: string) =>
    req<{ drafts: ClaimDraft[] }>(`/claims/${claimId}/drafts`, {}, token),
  generateClaimDraft: (token: string, claimId: string, kind: string) =>
    req<ClaimDraft>(`/claims/${claimId}/drafts/${kind}`, { method: "POST" }, token),
  getClaimDraft: (token: string, draftId: string) =>
    req<ClaimDraft>(`/drafts/${draftId}`, {}, token),
  approveClaimDraft: (token: string, draftId: string) =>
    req<ClaimDraft>(`/drafts/${draftId}/approve`, { method: "POST" }, token),
  getClaimChainIntegrity: (token: string, claimId: string) =>
    req<{ status: string; missing_link?: string }>(`/claims/${claimId}/chain-integrity`, {}, token),
  getClaimMetrics: (token: string, opportunityId: string) =>
    req<Record<string, unknown>>(`/claims/opportunities/${opportunityId}/claim-metrics`, {}, token),
  // Control tower dashboards (Phase 20)
  getExposure: (token: string, opportunityId: string, params?: { cost_of_capital_pa?: number; currency?: string }) =>
    req<Record<string, unknown>>(`/controltower/exposure?${new URLSearchParams({ opportunity_id: opportunityId, ...(params ? { cost_of_capital_pa: String(params.cost_of_capital_pa ?? 0.12), currency: params.currency ?? "INR" } : {}) })}`, {}, token),
  getControlDashboard: (token: string, opportunityId: string, currency = "INR") =>
    req<Record<string, unknown>>(`/controltower/dashboard?opportunity_id=${encodeURIComponent(opportunityId)}&currency=${currency}`, {}, token),
  getPortfolio: (token: string, params?: { cost_of_capital_pa?: number; currency?: string }) =>
    req<Record<string, unknown>>(`/controltower/portfolio?${new URLSearchParams({ cost_of_capital_pa: String(params?.cost_of_capital_pa ?? 0.12), currency: params?.currency ?? "INR" })}`, {}, token),
  postForecast: (token: string, body: { opportunity_id: string; projected_final_cost_minor: number; contingency_percent?: number; cost_of_capital_pa?: number; currency?: string }) =>
    req<Record<string, unknown>>(`/controltower/forecast`, { method: "POST", body: JSON.stringify(body) }, token),
  getResponseTimes: (token: string, opportunityId: string) =>
    req<Record<string, unknown>>(`/controltower/response-times?opportunity_id=${encodeURIComponent(opportunityId)}`, {}, token),
  getClauseTrends: (token: string) =>
    req<Record<string, unknown>>(`/controltower/clause-trends`, {}, token),
  getExecutiveSummary: (token: string, opportunityId: string, params?: { cost_of_capital_pa?: number; currency?: string }) =>
    req<Record<string, unknown>>(`/controltower/executive-summary?${new URLSearchParams({ opportunity_id: opportunityId, cost_of_capital_pa: String(params?.cost_of_capital_pa ?? 0.12), currency: params?.currency ?? "INR" })}`, {}, token),
  getPaymentSchedule: (token: string, opportunityId: string) =>
    req<Record<string, unknown>>(`/controltower/payment-schedule?opportunity_id=${encodeURIComponent(opportunityId)}`, {}, token),
  recordPaymentEvent: (token: string, body: { opportunity_id: string; kind: string; due_date: string; amount_minor: number; certified_amount_minor?: number; currency?: string; status?: string; released_at?: string; description?: string }) =>
    req<Record<string, unknown>>(`/controltower/payment-schedule`, { method: "POST", body: JSON.stringify(body) }, token),
  getEconomics: (token: string, params?: { cost_of_sales_minor?: number; customer_acquisition_cost_minor?: number; currency?: string }) =>
    req<Record<string, unknown>>(`/controltower/economics?${new URLSearchParams({ currency: params?.currency ?? "INR" })}`, {}, token),
  getCustomerOutcomes: (token: string, params?: { hours_per_review_saved?: number; currency?: string }) =>
    req<Record<string, unknown>>(`/controltower/customer-outcomes?${new URLSearchParams({ hours_per_review_saved: String(params?.hours_per_review_saved ?? 2), currency: params?.currency ?? "INR" })}`, {}, token),
};

export type PlanSnapshot = {
  id?: string;
  opportunity_id: string;
  title: string;
  query: string;
  dashboard?: Record<string, unknown>;
  created_at?: string;
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
  plan: string;
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
