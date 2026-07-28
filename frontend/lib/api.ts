// Typed client for the TenderShield API. Base URL from env; every mutating call
// is workspace-scoped server-side (RLS) — the client just carries the bearer token.
export { API_BASE } from "./config";
import { API_BASE } from "./config";
import { refreshTokens } from "./auth-client";
import type { Tokens } from "./auth-client";
import { SessionExpired, toApiError } from "./errors";
export { ApiError, SessionExpired, PaywallError } from "./errors";
export type { Tokens } from "./auth-client";
export type Opportunity = { id: string; title: string; status: string; submission_due?: string | null };
export type WorkspaceSummary = {
  workspace_id: string;
  name: string;
  role: string;
  plan: string;
  is_current: boolean;
};
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
};

function withAuth(opts: RequestInit, token?: string): RequestInit {
  return {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers ?? {}),
    },
  };
}

/** Reactive 401 retry (R-010 §B.3): a 401 means the access token the caller
 * was holding has expired — refresh (single-flight, so concurrent 401s from
 * other in-flight calls collapse into the same request) and retry exactly
 * once with the new token. A retry loop against a genuinely revoked session
 * would hammer the API and hide the real problem, so this never retries
 * twice. Every OTHER call site keeps passing a plain token string; this is
 * the one place that knows how to recover from it going stale. */
async function req<T>(path: string, opts: RequestInit = {}, token?: string): Promise<T> {
  let res = await fetch(`${API_BASE}${path}`, withAuth(opts, token));

  if (res.status === 401 && token) {
    try {
      const tokens = await refreshTokens();
      res = await fetch(`${API_BASE}${path}`, withAuth(opts, tokens.access_token));
    } catch {
      throw new SessionExpired();
    }
  }

  if (!res.ok) throw await toApiError(res);
  return res.json() as Promise<T>;
}

export const api = {
  signup: (email: string, password: string, workspace_name: string) =>
    req<{ user_id: string; workspace_id: string }>("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password, workspace_name }),
    }),
  login: (email: string, password: string) =>
    req<Tokens>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  forgotPassword: (email: string) =>
    req<{ ok: boolean; token?: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  listWorkspaces: (token: string) =>
    req<WorkspaceSummary[]>("/auth/workspaces", {}, token),
  createWorkspace: (token: string, name: string, country = "IN") =>
    req<{ workspace_id: string; name: string }>(
      "/auth/workspaces",
      { method: "POST", body: JSON.stringify({ name, country }) },
      token
    ),
  switchWorkspace: (token: string, workspaceId: string, refreshToken: string) =>
    req<Tokens>(
      `/auth/workspaces/${workspaceId}/switch`,
      { method: "POST", body: JSON.stringify({ refresh_token: refreshToken }) },
      token
    ),
  resetPassword: (token: string, new_password: string) =>
    req<{ ok: boolean }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password }),
    }),
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
  reviewFinding: (token: string, findingId: string, decision: string, note?: string) =>
    req<{ id: string; review_status: string }>(
      `/review/findings/${findingId}`,
      { method: "POST", body: JSON.stringify({ decision, note }) },
      token
    ),
  gate: (token: string, id: string) =>
    req<Gate>(`/review/opportunities/${id}/gate`, {}, token),
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
};

// ---- Billing (R-008, TS-091) -------------------------------------------
//
// Thin client matching what the backend actually implements today (TS-089/
// TS-097): status, real checkout, intent polling, invoice list. Coupons
// (R-006/TS-090) and entitlement fields like seats/storage/reviews_included
// (R-009/TS-098) don't exist server-side yet — this client and the pages
// built on it add those calls when those tasks land, rather than stubbing
// endpoints that don't exist.

export type Plan = "free" | "paygo" | "pro" | "scale";

export type BillingStatus = {
  plan: Plan;
  plan_status: "active" | "past_due" | "cancelled" | "trialing";
  grace_until: string | null;
  free_review_used: boolean;
  reviews_this_month: number;
  reviews_included: number | null; // null = not metered by count (free/paygo)
  reviews_topup: number;
  seats_included: number | null;
  seats_used: number | null; // null when auth's seat-count capability is absent
  period_end: string | null;
};

export type CheckoutHandle = {
  intent_id: string;
  provider: string;
  order_id: string | null;
  amount_minor: number;
  currency: string;
  breakdown: { list: number; discount: number; tax: number; total: number };
  checkout: Record<string, unknown>;
};

export type IntentStatus = { status: string; amount_minor?: number };

export type Invoice = {
  id: number;
  invoice_number: string;
  amount_minor: number;
  currency: string;
  status: string;
  provider: string;
  paid_at: string | null;
  created_at: string;
};

export const billing = {
  status: (token: string) => req<BillingStatus>("/billing/status", {}, token),

  checkout: (
    token: string,
    body: { kind: "paygo" | "subscription" | "topup"; plan?: Plan; opportunity_id?: string }
  ) =>
    req<CheckoutHandle>(
      "/billing/checkout",
      { method: "POST", body: JSON.stringify(body) },
      token
    ),

  intent: (token: string, id: string) =>
    req<IntentStatus>(`/billing/intents/${id}`, {}, token),

  invoices: (token: string) => req<{ invoices: Invoice[] }>("/billing/invoices", {}, token),
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
