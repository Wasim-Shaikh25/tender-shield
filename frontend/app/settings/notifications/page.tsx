"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type NotificationPreferences } from "@/lib/api";
import { useSession } from "@/components/session";

export default function NotificationSettingsPage() {
  const { session } = useSession();
  const router = useRouter();
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    api.getNotificationPreferences(session.token)
      .then(setPrefs)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, [session]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  const update = async (patch: Partial<NotificationPreferences>) => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const next = { ...prefs!, ...patch };
      const updated = await api.updateNotificationPreferences(session.token, next);
      setPrefs(updated);
      setMessage("Preferences saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setLoading(false);
    }
  };

  if (!prefs) return <p className="p-6 text-sm text-slate-500">Loading...</p>;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold text-ink">Notification preferences</h1>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {message && <p className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">{message}</p>}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="space-y-4">
          {([
            ["email_deadlines", "Email deadline alerts", "Notify me by email when a tender deadline is approaching."],
            ["sms_deadlines", "SMS deadline alerts", "Notify me by SMS when a tender deadline is approaching."],
            ["email_digest", "Email digest", "Send a periodic summary of activity by email."],
            ["sms_alerts", "SMS alerts", "Send high-priority alerts by SMS."],
            ["marketing", "Marketing communications", "Receive product updates and offers."],
          ] as Array<[keyof NotificationPreferences, string, string]>).map(([key, label, help]) => (
            <label key={key} htmlFor={`pref-${key}`} aria-label={label} className="flex items-start gap-3">
              <input
                id={`pref-${key}`}
                type="checkbox"
                checked={!!prefs[key]}
                onChange={(e) => update({ [key]: e.target.checked })}
                disabled={loading}
                className="mt-1 h-4 w-4"
              />
              <div>
                <p className="text-sm font-medium text-slate-900">{label}</p>
                <p className="text-xs text-slate-500">{help}</p>
              </div>
            </label>
          ))}
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="quiet-start" className="mb-1 block text-sm font-medium text-slate-700">Quiet hours start</label>
            <input
              id="quiet-start"
              type="number"
              min={0}
              max={23}
              value={prefs.quiet_hours_start ?? ""}
              onChange={(e) => update({ quiet_hours_start: e.target.value === "" ? null : parseInt(e.target.value, 10) })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="quiet-end" className="mb-1 block text-sm font-medium text-slate-700">Quiet hours end</label>
            <input
              id="quiet-end"
              type="number"
              min={0}
              max={23}
              value={prefs.quiet_hours_end ?? ""}
              onChange={(e) => update({ quiet_hours_end: e.target.value === "" ? null : parseInt(e.target.value, 10) })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        </div>
      </section>
    </div>
  );
}
