"use client";

import { useState, useEffect, useRef } from "react";
import { orchestrate, type OrchestratorResponse } from "../lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  tools_used?: string[];
}

const THREAD_KEY = "orchestrator_thread_id";

function getOrCreateThreadId(): string {
  if (typeof window === "undefined") return "default";
  let tid = localStorage.getItem(THREAD_KEY);
  if (!tid) {
    tid = crypto.randomUUID();
    localStorage.setItem(THREAD_KEY, tid);
  }
  return tid;
}

function messagesKey(tid: string) {
  return `orchestrator_messages_${tid}`;
}

function loadMessages(tid: string): Message[] {
  if (typeof window === "undefined" || !tid) return [];
  try {
    const raw = localStorage.getItem(messagesKey(tid));
    return raw ? (JSON.parse(raw) as Message[]) : [];
  } catch {
    return [];
  }
}

function saveMessages(tid: string, msgs: Message[]) {
  if (typeof window === "undefined" || !tid) return;
  // Keep last 100 messages to avoid bloating localStorage
  const trimmed = msgs.slice(-100);
  localStorage.setItem(messagesKey(tid), JSON.stringify(trimmed));
}

export default function OrchestratorPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string>("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // On mount: restore thread ID and its saved messages
  useEffect(() => {
    const tid = getOrCreateThreadId();
    setThreadId(tid);
    setMessages(loadMessages(tid));
  }, []);

  // Persist messages to localStorage whenever they change
  useEffect(() => {
    if (threadId) saveMessages(threadId, messages);
  }, [messages, threadId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);

    try {
      const result = await orchestrate(text, threadId);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: result.response,
          tools_used: result.tools_used,
        },
      ]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Request failed");
      setMessages((prev) => prev.slice(0, -1)); // Remove optimistic user message
      setInput(text); // Restore input
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const resetThread = () => {
    // Clear saved messages for the current thread, create a new one
    if (threadId) localStorage.removeItem(messagesKey(threadId));
    const newId = crypto.randomUUID();
    localStorage.setItem(THREAD_KEY, newId);
    setThreadId(newId);
    setMessages([]);
    setError(null);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Orchestrator</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Manage the pipeline with natural language
          </p>
        </div>
        <button
          onClick={resetThread}
          className="px-3 py-1.5 text-xs border border-gray-300 rounded text-gray-600 hover:bg-gray-50"
          title="Start a new conversation"
        >
          New conversation
        </button>
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.length === 0 && (
          <div className="text-center py-16 text-gray-400 text-sm space-y-2">
            <p className="text-2xl">🤖</p>
            <p className="font-medium text-gray-500">Orchestrator ready</p>
            <p>Try: &ldquo;Show pending ideas&rdquo;, &ldquo;Add site ET Markets https://...&rdquo;, &ldquo;Trigger research&rdquo;</p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-2xl rounded-lg px-4 py-3 text-sm ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-white border border-gray-200 text-gray-800"
              }`}
            >
              <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              {msg.tools_used && msg.tools_used.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {msg.tools_used.map((t) => (
                    <span
                      key={t}
                      className="inline-block px-2 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-500"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-lg px-4 py-3 text-sm text-gray-400">
              <span className="animate-pulse">Thinking...</span>
            </div>
          </div>
        )}

        {error && (
          <div className="flex justify-center">
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-600">
              {error}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 flex gap-3 items-end border-t border-gray-200 pt-4">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          rows={2}
          placeholder="Ask the orchestrator... (Enter to send, Shift+Enter for newline)"
          className="flex-1 resize-none border border-gray-300 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
        />
        <button
          onClick={sendMessage}
          disabled={loading || !input.trim()}
          className="px-5 py-3 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </div>
    </div>
  );
}
