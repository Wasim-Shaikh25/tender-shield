// Typed API errors (R-010 §B.4) — replaces `throw new Error(body.detail)`,
// which rendered the 402 paywall payload (an object) as the literal string
// "[object Object]" since `body.detail` is never a string for that status.

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: unknown,
    message?: string
  ) {
    super(message ?? (typeof detail === "string" ? detail : `http_${status}`));
    this.name = "ApiError";
  }
}

export class SessionExpired extends ApiError {
  constructor() {
    super(401, "session_expired", "session_expired");
    this.name = "SessionExpired";
  }
}

export class PaywallError extends ApiError {
  constructor(
    readonly code: string,
    readonly upsell: Record<string, unknown>
  ) {
    super(402, { code, upsell }, code);
    this.name = "PaywallError";
  }
}

export async function toApiError(res: Response): Promise<ApiError> {
  const body = await res.json().catch(() => ({}));
  const detail = body.detail;
  if (res.status === 402 && detail && typeof detail === "object") {
    const d = detail as Record<string, unknown>;
    return new PaywallError(
      typeof d.code === "string" ? d.code : "payment_required",
      (d.upsell as Record<string, unknown>) ?? {}
    );
  }
  if (res.status === 401) return new SessionExpired();
  return new ApiError(res.status, detail, typeof detail === "string" ? detail : undefined);
}
