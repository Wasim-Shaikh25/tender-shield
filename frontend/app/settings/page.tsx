"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type AccountSettings } from "@/lib/api";
import { useSession } from "@/components/session";

export default function SettingsPage() {
  const { session, signOut } = useSession();
  const router = useRouter();
  const [settings, setSettings] = useState<AccountSettings | null>(null);
  const [form, setForm] = useState({ org_name: "", city: "", phone: "", dob: "" });
  const [password, setPassword] = useState({ current: "", new: "", confirm: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    api.getSettings(session.token)
      .then((s) => {
        setSettings(s);
        setForm({
          org_name: s.org_name ?? "",
          city: s.city ?? "",
          phone: s.phone ?? "",
          dob: s.dob ?? "",
        });
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load settings"));
  }, [session]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  const updateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const body: Parameters<typeof api.updateSettings>[1] = {};
      if (form.org_name !== (settings?.org_name ?? "")) body.org_name = form.org_name;
      if (form.city !== (settings?.city ?? "")) body.city = form.city;
      if (form.phone !== (settings?.phone ?? "")) body.phone = form.phone;
      if (form.dob !== (settings?.dob ?? "")) body.dob = form.dob || undefined;
      const updated = await api.updateSettings(session.token, body);
      setSettings(updated);
      setMessage("Profile updated." + (body.phone ? " A mobile verification code has been sent." : ""));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    } finally {
      setLoading(false);
    }
  };

  const changePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session) return;
    if (password.new !== password.confirm) {
      setError("New password and confirmation do not match.");
      return;
    }
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      await api.changePassword(session.token, {
        current_password: password.current,
        new_password: password.new,
        confirm_password: password.confirm,
      });
      setPassword({ current: "", new: "", confirm: "" });
      setMessage("Password changed.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Password change failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-ink">Account & Security</h1>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {message && <p className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">{message}</p>}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink">Profile</h2>
        {settings ? (
          <form onSubmit={updateProfile} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="settings-email" className="mb-1 block text-sm font-medium text-slate-700">Email</label>
                <input id="settings-email" readOnly value={settings.email} className="w-full rounded-md border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-500" />
                {settings.email_verified && <span className="text-xs text-green-600">Verified</span>}
              </div>
              <div>
                <label htmlFor="settings-phone" className="mb-1 block text-sm font-medium text-slate-700">Phone</label>
                <input
                  id="settings-phone"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
                {settings.mobile_verified ? (
                  <span className="text-xs text-green-600">Verified</span>
                ) : (
                  <span className="text-xs text-amber-600">Unverified</span>
                )}
              </div>
              <div>
                <label htmlFor="settings-org" className="mb-1 block text-sm font-medium text-slate-700">Organisation / Firm</label>
                <input
                  id="settings-org"
                  value={form.org_name}
                  onChange={(e) => setForm({ ...form, org_name: e.target.value })}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label htmlFor="settings-city" className="mb-1 block text-sm font-medium text-slate-700">City</label>
                <input
                  id="settings-city"
                  value={form.city}
                  onChange={(e) => setForm({ ...form, city: e.target.value })}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label htmlFor="settings-dob" className="mb-1 block text-sm font-medium text-slate-700">Date of Birth</label>
                <input
                  id="settings-dob"
                  type="date"
                  value={form.dob}
                  onChange={(e) => setForm({ ...form, dob: e.target.value })}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              Save profile
            </button>
          </form>
        ) : (
          <p className="text-sm text-slate-500">Loading profile...</p>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink">Security</h2>
        <form onSubmit={changePassword} className="space-y-4">
          <div>
            <label htmlFor="settings-current-password" className="mb-1 block text-sm font-medium text-slate-700">Current password</label>
            <input
              id="settings-current-password"
              type="password"
              value={password.current}
              onChange={(e) => setPassword({ ...password, current: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              required
            />
          </div>
          <div>
            <label htmlFor="settings-new-password" className="mb-1 block text-sm font-medium text-slate-700">New password</label>
            <input
              id="settings-new-password"
              type="password"
              value={password.new}
              onChange={(e) => setPassword({ ...password, new: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              required
              minLength={8}
            />
          </div>
          <div>
            <label htmlFor="settings-confirm-password" className="mb-1 block text-sm font-medium text-slate-700">Confirm new password</label>
            <input
              id="settings-confirm-password"
              type="password"
              value={password.confirm}
              onChange={(e) => setPassword({ ...password, confirm: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              required
              minLength={8}
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Change password
          </button>
        </form>

        <div className="mt-6 border-t border-slate-100 pt-4">
          <button
            onClick={signOut}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Sign out
          </button>
        </div>
      </section>
    </div>
  );
}
