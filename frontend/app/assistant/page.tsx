"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type AssistantSession, type AssistantMessage, type PlanDashboard } from "@/lib/api";
import { useSession } from "@/components/session";
import { Markdown } from "@/components/markdown";
import { DashboardView } from "@/components/plan-dashboard";

type UIMessage = AssistantMessage & { loading?: boolean };

const SOURCE_LABEL: Record<string, string> = {
  tool: "Tool result",
  llm: "AI answer",
  refusal: "Scope guard",
  user: "You",
};

const SOURCE_CLASS: Record<string, string> = {
  tool: "bg-emerald-100 text-emerald-700",
  llm: "bg-blue-100 text-blue-700",
  refusal: "bg-amber-100 text-amber-700",
  user: "bg-slate-100 text-slate-600",
};

export default function AssistantPage() {
  const { session } = useSession();
  const [sessions, setSessions] = useState<AssistantSession[]>([]);
  const [activeSession, setActiveSession] = useState<AssistantSession | null>(null);
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [panelDashboard, setPanelDashboard] = useState<PlanDashboard | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const sendingRef = useRef(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadSessions = useCallback(async () => {
    if (!session) return;
    const res = await api.listAssistantSessions(session.token);
    setSessions(res.sessions);
  }, [session]);

  useEffect(() => {
    if (!session) return;
    loadSessions();
  }, [session, loadSessions]);

  useEffect(() => {
    if (!session || !activeSession) {
      setMessages([]);
      return;
    }
    if (sendingRef.current) return;
    api.getAssistantMessages(session.token, activeSession.id)
      .then((res) => setMessages(res.messages))
      .catch(() => setError("Could not load messages."));
  }, [session, activeSession]);

  if (!session) {
    return null;
  }

  async function createSession(title?: string) {
    if (!session) throw new Error("Not authenticated");
    const res = await api.createAssistantSession(session.token, title);
    await loadSessions();
    setActiveSession(res);
    return res;
  }

  async function deleteSession(id: string) {
    if (!session) return;
    if (!confirm("Delete this chat?")) return;
    try {
      await api.deleteAssistantSession(session.token, id);
      if (activeSession?.id === id) {
        setActiveSession(null);
        setMessages([]);
      }
      await loadSessions();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete chat");
    }
  }

  function startNewChat() {
    setActiveSession(null);
    setMessages([]);
    setInput("");
    setPanelOpen(false);
  }

  async function send(text: string) {
    if (!session || !text.trim() || loading) return;
    sendingRef.current = true;
    const trimmed = text.trim();
    setInput("");
    setError(null);

    let sess = activeSession;
    let assistantId = "";
    try {
      if (!sess) {
        sess = await createSession(trimmed.slice(0, 40));
      }

      setLoading(true);
      const userMsg: UIMessage = {
        id: `u-${Date.now()}`,
        role: "user",
        content: trimmed,
        type: "text",
        grounded: true,
        source: "user",
        created_at: new Date().toISOString(),
      };
      assistantId = `a-${Date.now()}`;
      setMessages((m) => [
        ...m,
        userMsg,
        {
          id: assistantId,
          role: "assistant",
          content: "",
          type: "text",
          grounded: true,
          loading: true,
          created_at: new Date().toISOString(),
        },
      ]);

      const data = await api.sendAssistantMessage(session.token, sess.id, trimmed);
      setMessages((m) =>
        m.map((x) =>
          x.id === assistantId
            ? { ...data, id: assistantId, loading: false }
            : x
        )
      );
      if (data.type === "dashboard" && data.dashboard) {
        setPanelDashboard(data.dashboard ?? null);
        setPanelOpen(true);
      }
      await loadSessions();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Assistant request failed");
      if (assistantId) {
        setMessages((m) => m.filter((x) => x.id !== assistantId));
      }
    } finally {
      sendingRef.current = false;
      setLoading(false);
    }
  }

  const activeTitle = activeSession?.title || activeSession?.id?.slice(0, 8) || "New chat";

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col gap-4 md:flex-row">
      {/* Sidebar: title + new chat + session history + delete */}
      <div className="flex w-full flex-col rounded-xl border border-slate-200 bg-white md:w-64 md:shrink-0">
        <div className="border-b border-slate-100 p-4">
          <h1 className="text-lg font-bold text-ink">AI Assistant</h1>
          <p className="text-xs text-slate-500">Ask about deadlines, risks, BOQ defects, or request a dashboard.</p>
          <button
            type="button"
            onClick={startNewChat}
            className="mt-3 w-full rounded-md bg-ink py-2 text-sm font-medium text-white hover:opacity-90"
          >
            + New chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {sessions.length === 0 && (
            <p className="p-2 text-xs text-slate-500">No previous chats.</p>
          )}
          {sessions.map((s) => (
            <div
              key={s.id}
              className={`group mb-1 flex items-center justify-between rounded-md px-3 py-2 text-sm ${
                activeSession?.id === s.id
                  ? "bg-slate-100 font-medium text-ink"
                  : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              <button
                type="button"
                onClick={() => setActiveSession(s)}
                className="min-w-0 flex-1 text-left"
              >
                <span className="block truncate">{s.title || `Chat ${s.id.slice(0, 8)}`}</span>
                <span className="block truncate text-xs text-slate-400">
                  {new Date(s.updated_at).toLocaleString()}
                </span>
              </button>
              <button
                type="button"
                onClick={() => deleteSession(s.id)}
                className="ml-2 rounded px-2 py-1 text-xs text-slate-400 hover:bg-red-50 hover:text-red-600 md:opacity-0 md:group-hover:opacity-100"
                aria-label="Delete chat"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Chat column */}
      <div className="flex flex-1 flex-col rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-100 p-3">
          <h2 className="text-sm font-semibold text-ink">{activeSession ? activeTitle : "Start a new chat"}</h2>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {!activeSession && messages.length === 0 && (
            <div className="rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
              Start typing to create a new chat. You can also pick an older chat from the sidebar.
            </div>
          )}
          {activeSession && messages.length === 0 && (
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
                className={`max-w-[90%] rounded-xl px-4 py-3 text-sm md:max-w-[80%] ${
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
                    {m.role === "assistant" ? (
                      <div className="assistant-markdown">
                        <Markdown source={m.content} />
                      </div>
                    ) : (
                      <p className="whitespace-pre-wrap">{m.content}</p>
                    )}

                    {m.role === "assistant" && (
                      <div className="flex flex-wrap items-center gap-2 pt-1">
                        {m.source && (
                          <span className={`rounded-full px-2 py-0.5 text-xs ${SOURCE_CLASS[m.source] || "bg-slate-100 text-slate-600"}`}>
                            {SOURCE_LABEL[m.source] || m.source}
                          </span>
                        )}
                        {m.citations && m.citations.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {m.citations.map((c, i) => (
                              <span key={i} className="rounded bg-slate-200 px-1.5 py-0.5 text-xs text-slate-700">
                                {c.replace(/^p/, "p. ")}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {m.type === "dashboard" && m.dashboard && (
                      <button
                        type="button"
                        onClick={() => {
                          setPanelDashboard(m.dashboard ?? null);
                          setPanelOpen(true);
                        }}
                        className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
                      >
                        {panelOpen ? "Hide dashboard" : "Show dashboard"}
                      </button>
                    )}

                    {m.role === "assistant" && m.suggested_followups && m.suggested_followups.length > 0 && (
                      <div className="flex flex-wrap gap-2 pt-1">
                        {m.suggested_followups.map((chip) => (
                          <button
                            key={chip}
                            type="button"
                            onClick={() => send(chip)}
                            disabled={loading}
                            className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs text-slate-700 hover:border-ink hover:text-ink disabled:opacity-50"
                          >
                            {chip}
                          </button>
                        ))}
                      </div>
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

        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="flex items-start gap-2 border-t border-slate-100 p-4"
        >
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
        <div className="w-full overflow-y-auto rounded-xl border border-slate-200 bg-white p-4 md:w-[45%] md:max-w-xl">
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
