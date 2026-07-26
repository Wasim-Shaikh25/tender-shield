"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [result, setResult] = useState<{ ok: boolean; token?: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.forgotPassword(email);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <div className="rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-ink">Reset your password</h1>
        <p className="mt-1 text-sm text-slate-500">
          Enter your email and we will send a reset link.
        </p>

        <form onSubmit={submit} className="mt-6 space-y-4">
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@firm.com"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-ink focus:ring-1 focus:ring-ink"
            />
          </label>

          {result && (
            <p className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">
              If this email is registered, a reset link has been generated.
              {result.token && (
                <>
                  {" "}
                  Dev token: <code className="font-mono text-xs">{result.token}</code>
                </>
              )}
            </p>
          )}

          {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

          <button
            disabled={busy}
            className="w-full rounded-md bg-ink py-2.5 font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Please wait…" : "Send reset link"}
          </button>
        </form>

        <Link
          href="/login"
          className="mt-4 block w-full text-center text-sm text-slate-500 hover:text-ink"
        >
          Back to sign in
        </Link>
      </div>
    </div>
  );
}
