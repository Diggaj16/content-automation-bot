"use client";

import { useState, useEffect } from "react";
import { getDrafts, approveDraft, type Draft } from "../lib/api";

const platformColors: Record<string, string> = {
  linkedin: "bg-blue-100 text-blue-700",
  twitter: "bg-sky-100 text-sky-700",
  blog: "bg-purple-100 text-purple-700",
  email: "bg-amber-100 text-amber-700",
};

function PlatformBadge({ platform }: { platform: string }) {
  const cls = platformColors[platform] ?? "bg-gray-100 text-gray-700";
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${cls}`}
    >
      {platform}
    </span>
  );
}

function getTomorrowAt9AM(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(9, 0, 0, 0);
  // Format as datetime-local value: "YYYY-MM-DDTHH:mm"
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function DraftCard({
  draft,
  onAction,
}: {
  draft: Draft;
  onAction: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [approving, setApproving] = useState(false);
  const [contentText, setContentText] = useState(draft.content_text);
  const [scheduledAt, setScheduledAt] = useState(getTomorrowAt9AM());
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const handleApprove = async () => {
    setBusy(true);
    setLocalError(null);
    try {
      await approveDraft(draft.id, {
        approval_status: "approved",
        content_text: contentText !== draft.content_text ? contentText : undefined,
        scheduled_at: scheduledAt
          ? new Date(scheduledAt).toISOString()
          : undefined,
      });
      onAction(draft.id);
    } catch (e: unknown) {
      setLocalError(e instanceof Error ? e.message : "Failed to approve");
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async () => {
    setBusy(true);
    setLocalError(null);
    try {
      await approveDraft(draft.id, { approval_status: "rejected" });
      onAction(draft.id);
    } catch (e: unknown) {
      setLocalError(e instanceof Error ? e.message : "Failed to reject");
    } finally {
      setBusy(false);
    }
  };

  const preview = draft.content_text.slice(0, 200);
  const hasMore = draft.content_text.length > 200;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <PlatformBadge platform={draft.platform} />
          {draft.finance_flags && draft.finance_flags.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              {draft.finance_flags.map((flag, i) => (
                <span
                  key={i}
                  className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800 border border-yellow-200"
                  title={flag.context}
                >
                  ⚠ {flag.flag_type}
                </span>
              ))}
            </div>
          )}
        </div>
        <span className="text-xs text-gray-400 whitespace-nowrap">
          {new Date(draft.created_at).toLocaleDateString()}
        </span>
      </div>

      {/* Content preview */}
      <div className="text-sm text-gray-800 leading-relaxed">
        <p>
          {expanded ? draft.content_text : preview}
          {!expanded && hasMore && "..."}
        </p>
        {hasMore && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-blue-600 hover:underline mt-1"
          >
            {expanded ? "Show less" : "Show more"}
          </button>
        )}
      </div>

      {/* Agent reasoning */}
      {draft.agent_reasoning && (
        <details className="text-xs">
          <summary className="cursor-pointer text-blue-600 hover:underline">
            Agent reasoning
          </summary>
          <p className="mt-1 text-gray-600 bg-gray-50 rounded p-2 leading-relaxed">
            {draft.agent_reasoning}
          </p>
        </details>
      )}

      {/* Approve form */}
      {approving ? (
        <div className="space-y-3 pt-1 border-t border-gray-100">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Edit content before approving
            </label>
            <textarea
              className="w-full text-sm border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={8}
              value={contentText}
              onChange={(e) => setContentText(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Schedule at
            </label>
            <input
              type="datetime-local"
              className="text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
            />
          </div>
          {localError && (
            <p className="text-xs text-red-600">{localError}</p>
          )}
          <div className="flex gap-2">
            <button
              onClick={handleApprove}
              disabled={busy}
              className="px-3 py-1.5 text-xs bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
            >
              {busy ? "Saving..." : "Confirm Approve"}
            </button>
            <button
              onClick={() => setApproving(false)}
              disabled={busy}
              className="px-3 py-1.5 text-xs border border-gray-300 text-gray-600 rounded hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2 pt-1">
          {localError && (
            <span className="text-xs text-red-600 mr-2">{localError}</span>
          )}
          <button
            onClick={() => setApproving(true)}
            disabled={busy}
            className="px-3 py-1.5 text-xs bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
          >
            Approve
          </button>
          <button
            onClick={handleReject}
            disabled={busy}
            className="px-3 py-1.5 text-xs bg-red-50 text-red-700 border border-red-200 rounded hover:bg-red-100 disabled:opacity-50"
          >
            {busy ? "Rejecting..." : "Reject"}
          </button>
        </div>
      )}
    </div>
  );
}

export default function DraftsPage() {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const fetchDrafts = async () => {
    setLoading(true);
    setError(null);
    try {
      setDrafts(await getDrafts("pending_approval"));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load drafts");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDrafts();
  }, []);

  const handleAction = (id: string) => {
    setDrafts((prev) => prev.filter((d) => d.id !== id));
    setToast("Action recorded.");
    setTimeout(() => setToast(null), 3000);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">
            Gate 2 — Drafts Approval
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {loading
              ? "Loading..."
              : `${drafts.length} pending draft${drafts.length !== 1 ? "s" : ""}`}
          </p>
        </div>
        <button
          onClick={fetchDrafts}
          disabled={loading}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {toast && (
        <div className="px-4 py-3 rounded-md text-sm bg-green-50 text-green-700 border border-green-200">
          {toast}
        </div>
      )}

      {error && (
        <div className="px-4 py-3 rounded-md text-sm bg-red-50 text-red-700 border border-red-200">
          {error}
        </div>
      )}

      {!loading && !error && drafts.length === 0 && (
        <div className="text-center py-12 text-gray-500 text-sm">
          No pending drafts. All caught up!
        </div>
      )}

      <div className="grid gap-4">
        {drafts.map((draft) => (
          <DraftCard key={draft.id} draft={draft} onAction={handleAction} />
        ))}
      </div>
    </div>
  );
}
