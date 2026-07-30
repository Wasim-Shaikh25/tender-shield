import { test as base, request, type Page, type APIRequestContext } from "@playwright/test";

const API = "http://localhost:8000/api";

export type TestAccount = {
  email: string;
  phone: string;
  password: string;
  token: string;
};

/**
 * Create an account, verify email + mobile, complete MFA login, and return the
 * access token. In dev mode the backend returns verification/MFA codes directly.
 */
export async function createAccount(
  apiContext: APIRequestContext,
  email: string,
  phone: string,
  password = "Test1234!"
): Promise<TestAccount> {
  const signup = await apiContext.post(`${API}/auth/signup`, {
    data: { email, phone, password, confirm_password: password, org_name: "E2E", city: "Mumbai" },
  });
  if (!signup.ok()) throw new Error(`signup failed: ${await signup.text()}`);
  const signupBody = await signup.json();

  await apiContext.post(`${API}/auth/verify-email`, { data: { token: signupBody.email_verification_token } });
  await apiContext.post(`${API}/auth/verify-mobile`, { data: { token: signupBody.mobile_verification_token } });

  const login = await apiContext.post(`${API}/auth/login`, { data: { email, password } });
  if (!login.ok()) throw new Error(`login failed: ${await login.text()}`);
  const loginBody = await login.json();

  const challenge = await apiContext.post(`${API}/auth/mfa/challenge`, {
    data: { mfa_token: loginBody.mfa_token, code: loginBody.mfa_code },
  });
  if (!challenge.ok()) throw new Error(`mfa challenge failed: ${await challenge.text()}`);
  const tokens = await challenge.json();
  return { email, phone, password, token: tokens.access_token };
}

export const test = base.extend<{ authenticatedPage: Page }>({
  authenticatedPage: async ({ browser }, use) => {
    const ctx = await browser.newContext();
    const apiContext = ctx.request;
    const ts = Date.now();
    await createAccount(apiContext, `e2e-${ts}@example.com`, `+9198765432${ts % 100}`.slice(0, 13));
    const page = await ctx.newPage();
    await use(page);
    await ctx.close();
  },
});
