"use client";

import { useState, useEffect } from "react";
import { getIdeas, approveIdea, triggerCreation, type Idea } from "../lib/api";

const platformColors: Record<string, string> = {
  linkedin: "bg-blue-100 text-blue-700",
  twitter: "bg-sky-100 text-sky-700",
  blog: "bg-purple-100 text-purple-700",
  email: "bg-amber-100 text-amber-700",
};

function PlatformBadge({ platform }: { platform: string }) {
  const cls = platformColors[platform] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {platform}
    </span>
  );
}

function IdeaCard({
  idea,
  onAction,
  onApproved,
}: {
  idea: Idea;
  onAction: (id: string) => void;
  onApproved: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [approving, setApproving] = useState(false);
  const [editedAngle, setEditedAngle] = useState(idea.angle);
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const handleApprove = async () => {
    setBusy(true);
    setLocalError(null);
    try {
      await approveIdea(idea.id, {
        approval_status: "approved",
        edited_angle: editedAngle !== idea.angle ? editedAngle : undefined,
      });
      onApproved(idea.id);
      onAction(idea.id);
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
      await approveIdea(idea.id, { approval_status: "rejected" });
      onAction(idea.id);
    } catch (e: unknown) {
      setLocalError(e instanceof Error ? e.message : "Failed to reject");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <PlatformBadge platform={idea.platform} />
          {idea.score != null && (
            <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
              Score: {idea.score.toFixed(2)}
            </span>
          )}
          {idea.recent_coverage_flag && (
            <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-700">
              Recent coverage
            </span>
          )}
        </div>
        <span className="text-xs text-gray-400 whitespace-nowrap">
          {new Date(idea.created_at).toLocaleDateString()}
        </span>
      </div>

      <p className="text-sm font-medium text-gray-900">{idea.angle}</p>

      {idea.agent_reasoning && (
        <div>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-blue-600 hover:underline"
          >
            {expanded ? "Hide reasoning" : "Show reasoning"}
          </button>
          {expanded && (
            <p className="mt-1 text-xs text-gray-600 bg-gray-50 rounded p-2 leading-relaxed">
              {idea.agent_reasoning}
            </p>
          )}
        </div>
      )}

      {approving ? (
        <div className="space-y-2 pt-1">
          <label className="block text-xs font-medium text-gray-700">
            Edit angle before approving
          </label>
          <textarea
            className="w-full text-sm border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={3}
            value={editedAngle}
            onChange={(e) => setEditedAngle(e.target.value)}
          />
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

export default function IdeasPage() {
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [approvedIds, setApprovedIds] = useState<string[]>([]);
  const [creationMsg, setCreationMsg] = useState<string | null>(null);
  const [sendingToCreation, setSendingToCreation] = useState(false);

  const fetchIdeas = async () => {
    setLoading(true);
    setError(null);
    try {
      setIdeas(await getIdeas("pending"));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load ideas");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIdeas();
  }, []);

  const handleAction = (id: string) => {
    setIdeas((prev) => prev.filter((i) => i.id !== id));
    setToast("Action recorded.");
    setTimeout(() => setToast(null), 3000);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">
            Gate 1 — Ideas Approval
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {loading
              ? "Loading..."
              : `${ideas.length} pending idea${ideas.length !== 1 ? "s" : ""}`}
          </p>
        </div>
        <button
          onClick={fetchIdeas}
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

      {!loading && !error && ideas.length === 0 && (
        <div className="text-center py-12 text-gray-500 text-sm">
          No pending ideas. All caught up!
        </div>
      )}

      <div className="grid gap-4">
        {ideas.map((idea) => (
          <IdeaCard
            key={idea.id}
            idea={idea}
            onAction={handleAction}
            onApproved={(id) => setApprovedIds((prev) => [...prev, id])}
          />
        ))}
      </div>

      {approvedIds.length > 0 && (
        <div className="flex items-center gap-3 mt-4">
          <button
            onClick={async () => {
              setSendingToCreation(true); setCreationMsg(null);
              try {
                const r = await triggerCreation(approvedIds);
                setCreationMsg(`Creation queued for ${r.idea_count} idea(s) — job_id: ${r.job_id ?? "n/a"}`);
                setApprovedIds([]);
              } catch (e: unknown) {
                setCreationMsg(e instanceof Error ? `Error: ${e.message}` : "Failed");
              } finally { setSendingToCreation(false); }
            }}
            disabled={sendingToCreation}
            className="bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded"
          >
            {sendingToCreation ? "Sending…" : `Send ${approvedIds.length} approved idea(s) to Creation`}
          </button>
          {creationMsg && <p className="text-sm text-gray-600">{creationMsg}</p>}
        </div>
      )}
    </div>
  );
}
