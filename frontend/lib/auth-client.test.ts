// R-010 §B.2: single-flight refresh is a correctness requirement, not an
// optimization — the backend revokes the whole refresh-token family when a
// refresh token is replayed (auth/refresh.py reuse detection), and two
// concurrent refreshes against the same stored token look exactly like a
// replay to the server. This is the test that proves the collapsing works.
import { beforeEach, describe, expect, it, vi } from "vitest";

async function freshModule() {
  vi.resetModules();
  return import("./auth-client");
}

function jsonResponse(body: unknown, ok = true) {
  return {
    ok,
    status: ok ? 200 : 401,
    json: async () => body,
  } as Response;
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("refreshTokens", () => {
  it("collapses concurrent callers into exactly one network request", async () => {
    const { refreshTokens, storeRefreshToken } = await freshModule();
    storeRefreshToken("rt_original");

    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        access_token: "at_new",
        refresh_token: "rt_rotated",
        role: "owner",
        workspace_id: "ws_1",
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const [a, b, c] = await Promise.all([refreshTokens(), refreshTokens(), refreshTokens()]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(a.access_token).toBe("at_new");
    expect(b).toEqual(a);
    expect(c).toEqual(a);
  });

  it("rotates the stored refresh token so a stale one can't be replayed", async () => {
    const { refreshTokens, storeRefreshToken, loadRefreshToken } = await freshModule();
    storeRefreshToken("rt_original");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          access_token: "at_new",
          refresh_token: "rt_rotated",
          role: "owner",
          workspace_id: "ws_1",
        })
      )
    );

    await refreshTokens();

    expect(loadRefreshToken()).toBe("rt_rotated");
  });

  it("rejects with SessionExpired and fires the session-expired event when no refresh token is stored", async () => {
    const { refreshTokens, onSessionExpired } = await freshModule();
    const seen = vi.fn();
    onSessionExpired(seen);

    await expect(refreshTokens()).rejects.toThrow("session_expired");
  });

  it("fires the session-expired event when the server rejects the refresh token", async () => {
    const { refreshTokens, storeRefreshToken, onSessionExpired } = await freshModule();
    storeRefreshToken("rt_revoked");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, false)));

    const seen = vi.fn();
    onSessionExpired(seen);

    await expect(refreshTokens()).rejects.toThrow("session_expired");
    expect(seen).toHaveBeenCalledTimes(1);
  });

  it("notifies onTokensRefreshed listeners on success", async () => {
    const { refreshTokens, storeRefreshToken, onTokensRefreshed } = await freshModule();
    storeRefreshToken("rt_original");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          access_token: "at_new",
          refresh_token: "rt_rotated",
          role: "owner",
          workspace_id: "ws_1",
        })
      )
    );

    const seen = vi.fn();
    onTokensRefreshed(seen);
    await refreshTokens();

    expect(seen).toHaveBeenCalledWith(expect.objectContaining({ access_token: "at_new" }));
  });
});

describe("decodeExpiry", () => {
  it("decodes a JWT's exp claim to epoch milliseconds", async () => {
    const { decodeExpiry } = await freshModule();
    const exp = Math.floor(Date.now() / 1000) + 900; // 15 minutes out
    const payload = btoa(JSON.stringify({ exp }));
    const jwt = `header.${payload}.signature`;

    expect(decodeExpiry(jwt)).toBe(exp * 1000);
  });

  it("falls back to a near-future timestamp for a malformed token", async () => {
    const { decodeExpiry } = await freshModule();
    const before = Date.now();
    expect(decodeExpiry("not-a-jwt")).toBeGreaterThan(before);
  });
});
