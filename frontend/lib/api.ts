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
export type ReportTemplate = { id: string; name: string; is_default: boolean; report_title?: string | null; primary_color?: string | null; accent_color?: string | null; logo_url?: string | null; watermark_text?: string | null; footer_text?: string | null };
export type DynamicConnectorConfig = { id?: string; name: string; base_url: string; auth_type: "none" | "bearer" | "basic" | "api_key"; auth_config?: Record<string, string>; headers?: Record<string, string>; pagination?: Record<string, unknown>; mappings?: Record<string, { items?: string; fields?: Record<string, string> }>; enabled?: boolean; last_tested_at?: string | null; last_test_status?: string | null };
export type IntegrationSource = { id: string; adapter_kind: string; name: string; opportunity_id?: string | null; status: string; config?: Record<string, unknown>; rate_limit_calls_per_minute?: number | null; last_synced_at?: string | null; created_at?: string };
export type Subcontract = { id: string; opportunity_id: string; subcontractor_name: string; reference?: string | null; contract_value_minor?: number | null; currency?: string; scope?: string | null; notice_buffer_days?: number; postal_buffer_days?: number; status: string; created_at?: string };
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

export type PricingLoading = {
  finding_id: string;
  pattern_id: string;
  produced: boolean;
  amount_minor?: number | null;
  currency: string;
  basis: string;
  formula: string;
  rulepack_version: string;
  inputs_used: Record<string, unknown>;
  missing_inputs?: string[];
  reason?: string | null;
};

export type RateMatch = {
  src_row: number;
  boq_description: string;
  boq_unit: string;
  boq_rate_minor: number;
  matched_by: string;
  schedule_code?: string | null;
  schedule_description?: string | null;
  schedule_rate_minor?: number | null;
  variance_minor?: number | null;
  variance_pct?: number | null;
};

export type RateBenchmark = {
  schedule_id?: string | null;
  schedule_confidence?: string | null;
  headline_variance_pct?: number | null;
  code_matched: RateMatch[];
  description_matched: RateMatch[];
  unmatched: RateMatch[];
};

export type CashflowMonth = {
  month: number;
  billed_minor: number;
  incurred_minor: number;
  received_minor: number;
  cumulative_net_minor: number;
};

export type CashflowResult = {
  monthly: CashflowMonth[];
  peak_requirement_minor: number;
  peak_month: number;
  total_financing_cost_minor: number;
  currency: string;
  assumptions: string[];
};

export type RateBuildupItem = {
  src_row: number;
  description: string;
  unit: string;
  qty: number;
  rate_minor: number;
  amount_minor: number;
  material_rate_minor: number;
  labour_rate_minor: number;
  equipment_rate_minor: number;
  overhead_rate_minor: number;
  profit_rate_minor: number;
  build_total_minor: number;
};

export type RateBuildupResult = {
  currency: string;
  total_amount_minor: number;
  total_profit_minor: number;
  items: RateBuildupItem[];
  assumptions: string[];
};

export type SensitivityScenario = {
  name: string;
  param: string;
  delta_pct: number;
  total_amount_minor: number;
  delta_minor: number;
  delta_pct_total: number;
};

export type SensitivityResult = {
  base_total_minor: number;
  currency: string;
  scenarios: SensitivityScenario[];
};

export type Drawing = {
  id: string;
  opportunity_id: string;
  document_id?: string | null;
  filename: string;
  drawing_number?: string | null;
  title?: string | null;
  revision?: string | null;
  revision_date?: string | null;
  discipline?: string | null;
  supersedes_id?: string | null;
  page_count?: number | null;
  title_block: Record<string, unknown>;
  status: string;
  created_at: string;
};

export type DrawingComparison = {
  id: string;
  current_drawing_id: string;
  previous_drawing_id: string;
  summary: string;
  changed_pages: number[];
  changed_regions: { page: number; region: string; lines_added: number; lines_removed: number }[];
  created_at: string;
};

export type DrawingBoqLink = {
  id: string;
  drawing_id: string;
  page?: number | null;
  region?: string | null;
  source_quote?: string | null;
  item_code?: string | null;
  description: string;
  unit: string;
  qty?: number | null;
  rate_minor?: number | null;
  currency: string;
  created_at: string;
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

export type RulePackSummary = {
  id: string;
  pack_id: string;
  version: string;
  scope: "global" | "workspace";
  workspace_id: string | null;
  jurisdiction: string;
  is_active: boolean;
  status: "draft" | "active" | "deprecated";
  created_at: string;
  activated_at: string | null;
};

export type RulePackFile = {
  id: string;
  path: string;
  size: number;
  mime_type: string;
};

export type RagSuggestion = {
  id: string;
  rulepack_id: string;
  source_file_id: string | null;
  kind: string;
  proposed_yaml: Record<string, unknown>;
  rationale: string;
  source_quote: string;
  source_page: number | null;
  confidence: string;
  status: string;
  created_at: string;
};

export type AssistantSession = {
  id: string;
  opportunity_id: string | null;
  title: string | null;
  created_at: string;
  updated_at: string;
};

export type AssistantMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  type: string;
  dashboard?: PlanDashboard | null;
  grounded: boolean;
  source?: string;
  citations?: string[];
  suggested_followups?: string[];
  created_at: string;
};

