"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useSession, isNoWorkspace } from "@/components/session";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

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

  const getTitle = () => {
    if (step === "verify") return "Verify your account";
    if (step === "otp") return "Enter login code";
    if (step === "workspace") return "Create your workspace";
    if (mode === "signup") return "Create your account";
    return "Welcome back";
  };

  const getDescription = () => {
    if (step === "verify") return "Enter the verification codes sent to your email and mobile.";
    if (step === "otp") return "We sent a 6-digit code to your registered email/mobile.";
    if (step === "workspace") return "Your account is ready. Start by creating a workspace for your projects.";
    if (mode === "signup") return "One account. Multiple workspaces. Multiple projects per workspace.";
    return "Sign in to your account to continue.";
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-bg-primary">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>{getTitle()}</CardTitle>
          <CardDescription>{getDescription()}</CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          {error && (
            <Alert variant="error" title="Error">
              {error}
            </Alert>
          )}

          {step === "credentials" && (
            <form onSubmit={handleCredentials} className="space-y-4">
              {mode === "signup" && (
                <>
                  <Input
                    label="Organisation / Firm name"
                    value={orgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    placeholder="Acme Infra Pvt Ltd"
                    required
                  />
                  <Input
                    label="Email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@firm.com"
                    required
                  />
                  <Input
                    label="Mobile"
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+91 99999 99999"
                    required
                  />
                  <Input
                    label="City"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    placeholder="Mumbai"
                    required
                  />
                  <Input
                    label="Date of birth"
                    type="date"
                    value={dob}
                    onChange={(e) => setDob(e.target.value)}
                  />
                </>
              )}
              {mode === "login" && (
                <Input
                  label="Email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@firm.com"
                  required
                />
              )}
              <Input
                label="Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
              {mode === "signup" && (
                <Input
                  label="Re-enter password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                />
              )}

              <Button
                type="submit"
                variant="primary"
                size="md"
                loading={busy}
                className="w-full"
              >
                {mode === "signup" ? "Create account" : "Sign in"}
              </Button>
            </form>
          )}

          {step === "verify" && (
            <form onSubmit={handleVerify} className="space-y-4">
              <Input
                label="Email verification code"
                value={emailToken}
                onChange={(e) => setEmailToken(e.target.value)}
                placeholder="Paste email code"
                required
              />
              <Input
                label="Mobile verification code"
                value={mobileToken}
                onChange={(e) => setMobileToken(e.target.value)}
                placeholder="Paste mobile code"
                required
              />
              <Button
                type="submit"
                variant="primary"
                size="md"
                loading={busy}
                className="w-full"
              >
                Verify and continue
              </Button>
            </form>
          )}

          {step === "otp" && (
            <form onSubmit={handleOtp} className="space-y-4">
              <Input
                label="6-digit login code"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                placeholder="123456"
                required
              />
              <Button
                type="submit"
                variant="primary"
                size="md"
                loading={busy}
                className="w-full"
              >
                Verify
              </Button>
            </form>
          )}

          {step === "workspace" && (
            <form onSubmit={handleWorkspace} className="space-y-4">
              <Input
                label="Workspace name"
                value={workspaceName}
                onChange={(e) => setWorkspaceName(e.target.value)}
                placeholder="Acme Infra"
                required
              />
              <Button
                type="submit"
                variant="primary"
                size="md"
                loading={busy}
                className="w-full"
              >
                Create workspace
              </Button>
            </form>
          )}

          {step === "credentials" && (
            <div className="space-y-2 text-center text-sm">
              <button
                type="button"
                onClick={() => setMode(mode === "signup" ? "login" : "signup")}
                className="text-text-muted hover:text-text-secondary transition-colors"
              >
                {mode === "signup" ? "Already have an account? Sign in" : "New here? Create an account"}
              </button>
              <Link
                href="/forgot-password"
                className="block text-text-muted hover:text-text-secondary transition-colors"
              >
                Forgot your password?
              </Link>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
