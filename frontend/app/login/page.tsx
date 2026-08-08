"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useSession, isNoWorkspace } from "@/components/session";

type Mode = "login" | "signup";
type Step = "credentials" | "verify" | "otp" | "workspace";

export default function LoginPage() {
  const { signIn, createWorkspace, switchWorkspace } = useSession();
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("signup");
  const [step, setStep] = useState<Step>("credentials");

  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [orgName, setOrgName] = useState("");
  const [city, setCity] = useState("");
  const [dob, setDob] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [emailToken, setEmailToken] = useState("");
  const [mobileToken, setMobileToken] = useState("");

  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [otp, setOtp] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const clearError = () => setError(null);

  const handleCredentials = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    setBusy(true);
    try {
      if (mode === "signup") {
        if (password !== confirmPassword) {
          setError("Passwords do not match");
          return;
        }
        const data = await api.signup({
          email,
          phone,
          password,
          confirm_password: confirmPassword,
          org_name: orgName,
          city,
          dob: dob || undefined,
        });
        if (data.email_verification_token) setEmailToken(data.email_verification_token);
        if (data.mobile_verification_token) setMobileToken(data.mobile_verification_token);
        setStep("verify");
      } else {
        const login = await api.login(email, password);
        if (login.mfa_required && login.mfa_token) {
          setMfaToken(login.mfa_token);
          setStep("otp");
        } else if (login.access_token) {
          // OTP/MFA disabled — the backend returned tokens directly.
          const all = await signIn(login as import("@/lib/api").Tokens);
          if (all.length === 0) {
            setStep("workspace");
          } else if (login.workspace_id && !isNoWorkspace(login.workspace_id)) {
            router.push("/opportunities");
          } else {
            await switchWorkspace(all[0].workspace_id);
            router.push("/opportunities");
          }
        } else {
          setError("Unexpected login response");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    setBusy(true);
    try {
      if (emailToken) await api.verifyEmail(emailToken);
      if (mobileToken) await api.verifyMobile(mobileToken);
      setMode("login");
      setStep("credentials");
      // Stay on credentials so the user enters password for login.
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setBusy(false);
    }
  };

  const handleOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mfaToken) return;
    clearError();
    setBusy(true);
    try {
      const tokens = await api.mfaChallenge(mfaToken, otp);
      const all = await signIn(tokens);
      if (all.length === 0) {
        setStep("workspace");
      } else if (tokens.workspace_id && !isNoWorkspace(tokens.workspace_id)) {
        router.push("/opportunities");
      } else {
        // MFA challenge returns the sentinel account workspace; switch to the
        // first available workspace so workspace-scoped pages work immediately.
        await switchWorkspace(all[0].workspace_id);
        router.push("/opportunities");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid code");
    } finally {
      setBusy(false);
    }
  };

  const handleWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    setBusy(true);
    try {
      await createWorkspace(workspaceName || "My Firm");
      router.push("/opportunities");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create workspace");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-md">
      <div className="rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-ink">
          {step === "verify"
            ? "Verify your account"
            : step === "otp"
            ? "Enter login code"
            : step === "workspace"
            ? "Create your workspace"
            : mode === "signup"
            ? "Create your account"
            : "Welcome back"}
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          {step === "verify"
            ? "Enter the verification codes sent to your email and mobile."
            : step === "otp"
            ? "We sent a 6-digit code to your registered email/mobile."
            : step === "workspace"
            ? "Your account is ready. Start by creating a workspace for your projects."
            : mode === "signup"
            ? "One account. Multiple workspaces. Multiple projects per workspace."
            : "Sign in to your account."}
        </p>

        {step === "credentials" && (
          <form onSubmit={handleCredentials} className="mt-6 space-y-4">
            {mode === "signup" && (
              <>
                <Field label="Organisation / Firm name" value={orgName} onChange={setOrgName} placeholder="Acme Infra Pvt Ltd" required />
                <Field label="Email" type="email" value={email} onChange={setEmail} placeholder="you@firm.com" required />
                <Field label="Mobile" type="tel" value={phone} onChange={setPhone} placeholder="+91 99999 99999" required />
                <Field label="City" value={city} onChange={setCity} placeholder="Mumbai" required />
                <Field label="Date of birth" type="date" value={dob} onChange={setDob} />
              </>
            )}
            {mode === "login" && (
              <Field label="Email" type="email" value={email} onChange={setEmail} placeholder="you@firm.com" required />
            )}
            <Field label="Password" type="password" value={password} onChange={setPassword} placeholder="••••••••" required />
            {mode === "signup" && (
              <Field label="Re-enter password" type="password" value={confirmPassword} onChange={setConfirmPassword} placeholder="••••••••" required />
            )}

            {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

            <button
              disabled={busy}
              className="w-full rounded-md bg-ink py-2.5 font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "Please wait…" : mode === "signup" ? "Create account" : "Sign in"}
            </button>
          </form>
        )}

        {step === "verify" && (
          <form onSubmit={handleVerify} className="mt-6 space-y-4">
            <Field label="Email verification code" value={emailToken} onChange={setEmailToken} placeholder="Paste email code" required />
            <Field
              label="Mobile verification code"
              value={mobileToken}
              onChange={setMobileToken}
              placeholder={mobileToken ? "Paste mobile code" : "Mobile verification disabled"}
              required={!!mobileToken}
            />
            {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
            <button disabled={busy} className="w-full rounded-md bg-ink py-2.5 font-medium text-white hover:opacity-90 disabled:opacity-50">
              {busy ? "Verifying…" : "Verify and continue"}
            </button>
          </form>
        )}

        {step === "otp" && (
          <form onSubmit={handleOtp} className="mt-6 space-y-4">
            <Field label="6-digit login code" value={otp} onChange={setOtp} placeholder="123456" required />
            {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
            <button disabled={busy} className="w-full rounded-md bg-ink py-2.5 font-medium text-white hover:opacity-90 disabled:opacity-50">
              {busy ? "Verifying…" : "Verify"}
            </button>
          </form>
        )}

        {step === "workspace" && (
          <form onSubmit={handleWorkspace} className="mt-6 space-y-4">
            <Field label="Workspace name" value={workspaceName} onChange={setWorkspaceName} placeholder="Acme Infra" required />
            {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
            <button disabled={busy} className="w-full rounded-md bg-ink py-2.5 font-medium text-white hover:opacity-90 disabled:opacity-50">
              {busy ? "Creating…" : "Create workspace"}
            </button>
          </form>
        )}

        {step === "credentials" && (
          <button
            onClick={() => setMode(mode === "signup" ? "login" : "signup")}
            className="mt-4 w-full text-sm text-slate-500 hover:text-ink"
          >
            {mode === "signup" ? "Already have an account? Sign in" : "New here? Create an account"}
          </button>
        )}

        <Link
          href="/forgot-password"
          className="mt-2 block w-full text-center text-sm text-slate-500 hover:text-ink"
        >
          Forgot your password?
        </Link>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-ink focus:ring-1 focus:ring-ink"
      />
    </label>
  );
}