export type ProjectState = {
  opportunity_id: string;
  workspace_id: string;
  title: string;
  employer: string | null;
  jurisdiction: string;
  contract_value_minor: number | null;
  currency: string;
  submission_due: string | null;
  days_to_deadline: number | null;
  state: string;
  state_label: string;
  health: string;
  next_action: { label: string; link: string };
  blockers: { kind: string; message: string; count?: number }[];
  completed_gates: string[];
  document_count: number;
  finding_count: number;
  unreviewed_finding_count: number;
  baseline_count: number;
};

export type WorkspaceStateSummary = {
  workspace_id: string;
  workspace_name: string | null;
  opportunity_count: number;
  state_counts: Record<string, number>;
  upcoming_deadlines: { opportunity_id: string; title: string; submission_due: string | null; days_to_deadline: number | null; state: string }[];
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

export type ApprovalMatrixEntry = { action: string; threshold_minor: number; currency: string; required_roles?: string[] };
export type WorkspaceProject = { id: string; name: string; status: string; created_at?: string | null };
export type ProjectMember = { user_id: string; email: string; role: string };
export type BoqFinding = { category: string; severity: string; kind: string; title: string; detail: string };
export type RulePackPattern = { id: string; category: string; title: string; confidence: string; source: string };
export type CorrectionProposal = { id: string; kind: string; description: string; status: string; created_at?: string | null };

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
  listDocumentClassAcls: (token: string) =>
    req<{ rules: { id: string; document_class: string; min_role: string }[] }>("/auth/document-classes", {}, token),
  setDocumentClassAcl: (token: string, body: { document_class: string; min_role: string }) =>
    req<{ id: string; document_class: string; min_role: string }>("/auth/document-classes", { method: "POST", body: JSON.stringify(body) }, token),
  deleteDocumentClassAcl: (token: string, documentClass: string) =>
    req<{ deleted: boolean }>(`/auth/document-classes/${encodeURIComponent(documentClass)}`, { method: "DELETE" }, token),
  listReportTemplates: (token: string) =>
    req<{ templates: ReportTemplate[] }>("/export/templates", {}, token),
  createReportTemplate: (token: string, body: Partial<ReportTemplate>) =>
    req<ReportTemplate>("/export/templates", { method: "POST", body: JSON.stringify(body) }, token),
  updateReportTemplate: (token: string, id: string, body: Partial<ReportTemplate>) =>
    req<ReportTemplate>(`/export/templates/${id}`, { method: "PUT", body: JSON.stringify(body) }, token),
  deleteReportTemplate: (token: string, id: string) =>
    req<{ deleted: boolean }>(`/export/templates/${id}`, { method: "DELETE" }, token),
  setDefaultReportTemplate: (token: string, id: string) =>
    req<ReportTemplate>(`/export/templates/${id}/default`, { method: "POST" }, token),
  getDataGovernance: (token: string, workspaceId: string) =>
    req<{ data_region: string; retention_days: number | null; archive_after_days: number | null; legal_hold: boolean; encryption_at_rest: string }>(`/governance/workspaces/${workspaceId}/data-governance`, {}, token),
  updateDataGovernance: (token: string, workspaceId: string, body: Partial<{ data_region: string; retention_days: number; archive_after_days: number; legal_hold: boolean; encryption_at_rest: string }>) =>
    req<Record<string, unknown>>(`/governance/workspaces/${workspaceId}/data-governance`, { method: "PUT", body: JSON.stringify(body) }, token),
  listRetentionCandidates: (token: string, workspaceId: string) =>
    req<{ candidates: { id: string; filename: string; kind: string; opportunity_id: string; created_at: string }[] }>(`/governance/workspaces/${workspaceId}/data-governance/retention-candidates`, {}, token),
  listDynamicConnectors: (token: string) =>
    req<{ connectors: DynamicConnectorConfig[] }>("/integrations/dynamic-connectors", {}, token),
  getDynamicConnector: (token: string, id: string) =>
    req<DynamicConnectorConfig>(`/integrations/dynamic-connectors/${id}`, {}, token),
  createDynamicConnector: (token: string, body: Partial<DynamicConnectorConfig>) =>
    req<DynamicConnectorConfig>("/integrations/dynamic-connectors", { method: "POST", body: JSON.stringify(body) }, token),
  updateDynamicConnector: (token: string, id: string, body: Partial<DynamicConnectorConfig>) =>
    req<DynamicConnectorConfig>(`/integrations/dynamic-connectors/${id}`, { method: "PUT", body: JSON.stringify(body) }, token),
  deleteDynamicConnector: (token: string, id: string) =>
    req<{ deleted: boolean }>(`/integrations/dynamic-connectors/${id}`, { method: "DELETE" }, token),
  testDynamicConnector: (token: string, id: string) =>
    req<{ status: string; http_status: number | null; latency_ms: number; preview: string }>(`/integrations/dynamic-connectors/${id}/test`, { method: "POST" }, token),
  pollDynamicConnector: (token: string, id: string) =>
    req<Record<string, unknown>>(`/integrations/dynamic-connectors/${id}/poll`, { method: "POST" }, token),
  listConnectors: (token: string) =>
    req<{ connectors: { kind: string; name: string; auth_required: boolean }[] }>("/integrations/connectors", {}, token),
  listAdapters: (token: string) =>
    req<{ adapters: { kind: string; supported_mimetypes: string[] }[] }>("/integrations/adapters", {}, token),
  listSources: (token: string) =>
    req<{ sources: IntegrationSource[] }>("/integrations/sources", {}, token),
  createSource: (token: string, body: { adapter_kind: string; name: string; opportunity_id?: string; config?: Record<string, unknown>; rate_limit_calls_per_minute?: number }) =>
    req<IntegrationSource>("/integrations/sources", { method: "POST", body: JSON.stringify(body) }, token),
  startOAuth: (token: string, sourceId: string, redirectUri: string) =>
    req<{ authorization_url: string; state: string }>(`/integrations/sources/${sourceId}/oauth`, { method: "POST", body: JSON.stringify({ redirect_uri: redirectUri }) }, token),
  pollSource: (token: string, sourceId: string) =>
    req<Record<string, unknown>>(`/integrations/sources/${sourceId}/poll`, { method: "POST" }, token),
  importSource: (token: string, sourceId: string, payload: Record<string, unknown>) =>
    req<Record<string, unknown>>(`/integrations/sources/${sourceId}/import`, { method: "POST", body: JSON.stringify({ payload }) }, token),
  listSubcontracts: (token: string, opportunityId: string) =>
    req<{ subcontracts: Subcontract[] }>(`/subcontract/opportunities/${opportunityId}/subcontracts`, {}, token),
  createSubcontract: (token: string, opportunityId: string, body: { subcontractor_name: string; reference?: string; contract_value_minor?: number; currency?: string; scope?: string; notice_buffer_days?: number; postal_buffer_days?: number }) =>
    req<{ id: string }>(`/subcontract/opportunities/${opportunityId}/subcontracts`, { method: "POST", body: JSON.stringify(body) }, token),
  getSubcontract: (token: string, id: string) =>
    req<Subcontract>(`/subcontract/subcontracts/${id}`, {}, token),
  addSubcontractClause: (token: string, id: string, body: { title: string; source_quote?: string; present?: boolean; status?: string }) =>
    req<{ id: string }>(`/subcontract/subcontracts/${id}/clauses`, { method: "POST", body: JSON.stringify(body) }, token),
  addSubcontractScopeItem: (token: string, id: string, body: { item_text: string; covered?: boolean; source_event_id?: string }) =>
    req<{ id: string }>(`/subcontract/subcontracts/${id}/scope-items`, { method: "POST", body: JSON.stringify(body) }, token),
  addSubcontractPaymentEvent: (token: string, id: string, body: { kind: string; due_date: string; amount_minor: number; certified_amount_minor?: number; currency?: string; status?: string }) =>
    req<{ id: string }>(`/subcontract/subcontracts/${id}/payment-events`, { method: "POST", body: JSON.stringify(body) }, token),
  flowdownCheck: (token: string, id: string) =>
    req<{ matched: { id: string; title: string }[]; missing: { id: string; title: string }[] }>(`/subcontract/subcontracts/${id}/flowdown-check`, {}, token),
  scopeGaps: (token: string, id: string) =>
    req<{ uncovered: { id: string; item_text: string; source_event_id?: string | null }[]; covered: { id: string; item_text: string }[] }>(`/subcontract/subcontracts/${id}/scope-gaps`, {}, token),
  noticeCalendar: (token: string, id: string) =>
    req<{ events: { kind: string; due_date: string; buffer_date: string; status: string }[] }>(`/subcontract/subcontracts/${id}/notice-calendar`, {}, token),
  paymentExposure: (token: string, id: string) =>
    req<{ currency: string; total_certified_minor: number; total_paid_minor: number; pending_minor: number; pay_when_paid_exposed_minor: number; age_days_max: number }>(`/subcontract/subcontracts/${id}/payment-exposure`, {}, token),
  listPublicApiKeys: (token: string) =>
    req<{ keys: { id: string; name: string; scopes: string[] }[] }>("/public_api/keys", {}, token),
  createPublicApiKey: (token: string, body: { name: string; scopes?: string[] }) =>
    req<{ id: string; name: string; plaintext_key: string; scopes: string[] }>("/public_api/keys", { method: "POST", body: JSON.stringify(body) }, token),
  revokePublicApiKey: (token: string, id: string) =>
    req<{ revoked: boolean }>(`/public_api/keys/${id}`, { method: "DELETE" }, token),
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
  // Assistant (TS-352)
  createAssistantSession: (token: string, title?: string, opportunityId?: string) =>
    req<AssistantSession>("/assistant/sessions", {
      method: "POST",
      body: JSON.stringify({ title, opportunity_id: opportunityId }),
    }, token),
  listAssistantSessions: (token: string, opportunityId?: string) =>
    req<{ sessions: AssistantSession[] }>(`/assistant/sessions${opportunityId ? `?opportunity_id=${encodeURIComponent(opportunityId)}` : ""}`, {}, token),
  getAssistantMessages: (token: string, sessionId: string) =>
    req<{ messages: AssistantMessage[] }>(`/assistant/sessions/${sessionId}/messages`, {}, token),
  sendAssistantMessage: (token: string, sessionId: string, message: string) =>
    req<AssistantMessage>(`/assistant/sessions/${sessionId}/chat`, { method: "POST", body: JSON.stringify({ message }) }, token),
  deleteAssistantSession: (token: string, sessionId: string) =>
    req<{ deleted: boolean }>(`/assistant/sessions/${sessionId}`, { method: "DELETE" }, token),
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
  getClauseDeviation: (token: string, opportunityId: string) =>
    req<{ clauses: { clause_ref: string | null; heading: string | null; deviation_score: number; policies_matched: number; violations: Record<string, unknown>[] }[]; overall_deviation_score: number; policies_checked: number }>(`/comparison/opportunities/${opportunityId}/deviation`, {}, token),
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
    req<Record<string, unknown>>("/auth/export", { method: "POST" }, token),
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
  ingestSignal: (token: string, opportunityId: string, body: { signal_kind: string; text: string; title?: string; external_ref?: string }) =>
    req<ChangeEvent>(`/change/opportunities/${opportunityId}/signals`, { method: "POST", body: JSON.stringify(body) }, token),
  pollSignals: (token: string, opportunityId: string, messages: { signal_kind?: string; subject?: string; body: string; external_ref?: string }[]) =>
    req<{ processed: number; results: { event: ChangeEvent; created: boolean; classification: Record<string, unknown> }[] }>(`/change/opportunities/${opportunityId}/signals/poll`, { method: "POST", body: JSON.stringify({ messages }) }, token),
  runDelayAnalysis: (token: string, opportunityId: string, body: { event_id: string; delay_days: number }) =>
    req<{ trigger_date: string; delay_days: number; window_end: string; impacted_count: number; impacted_activities: { source_native_id: string; name: string; start_date: string | null; finish_date: string | null; duration_days: number | null; delay_window_days: number }[]; note?: string }>(`/change/opportunities/${opportunityId}/delay-analysis`, { method: "POST", body: JSON.stringify(body) }, token),
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
    req<Claim>(`/claims/claims/${claimId}`, {}, token),
  submitClaim: (token: string, claimId: string) =>
    req<Claim>(`/claims/claims/${claimId}/submit`, { method: "POST" }, token),
  getClaimChronology: (token: string, claimId: string) =>
    req<{ entries: ClaimChronologyEntry[] }>(`/claims/claims/${claimId}/chronology`, {}, token),
  getClaimChecklist: (token: string, claimId: string) =>
    req<{ items: ClaimChecklistItem[] }>(`/claims/claims/${claimId}/checklist`, {}, token),
  overrideChecklistItem: (token: string, claimId: string, itemId: string, override_note: string) =>
    req<ClaimChecklistItem>(`/claims/claims/${claimId}/checklist/${itemId}/override`, { method: "POST", body: JSON.stringify({ override_note }) }, token),
  getClaimQuantum: (token: string, claimId: string) =>
    req<ClaimQuantum>(`/claims/claims/${claimId}/quantum`, {}, token),
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
    req<ClaimLineItem>(`/claims/claims/${claimId}/quantum/line-items`, { method: "POST", body: JSON.stringify(body) }, token),
  updateClaimLineItem: (token: string, claimId: string, lineId: string, body: Partial<{
    description: string;
    quantity: string;
    unit: string;
    rate_minor: number;
    daywork_days?: number;
    daywork_rate_minor?: number;
  }>) =>
    req<ClaimLineItem>(`/claims/claims/${claimId}/quantum/line-items/${lineId}`, { method: "PUT", body: JSON.stringify(body) }, token),
  deleteClaimLineItem: (token: string, claimId: string, lineId: string) =>
    req<{ ok: boolean }>(`/claims/claims/${claimId}/quantum/line-items/${lineId}`, { method: "DELETE" }, token),
  recordClaimResponse: (token: string, claimId: string, body: {
    response_kind: string;
    received_at: string;
    responder: string;
    due_at?: string;
    notes?: string;
    document_id?: string;
  }) =>
    req<ClaimResponse>(`/claims/claims/${claimId}/responses`, { method: "POST", body: JSON.stringify(body) }, token),
  recordClaimNegotiation: (token: string, claimId: string, body: {
    offered_amount_minor: number;
    counter_amount_minor?: number;
    status?: string;
  }) =>
    req<ClaimNegotiation>(`/claims/claims/${claimId}/negotiations`, { method: "POST", body: JSON.stringify(body) }, token),
  recordClaimSettlement: (token: string, claimId: string, body: {
    outcome: string;
    settled_amount_minor: number;
    notes?: string;
  }) =>
    req<ClaimSettlement>(`/claims/claims/${claimId}/settlement`, { method: "POST", body: JSON.stringify(body) }, token),
  listClaimDrafts: (token: string, claimId: string) =>
    req<{ drafts: ClaimDraft[] }>(`/claims/claims/${claimId}/drafts`, {}, token),
  generateClaimDraft: (token: string, claimId: string, kind: string) =>
    req<ClaimDraft>(`/claims/claims/${claimId}/drafts/${kind}`, { method: "POST" }, token),
  getClaimDraft: (token: string, draftId: string) =>
    req<ClaimDraft>(`/claims/drafts/${draftId}`, {}, token),
  approveClaimDraft: (token: string, draftId: string) =>
    req<ClaimDraft>(`/claims/drafts/${draftId}/approve`, { method: "POST" }, token),
  getClaimChainIntegrity: (token: string, claimId: string) =>
    req<{ status: string; missing_link?: string }>(`/claims/claims/${claimId}/chain-integrity`, {}, token),
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
  getRecurringOmissions: (token: string, opportunityId?: string) =>
    req<Record<string, unknown>>(`/controltower/recurring-omissions?${opportunityId ? new URLSearchParams({ opportunity_id: opportunityId }) : ""}`, {}, token),
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
  // Schedule / model schedule ingestion
  importScheduleFile: (token: string, opportunityId: string, file: File, format = "csv") => {
    const body = new FormData();
    body.append("file", file);
    return req<{ activities_imported: number }>(`/integrations/schedule/opportunities/${opportunityId}/upload?format=${encodeURIComponent(format)}`, { method: "POST", body }, token);
  },
  listScheduleActivities: (token: string, opportunityId: string) =>
    req<{ activities: Record<string, unknown>[] }>(`/integrations/schedule/opportunities/${opportunityId}/activities`, {}, token),
  snapshotSchedule: (token: string, opportunityId: string) =>
    req<{ snapshot_at: string; activities: number }>(`/integrations/schedule/opportunities/${opportunityId}/snapshot`, { method: "POST" }, token),
  // Pricing intelligence (Phase 1)
  getLoadings: (token: string, opportunityId: string, params?: { contract_value_minor?: number; currency?: string; facts?: string }) =>
    req<{ loadings: PricingLoading[] }>(`/pricing/opportunities/${opportunityId}/loading?${new URLSearchParams({ ...(params?.contract_value_minor ? { contract_value_minor: String(params.contract_value_minor) } : {}), currency: params?.currency ?? "INR", ...(params?.facts ? { facts: params.facts } : {}) })}`, {}, token),
  runRateBenchmark: (token: string, opportunityId: string, body: { csv: string; authority?: string; year?: string }) =>
    req<RateBenchmark>(`/pricing/opportunities/${opportunityId}/rate-benchmark`, { method: "POST", body: JSON.stringify(body) }, token),
  runCashflow: (token: string, opportunityId: string, body: {
    contract_value_minor: number;
    duration_months: number;
    cost_of_capital_pa: number;
    currency?: string;
    payment_days?: number;
    retention_pct?: number;
    retention_release_month?: number;
    mobilization_advance_pct?: number;
    mobilization_recovery_months?: number;
    milestone_billing_minor?: Record<string, number>;
  }) =>
    req<CashflowResult>(`/pricing/opportunities/${opportunityId}/cashflow`, { method: "POST", body: JSON.stringify(body) }, token),
  runRateBuildup: (token: string, opportunityId: string, body: {
    csv: string;
    currency?: string;
    material_pct?: number;
    labour_pct?: number;
    equipment_pct?: number;
    overhead_pct?: number;
    profit_pct?: number;
  }) =>
    req<RateBuildupResult>(`/pricing/opportunities/${opportunityId}/rate-buildup`, { method: "POST", body: JSON.stringify(body) }, token),
  runSensitivity: (token: string, opportunityId: string, body: {
    csv: string;
    currency?: string;
    scenarios?: { name: string; param: string; delta_pct: number }[];
  }) =>
    req<SensitivityResult>(`/pricing/opportunities/${opportunityId}/sensitivity`, { method: "POST", body: JSON.stringify(body) }, token),
  // Addendum / duplicate detection
  getAddendum: (token: string, opportunityId: string, documentId: string) =>
    req<{ document_id: string; supersedes: string | null; is_addendum: boolean; addendum_reason?: string; addendum_changes: Record<string, unknown>[]; duplicate_of?: string; ocr_status: string }>(`/ingestion/opportunities/${opportunityId}/documents/${documentId}/addendum`, {}, token),
  getDocument: (token: string, documentId: string) =>
    req<{ id: string; opportunity_id: string; filename: string; kind: string; ocr_status: string; language?: string | null; translation_summary?: string | null; sha256: string; supersedes: string | null; meta: Record<string, unknown>; created_at?: string | null }>(`/ingestion/documents/${documentId}`, {}, token),
  getGlossary: (token: string, opportunityId: string) =>
    req<{ terms: { id: string; document_id: string; term: string; definition: string; source_quote?: string | null; source_clause_ref?: string | null }[] }>(`/ingestion/opportunities/${opportunityId}/glossary`, {}, token),
  getDocumentGlossary: (token: string, opportunityId: string, documentId: string) =>
    req<{ terms: { id: string; document_id: string; term: string; definition: string; source_quote?: string | null; source_clause_ref?: string | null }[] }>(`/ingestion/opportunities/${opportunityId}/documents/${documentId}/glossary`, {}, token),
  // Outcomes
  getOutcome: (token: string, opportunityId: string, tenderRef?: string) =>
    req<Record<string, unknown>>(`/outcomes/opportunities/${opportunityId}${tenderRef ? `?tender_ref=${encodeURIComponent(tenderRef)}` : ""}`, {}, token),
  getScopePatterns: (token: string, opportunityId: string) =>
    req<{ patterns: Record<string, unknown>[] }>(`/outcomes/opportunities/${opportunityId}/scope-patterns`, {}, token),
  // Drawings (TS-321, TS-322)
  listDrawings: (token: string, opportunityId: string) =>
    req<{ drawings: Drawing[] }>(`/drawings/opportunities/${opportunityId}/drawings`, {}, token),
  createDrawing: (token: string, opportunityId: string, body: {
    filename: string;
    document_id?: string;
    drawing_number?: string;
    title?: string;
    revision?: string;
    revision_date?: string;
    discipline?: string;
    supersedes_id?: string;
  }) =>
    req<Drawing>(`/drawings/opportunities/${opportunityId}/drawings`, { method: "POST", body: JSON.stringify(body) }, token),
  uploadDrawingFile: (token: string, opportunityId: string, drawingId: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return req<Drawing>(`/drawings/opportunities/${opportunityId}/drawings/${drawingId}/upload`, { method: "POST", body }, token);
  },
  supersedeDrawing: (token: string, opportunityId: string, currentId: string, previousId: string) =>
    req<Drawing>(`/drawings/opportunities/${opportunityId}/drawings/${currentId}/supersedes/${previousId}`, { method: "POST" }, token),
  compareDrawings: (token: string, opportunityId: string, currentId: string, previousId: string) =>
    req<DrawingComparison>(`/drawings/opportunities/${opportunityId}/drawings/${currentId}/compare/${previousId}`, { method: "POST" }, token),
  runSymbolAssist: (token: string, opportunityId: string, drawingId: string) =>
    req<{ pages: { page: number; symbols: { symbol: string; count: number; confidence: string; verify_manually: boolean }[] }[]; totals: Record<string, number>; note?: string }>(`/drawings/opportunities/${opportunityId}/drawings/${drawingId}/symbol-assist`, { method: "POST" }, token),
  linkDrawingBoq: (token: string, opportunityId: string, drawingId: string, body: {
    page?: number;
    region?: string;
    source_quote?: string;
    item_code?: string;
    description: string;
    unit: string;
    qty?: number;
    rate_minor?: number;
    currency?: string;
  }) =>
    req<DrawingBoqLink>(`/drawings/opportunities/${opportunityId}/drawings/${drawingId}/link-boq`, { method: "POST", body: JSON.stringify(body) }, token),
  listDrawingBoqLinks: (token: string, opportunityId: string, drawingId: string) =>
    req<{ links: DrawingBoqLink[] }>(`/drawings/opportunities/${opportunityId}/drawings/${drawingId}/boq-links`, {}, token),
  getDrawingHeatmap: (token: string, opportunityId: string, drawingId: string) =>
    req<{ pages: { page: number; confidence: number; cannot_determine: boolean; regions: Record<string, { start_line: number; end_line: number; confidence: number }> }[]; overall_confidence: number; note?: string }>(`/drawings/opportunities/${opportunityId}/drawings/${drawingId}/heatmap`, {}, token),
  importIfcQuantities: (token: string, opportunityId: string, drawingId: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return req<{ boq_candidates: { description: string; classification: string; unit: string; quantity: number; count: number; confidence: string; verify_manually: boolean }[]; activity_candidates: { source_native_id: string; name: string; classification: string }[]; element_count: number; note?: string }>(`/drawings/opportunities/${opportunityId}/drawings/${drawingId}/ifc-quantities`, { method: "POST", body }, token);
  },
  // Rulepack admin (TS-348)
  listRulepacks: (token: string) =>
    req<{ packs: RulePackSummary[] }>("/rulepacks/admin/packs", {}, token),
  uploadRulepack: (token: string, file: File, scope: "global" | "workspace" = "workspace") => {
    const body = new FormData();
    body.append("archive", file);
    body.append("scope", scope);
    return req<RulePackSummary>("/rulepacks/admin/packs", { method: "POST", body, headers: {} }, token);
  },
  activateRulepack: (token: string, id: string) =>
    req<RulePackSummary>(`/rulepacks/admin/packs/${id}/activate`, { method: "POST" }, token),
  deleteRulepack: (token: string, id: string) =>
    req<{ ok: boolean }>(`/rulepacks/admin/packs/${id}`, { method: "DELETE" }, token),
  getOpportunityRulepacks: (token: string, opportunityId: string) =>
    req<{ packs: RulePackSummary[] }>(`/rulepacks/opportunities/${opportunityId}/packs`, {}, token),
  applyOpportunityRulepacks: (token: string, opportunityId: string, packIds: string[]) =>
    req<{ packs: RulePackSummary[] }>(`/rulepacks/opportunities/${opportunityId}/packs`, { method: "POST", body: JSON.stringify({ pack_ids: packIds }) }, token),
  listRulepackFiles: (token: string, id: string) =>
    req<{ files: RulePackFile[] }>(`/rulepacks/admin/packs/${id}/files`, {}, token),
  generateRagSuggestions: (token: string, rulepackId: string, fileId: string) =>
    req<{ suggestions: RagSuggestion[] }>(`/rulepacks/admin/packs/${rulepackId}/files/${fileId}/suggest`, { method: "POST" }, token),
  listRagSuggestions: (token: string, rulepackId: string, status?: string) =>
    req<{ suggestions: RagSuggestion[] }>(`/rulepacks/admin/packs/${rulepackId}/suggestions${status ? `?status=${encodeURIComponent(status)}` : ""}`, {}, token),
  approveRagSuggestion: (token: string, id: string) =>
    req<{ suggestion_id: string; new_rulepack: { id: string; pack_id: string; version: string; status: string; is_active: boolean } }>(`/rulepacks/admin/suggestions/${id}/approve`, { method: "POST" }, token),
  rejectRagSuggestion: (token: string, id: string) =>
    req<{ id: string; status: string }>(`/rulepacks/admin/suggestions/${id}/reject`, { method: "POST" }, token),
  // Project state dashboard (TS-353/TS-354)
  listProjectStates: (token: string, filters?: Record<string, string | number | undefined>) => {
    const params = new URLSearchParams();
    Object.entries(filters ?? {}).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
    });
    return req<{ opportunities: ProjectState[] }>(`/project_state/opportunities?${params.toString()}`, {}, token);
  },
  getProjectState: (token: string, opportunityId: string) =>
    req<ProjectState>(`/project_state/opportunities/${opportunityId}/state`, {}, token),
  listWorkspaceStateSummaries: (token: string) =>
    req<{ workspaces: WorkspaceStateSummary[] }>("/project_state/workspaces/me/opportunities/state", {}, token),
  // Phase 1 backend-only route wrappers (TS-382)
  logout: (token: string) =>
    req<OkResponse>("/auth/logout", { method: "POST" }, token),
  mfaEnroll: (token: string, body: { method: string; phone?: string }) =>
    req<{ mfa_token: string; uri: string; backup_codes: string[] }>("/auth/mfa/enroll", { method: "POST", body: JSON.stringify(body) }, token),
  mfaVerify: (token: string, code: string) =>
    req<OkResponse>("/auth/mfa/verify", { method: "POST", body: JSON.stringify({ code }) }, token),
  getApprovalMatrix: (token: string, workspaceId: string) =>
    req<{ actions: string[]; limits: ApprovalMatrixEntry[] }>(`/auth/workspaces/${workspaceId}/approval-matrix`, {}, token),
  updateApprovalMatrix: (token: string, workspaceId: string, body: { limits: ApprovalMatrixEntry[] }) =>
    req<{ limits: ApprovalMatrixEntry[] }>(`/auth/workspaces/${workspaceId}/approval-matrix`, { method: "PUT", body: JSON.stringify(body) }, token),
  listWorkspaceProjects: (token: string, workspaceId: string) =>
    req<{ items: WorkspaceProject[]; total: number }>(`/auth/workspaces/${workspaceId}/projects`, {}, token),
  createWorkspaceProject: (token: string, workspaceId: string, body: { name: string; status?: string }) =>
    req<WorkspaceProject>(`/auth/workspaces/${workspaceId}/projects`, { method: "POST", body: JSON.stringify(body) }, token),
  listProjectMembers: (token: string, projectId: string) =>
    req<{ items: ProjectMember[]; total: number }>(`/auth/projects/${projectId}/members`, {}, token),
  addProjectMember: (token: string, projectId: string, body: { email: string; role: string }) =>
    req<ProjectMember>(`/auth/projects/${projectId}/members`, { method: "POST", body: JSON.stringify(body) }, token),
  adminCreateUser: (token: string, body: { email: string; password: string }) =>
    req<Tokens>("/auth/admin/users", { method: "POST", body: JSON.stringify(body) }, token),
  getBillingProjectStatus: (token: string, opportunityId: string) =>
    req<{ opportunity_id: string; active: boolean; activation_fee_minor: number; currency: string }>(`/billing/projects/${opportunityId}/status`, {}, token),
  uploadBoq: (token: string, opportunityId: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return req<{ count: number; findings: BoqFinding[] }>(`/boq/opportunities/${opportunityId}/upload`, { method: "POST", body, headers: {} }, token);
  },
  getDocumentText: (token: string, documentId: string, page?: number) =>
    req<{ text: string }>(`/ingestion/documents/${documentId}/text${page !== undefined ? `?page=${page}` : ""}`, {}, token),
  listCorrectionProposals: (token: string, status?: string) =>
    req<{ proposals: CorrectionProposal[] }>(`/rulepacks/corrections/proposals${status ? `?status=${encodeURIComponent(status)}` : ""}`, {}, token),
  scanCorrections: (token: string) =>
    req<{ count: number }>("/rulepacks/corrections/scan", { method: "POST" }, token),
  dismissCorrectionProposal: (token: string, proposalId: string) =>
    req<{ id: string; status: string }>(`/rulepacks/corrections/proposals/${proposalId}/dismiss`, { method: "POST" }, token),
  listRulepackPatterns: (token: string, packId: string, validatedOnly?: boolean) =>
    req<{ pack: string; patterns: RulePackPattern[] }>(`/rulepacks/${packId}/patterns${validatedOnly ? "?validated_only=true" : ""}`, {}, token),
  getSubcontractStatus: (token: string) =>
    req<{ module: string; status: string }>("/subcontract/status", {}, token),
  streamDocument: (token: string, opportunityId: string, documentId: string, taskId: string, onEvent: (event: string, data: unknown) => void): (() => void) => {
    const url = `${API_BASE}/ingestion/opportunities/${opportunityId}/documents/${documentId}/stream?task_id=${encodeURIComponent(taskId)}`;
    const controller = new AbortController();
    fetch(url, { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal })
      .then(async (res) => {
        if (!res.ok || !res.body) return;
        const reader = res.body.getReader();
        let buffer = "";
        const decoder = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() ?? "";
          for (const part of parts) {
            const lines = part.split("\n");
            const eventLine = lines.find((l) => l.startsWith("event: "));
            const dataLine = lines.find((l) => l.startsWith("data: "));
            if (dataLine) {
              const event = eventLine ? eventLine.slice(7) : "";
              const data = JSON.parse(dataLine.slice(6));
              onEvent(event, data);
            }
          }
        }
      })
      .catch(() => {});
    return () => controller.abort();
  },
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

export type ScheduleActivity = {
  id: string;
  source_native_id: string;
  name: string;
  start_date?: string | null;
  finish_date?: string | null;
  duration_days?: number | null;
  predecessors?: Record<string, unknown> | null;
  linked_change_event_ids?: Record<string, unknown> | null;
  snapshot_at?: string | null;
};
