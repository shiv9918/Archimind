"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError, type ChatMessageOut } from "@/lib/api";

export default function ChatPanel({ repoId, repoReady }: { repoId: string; repoReady: boolean }) {
  const [messages, setMessages] = useState<ChatMessageOut[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getChatHistory(repoId).then(setMessages).catch(() => {});
  }, [repoId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const message = input.trim();
    if (!message || sending) return;

    setError(null);
    setInput("");
    setMessages((prev) => [
      ...prev,
      { id: `pending-${Date.now()}`, role: "user", content: message, created_at: new Date().toISOString() },
    ]);
    setSending(true);

    try {
      const { message: assistantMessage } = await api.postChat(repoId, message);
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to send message");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex h-[70vh] flex-col rounded-xl border border-slate-800 bg-slate-900/60">
      <div className="flex-1 space-y-4 overflow-y-auto p-5">
        {messages.length === 0 && (
          <p className="text-sm text-slate-500">
            Ask about this repository -- e.g. &quot;Explain the authentication flow&quot; or &quot;Where is UserService used?&quot;
          </p>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${
                m.role === "user" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-100"
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {sending && <p className="text-xs text-slate-500">ArchMind AI is thinking...</p>}
        <div ref={bottomRef} />
      </div>

      {error && <p className="border-t border-slate-800 px-5 py-2 text-xs text-red-400">{error}</p>}

      <form onSubmit={handleSend} className="flex gap-2 border-t border-slate-800 p-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={!repoReady || sending}
          placeholder={repoReady ? "Ask a question about this repository..." : "Waiting for scan to finish..."}
          className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-indigo-500 focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={!repoReady || sending || !input.trim()}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
