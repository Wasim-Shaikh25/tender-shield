// R-010 §B.3/A3: a request against an expired access token must recover
// transparently — refresh once (single-flight, shared with every other
// in-flight 401) and retry, rather than surfacing the 401 to the caller.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { API_BASE } from "./config";

async function freshModules() {
  vi.resetModules();
  const authClient = await import("./auth-client");
  const api = await import("./api");
  return { authClient, api };
}

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("req reactive refresh", () => {
  it("refreshes once and retries a single 401'd call transparently", async () => {
    const { authClient, api } = await freshModules();
    authClient.storeRefreshToken("rt_original");

    // First call to the opportunities endpoint 401s (stale token); every
    // later call to it succeeds — simulates the token having just expired.
    let opportunitiesCalls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === `${API_BASE}/auth/refresh`) {
          return jsonResponse({
            access_token: "at_new",
            refresh_token: "rt_rotated",
            role: "owner",
            workspace_id: "ws_1",
          });
        }
        if (url === `${API_BASE}/ingestion/opportunities`) {
          opportunitiesCalls += 1;
          if (opportunitiesCalls === 1) return jsonResponse({}, 401);
          return jsonResponse({ opportunities: [] });
        }
        throw new Error(`unexpected fetch: ${url}`);
      })
    );

    const result = await api.api.listOpportunities("at_stale");
    expect(result).toEqual({ opportunities: [] });
    expect(opportunitiesCalls).toBe(2); // one 401, one retry
  });

  it("collapses concurrent 401s from multiple calls into one refresh (R-010 A3)", async () => {
    const { authClient, api } = await freshModules();
    authClient.storeRefreshToken("rt_original");

    let refreshCalls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === `${API_BASE}/auth/refresh`) {
          refreshCalls += 1;
          return jsonResponse({
            access_token: "at_new",
            refresh_token: "rt_rotated",
            role: "owner",
            workspace_id: "ws_1",
          });
        }
        if (url === `${API_BASE}/billing/status`) {
          return jsonResponse({}, 401);
        }
        throw new Error(`unexpected fetch: ${url}`);
      })
    );

    await Promise.allSettled([
      api.billing.status("at_stale"),
      api.billing.status("at_stale"),
      api.billing.status("at_stale"),
    ]);

    expect(refreshCalls).toBe(1);
  });
});
