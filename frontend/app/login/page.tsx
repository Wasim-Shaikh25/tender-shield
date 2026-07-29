"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useSession } from "@/components/session";

export default function LoginPage() {
  const { signIn } = useSession();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mfaToken) {
        const tokens = await api.mfaChallenge(mfaToken, mfaCode);
        await signIn(tokens);
        router.push("/opportunities");
        return;
      }

      if (mode === "signup") {
        await api.signup(email, password, workspaceName || "My Firm");
      }
      const tokens = await api.login(email, password);
      if (tokens.mfa_required && tokens.mfa_token) {
        setMfaToken(tokens.mfa_token);
        setBusy(false);
        return;
      }
      await signIn(tokens);
      router.push("/opportunities");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <div className="rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-ink">
          {mfaToken ? "Two-factor authentication" : mode === "signup" ? "Create your account" : "Welcome back"}
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          {mfaToken
            ? "Enter the 6-digit code from your authenticator app."
            : mode === "signup"
            ? "One free full tender review per workspace."
            : "Sign in to your opportunity board."}
        </p>

        <form onSubmit={submit} className="mt-6 space-y-4">
          {!mfaToken && mode === "signup" && (
            <Field label="Workspace" value={workspaceName} onChange={setWorkspaceName} placeholder="Acme Infra Pvt Ltd" />
          )}
          {!mfaToken && (
            <Field label="Email" type="email" value={email} onChange={setEmail} placeholder="you@firm.com" />
          )}
          {!mfaToken && (
            <Field label="Password" type="password" value={password} onChange={setPassword} placeholder="••••••••" />
          )}
          {mfaToken && (
            <Field label="Authenticator code" value={mfaCode} onChange={setMfaCode} placeholder="123456" />
          )}

          {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

          <button
            disabled={busy}
            className="w-full rounded-md bg-ink py-2.5 font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Please wait…" : mfaToken ? "Verify" : mode === "signup" ? "Create account" : "Sign in"}
          </button>
        </form>

        {!mfaToken && (
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
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-ink focus:ring-1 focus:ring-ink"
      />
    </label>
  );
}
