"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, PlanDashboard } from "@/lib/api";
import { useSession } from "@/components/session";
import { DashboardView } from "@/components/plan-dashboard";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  type?: string;
  dashboard?: PlanDashboard;
  source?: string;
  loading?: boolean;
};

export default function AssistantPage() {
  const { session } = useSession();
  const router = useRouter();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [panelDashboard, setPanelDashboard] = useState<PlanDashboard | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  const sendMessage = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || loading) return;
    const text = input.trim();
    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: "user",
      content: text,
    };
    const assistantId = `a-${Date.now()}`;
    setMessages((m) => [...m, userMsg, {
      id: assistantId,
      role: "assistant",
      content: "",
      loading: true,
    }]);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const data = await api.askAssistant(session.token, text);
      const assistantMsg: Message = {
        id: assistantId,
        role: "assistant",
        content: data.answer,
        type: data.type || "text",
        dashboard: data.dashboard,
        source: data.source,
      };
      setMessages((m) => m.map((x) => (x.id === assistantId ? assistantMsg : x)));
      if (data.type === "dashboard" && data.dashboard) {
        setPanelDashboard(data.dashboard);
        setPanelOpen(true);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Assistant request failed");
      setMessages((m) => m.filter((x) => x.id !== assistantId));
    } finally {
      setLoading(false);
    }
  };

  const togglePanel = (dashboard?: PlanDashboard) => {
    if (dashboard) setPanelDashboard(dashboard);
    setPanelOpen((p) => !p);
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col gap-4 md:flex-row">
      {/* Chat column */}
      <div className="flex flex-1 flex-col rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-100 p-4">
          <h1 className="text-xl font-bold text-ink">AI Assistant</h1>
          <p className="text-sm text-slate-600">
            Ask anything about your workspace — deadlines, risks, BOQ defects, documents, or request a dashboard across all tenders.
          </p>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {messages.length === 0 && (
            <div className="rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
              Try: “What are the critical risks across my tenders?” or “Show a risk severity dashboard.”
            </div>
          )}
          {messages.map((m) => (
            <div
              key={m.id}
              className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-xl px-4 py-3 text-sm ${
                  m.role === "user"
                    ? "bg-ink text-white"
                    : "border border-slate-200 bg-slate-50 text-slate-800"
                }`}
              >
                {m.loading ? (
                  <span className="inline-flex items-center gap-2">
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
                    Thinking…
                  </span>
                ) : (
                  <div className="space-y-2">
                    <p className="whitespace-pre-wrap">{m.content}</p>
                    {m.type === "dashboard" && m.dashboard && (
                      <button
                        type="button"
                        onClick={() => togglePanel(m.dashboard)}
                        className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
                      >
                        {panelOpen ? "Hide dashboard" : "Show dashboard"}
                      </button>
                    )}
                    {m.source && (
                      <p className="text-xs opacity-70">Source: {m.source}</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {error && (
          <div className="px-4 pb-2">
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
          </div>
        )}

        <form onSubmit={sendMessage} className="flex items-start gap-2 border-t border-slate-100 p-4">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            placeholder="Ask about your workspace…"
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm text-ink disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </div>

      {/* Collapsible dashboard panel */}
      {panelOpen && panelDashboard && (
        <div className="w-full rounded-xl border border-slate-200 bg-white p-4 md:w-[45%] md:max-w-xl overflow-y-auto">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-ink">Dashboard</h2>
            <button
              type="button"
              onClick={() => setPanelOpen(false)}
              className="text-sm text-slate-500 hover:text-ink"
            >
              Close
            </button>
          </div>
          <DashboardView dashboard={panelDashboard} />
        </div>
      )}
    </div>
  );
}
