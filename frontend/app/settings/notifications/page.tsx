"use client";

import { useEffect, useState } from "react";
import { api, type NotificationPreferences } from "@/lib/api";
import { useSession } from "@/components/session";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";

export default function NotificationSettingsPage() {
  const { session } = useSession();
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

  if (!prefs) return <p className="p-6 text-sm text-text-muted">Loading...</p>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-heading-lg text-text-primary">Notification Preferences</h1>
        <p className="text-sm text-text-muted mt-2">Manage how and when you receive notifications</p>
      </div>

      {/* Alerts */}
      {error && <Alert variant="error" title="Error">{error}</Alert>}
      {message && <Alert variant="success" title="Success">{message}</Alert>}

      {/* Notification Channels */}
      <Card>
        <CardHeader>
          <CardTitle>Notification Channels</CardTitle>
          <CardDescription>Choose how you want to be notified</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {([
            ["email_deadlines", "Email deadline alerts", "Notify me by email when a tender deadline is approaching."],
            ["sms_deadlines", "SMS deadline alerts", "Notify me by SMS when a tender deadline is approaching."],
            ["email_digest", "Email digest", "Send a periodic summary of activity by email."],
            ["sms_alerts", "SMS alerts", "Send high-priority alerts by SMS."],
            ["marketing", "Marketing communications", "Receive product updates and offers."],
          ] as Array<[keyof NotificationPreferences, string, string]>).map(([key, label, help]) => (
            <label key={key} htmlFor={`pref-${key}`} aria-label={label} className="flex items-start gap-3 p-3 rounded-lg hover:bg-bg-secondary transition-colors cursor-pointer">
              <input
                id={`pref-${key}`}
                type="checkbox"
                checked={!!prefs[key]}
                onChange={(e) => update({ [key]: e.target.checked })}
                disabled={loading}
                className="mt-1 h-4 w-4 accent-ink"
              />
              <div>
                <p className="text-sm font-medium text-text-primary">{label}</p>
                <p className="text-xs text-text-muted">{help}</p>
              </div>
            </label>
          ))}
        </CardContent>
      </Card>

      {/* Quiet Hours */}
      <Card>
        <CardHeader>
          <CardTitle>Quiet Hours</CardTitle>
          <CardDescription>Specify times when you don&apos;t want to receive notifications</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="quiet-start" className="block text-sm font-medium text-text-primary mb-2">Start time (hour, 0-23)</label>
            <input
              id="quiet-start"
              type="number"
              min={0}
              max={23}
              value={prefs.quiet_hours_start ?? ""}
              onChange={(e) => update({ quiet_hours_start: e.target.value === "" ? null : parseInt(e.target.value, 10) })}
              className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
            />
          </div>
          <div>
            <label htmlFor="quiet-end" className="block text-sm font-medium text-text-primary mb-2">End time (hour, 0-23)</label>
            <input
              id="quiet-end"
              type="number"
              min={0}
              max={23}
              value={prefs.quiet_hours_end ?? ""}
              onChange={(e) => update({ quiet_hours_end: e.target.value === "" ? null : parseInt(e.target.value, 10) })}
              className="w-full rounded-md border border-border-default px-3 py-2 text-sm text-text-primary outline-none focus:border-ink focus:ring-1 focus:ring-ink"
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
