"use client";

import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import useSWR from "swr";
import { getIdeas, approveIdea, triggerCreation, type Idea, type IdeasResponse } from "../lib/api";
import { useJobStatus } from "../hooks/useJobStatus";
import SourceArticlePanel from "../components/SourceArticlePanel";

// ─── shared ──────────────────────────────────────────────────────────────────

const platformColors: Record<string, string> = {
  linkedin: "bg-blue-100 text-blue-700",
  twitter:  "bg-sky-100 text-sky-700",
  blog:     "bg-purple-100 text-purple-700",
  email:    "bg-amber-100 text-amber-700",
  whatsapp: "bg-green-100 text-green-700",
  carousel: "bg-pink-100 text-pink-700",
  advisor_talking_points: "bg-slate-100 text-slate-700",
};

function PlatformBadge({ platform }: { platform: string }) {
  const cls = platformColors[platform] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {platform}
    </span>
  );
}

// ─── idea card (pending only) ─────────────────────────────────────────────────

const IdeaCard = React.memo(function IdeaCard({
  idea,
  onAction,
  onApproved,
}: {
  idea: Idea;
  onAction: (id: string) => void;
  onApproved: (id: string) => void;
}) {
  const [showReasoning, setShowReasoning] = useState(false);
  const [showArticle, setShowArticle] = useState(false);
  const [approving, setApproving] = useState(false);
  const [editedAngle, setEditedAngle] = useState(idea.angle);
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const handleApprove = async () => {
    setBusy(true); setLocalError(null);
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
    setBusy(true); setLocalError(null);
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
          {idea.target_persona && (
            <span className="px-2 py-0.5 rounded text-[10px] uppercase font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
              {idea.target_persona}
            </span>
          )}
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
          {idea.source_article && (
            <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500">
              {idea.source_article.source_name}
            </span>
          )}
        </div>
        <span className="text-xs text-gray-400 whitespace-nowrap">
          {new Date(idea.created_at).toLocaleDateString()}
        </span>
      </div>

      <p className="text-sm font-medium text-gray-900">{idea.angle}</p>

      <div className="flex gap-3">
        {idea.agent_reasoning && (
          <button onClick={() => setShowReasoning((v) => !v)} className="text-xs hover:underline" style={{ color: "var(--brand-text)" }}>
            {showReasoning ? "Hide reasoning" : "Show reasoning"}
          </button>
        )}
        {idea.source_article && (
          <button onClick={() => setShowArticle((v) => !v)} className="text-xs text-green-700 hover:underline font-medium">
            {showArticle ? "Hide scraped article" : "View scraped article"}
          </button>
        )}
      </div>

      {showReasoning && idea.agent_reasoning && (
        <p className="text-xs text-gray-600 bg-gray-50 rounded p-2 leading-relaxed">{idea.agent_reasoning}</p>
      )}
      {showArticle && idea.source_article && <SourceArticlePanel article={idea.source_article} />}

      {approving ? (
        <div className="space-y-2 pt-1">
          <label className="block text-xs font-medium text-gray-700">Edit angle before approving</label>
          <textarea
            className="w-full text-sm border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2" style={{ "--tw-ring-color": "var(--brand)" } as React.CSSProperties}
            rows={3}
            value={editedAngle}
            onChange={(e) => setEditedAngle(e.target.value)}
          />
          {localError && <p className="text-xs text-red-600">{localError}</p>}
          <div className="flex gap-2">
            <button onClick={handleApprove} disabled={busy}
              className="px-3 py-1.5 text-xs bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50">
              {busy ? "Saving…" : "Confirm Approve"}
            </button>
            <button onClick={() => setApproving(false)} disabled={busy}
              className="px-3 py-1.5 text-xs border border-gray-300 text-gray-600 rounded hover:bg-gray-50 disabled:opacity-50">
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2 pt-1">
          {localError && <span className="text-xs text-red-600 mr-2">{localError}</span>}
          <button onClick={() => setApproving(true)} disabled={busy}
            className="px-3 py-1.5 text-xs bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50">
            Approve
          </button>
          <button onClick={handleReject} disabled={busy}
            className="px-3 py-1.5 text-xs bg-red-50 text-red-700 border border-red-200 rounded hover:bg-red-100 disabled:opacity-50">
            {busy ? "Rejecting…" : "Reject"}
          </button>
        </div>
      )}
    </div>
  );
});

// ─── read-only row (approved / rejected tabs) ─────────────────────────────────

const ReadOnlyIdeaRow = React.memo(function ReadOnlyIdeaRow({ idea }: { idea: Idea }) {
  return (
    <div className="bg-white border border-gray-100 rounded-lg px-4 py-3 space-y-1.5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <PlatformBadge platform={idea.platform} />
          {idea.target_persona && (
            <span className="px-2 py-0.5 rounded text-[10px] uppercase font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
              {idea.target_persona}
            </span>
          )}
          {idea.score != null && (
            <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
              Score: {idea.score.toFixed(2)}
            </span>
          )}
        </div>
        <span className="text-xs text-gray-400 whitespace-nowrap">
          {new Date(idea.created_at).toLocaleDateString()}
        </span>
      </div>
      <p className="text-sm text-gray-800">
        {idea.edited_angle || idea.angle}
      </p>
    </div>
  );
});

// ─── types ────────────────────────────────────────────────────────────────────

type StatusTab = "pending_approval" | "approved" | "rejected";
type SortOption = "score_desc" | "score_asc" | "date_desc" | "date_asc" | "platform_az";

const SORT_LABELS: Record<SortOption, string> = {
  score_desc:  "Score ↓",
  score_asc:   "Score ↑",
  date_desc:   "Date ↓",
  date_asc:    "Date ↑",
  platform_az: "Platform A→Z",
};

const TAB_LABELS: Record<StatusTab, string> = {
  pending_approval: "Pending",
  approved:         "Approved",
  rejected:         "Rejected",
};

// ─── main page ────────────────────────────────────────────────────────────────

export default function IdeasPage() {
  const [tab, setTab] = useState<StatusTab>("pending_approval");
  const [toast, setToast] = useState<string | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [sortBy, setSortBy] = useState<SortOption>("score_desc");
  const [platformFilter, setPlatformFilter] = useState<string>("");

  const [approvedIds, setApprovedIds] = useState<string[]>([]);
  const [contentType, setContentType] = useState("news_driven");
  const [creationMsg, setCreationMsg] = useState<string | null>(null);
  const [sendingToCreation, setSendingToCreation] = useState(false);

  const [rejectingAll, setRejectingAll] = useState(false);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 50;

  const creationJob = useJobStatus();

  // ── SWR fetch ──────────────────────────────────────────────────────────────
  const {
    data: ideasResp,
    isLoading: loading,
    error: swrError,
    mutate: refreshIdeas,
  } = useSWR<IdeasResponse>(
    `/api/proxy/ideas?status=${tab}&page=${page}`,
    () => getIdeas(tab, page, PAGE_SIZE),
    { revalidateOnFocus: false, dedupingInterval: 3000 }
  );

  const ideas = ideasResp?.data ?? [];
  const totalPages = ideasResp?.total_pages ?? 1;
  const total = ideasResp?.total ?? 0;

  const error = swrError instanceof Error ? swrError.message : swrError ? "Failed to load ideas" : null;

  // ── toast ──────────────────────────────────────────────────────────────────
  const showToast = useCallback((msg: string) => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast(msg);
    toastTimerRef.current = setTimeout(() => setToast(null), 3000);
  }, []);

  useEffect(() => {
    return () => { if (toastTimerRef.current) clearTimeout(toastTimerRef.current); };
  }, []);

  // ── derived state ──────────────────────────────────────────────────────────
  const platforms = useMemo(
    () => Array.from(new Set(ideas.map((i) => i.platform))).sort(),
    [ideas]
  );

  const displayedIdeas = useMemo(() => {
    const list = platformFilter ? ideas.filter((i) => i.platform === platformFilter) : ideas;
    const sorted = [...list];
    switch (sortBy) {
      case "score_desc":  sorted.sort((a, b) => (b.score ?? 0) - (a.score ?? 0)); break;
      case "score_asc":   sorted.sort((a, b) => (a.score ?? 0) - (b.score ?? 0)); break;
      case "date_desc":   sorted.sort((a, b) => b.created_at.localeCompare(a.created_at)); break;
      case "date_asc":    sorted.sort((a, b) => a.created_at.localeCompare(b.created_at)); break;
      case "platform_az": sorted.sort((a, b) => a.platform.localeCompare(b.platform)); break;
    }
    return sorted;
  }, [ideas, platformFilter, sortBy]);

  // ── handlers ───────────────────────────────────────────────────────────────
  const handleAction = useCallback((id: string) => {
    // Optimistic update: remove acted-on idea from SWR cache immediately
    refreshIdeas((prev) =>
      prev ? { ...prev, data: prev.data.filter((i) => i.id !== id) } : prev,
      false
    );
    showToast("Action recorded.");
    // Background revalidate to sync with server
    refreshIdeas();
  }, [showToast, refreshIdeas]);

  const handleApproved = useCallback((id: string) => {
    setApprovedIds((prev) => [...prev, id]);
  }, []);

  const handleRejectAll = async () => {
    if (!confirm(
      `Reject all ${displayedIdeas.length} visible idea${displayedIdeas.length !== 1 ? "s" : ""}?`
    )) return;
    setRejectingAll(true);
    let count = 0;
    // snapshot IDs before iteration — list mutates as we go
    const ids = displayedIdeas.map((i) => i.id);
    for (const id of ids) {
      try {
        await approveIdea(id, { approval_status: "rejected" });
        // Optimistic update per-item as we go
        refreshIdeas((prev) =>
          prev ? { ...prev, data: prev.data.filter((i) => i.id !== id) } : prev,
          false
        );
        count++;
      } catch {
        // continue with others
      }
    }
    showToast(`Rejected ${count} idea${count !== 1 ? "s" : ""}.`);
    setRejectingAll(false);
    // Final sync with server
    refreshIdeas();
  };

  const handleSendToCreation = async () => {
    setSendingToCreation(true);
    setCreationMsg(null);
    try {
      const r = await triggerCreation(approvedIds, contentType);
      if (r.job_id) {
        creationJob.start(
          r.job_id,
          "creation",
          `Creation (${r.idea_count} idea${r.idea_count !== 1 ? "s" : ""})`
        );
      }
      const countMismatch = r.idea_count !== approvedIds.length;
      setCreationMsg(
        `Queued ${r.idea_count} idea${r.idea_count !== 1 ? "s" : ""} as ${r.content_type} — job: ${r.job_id ?? "n/a"}`
        + (countMismatch ? ` ⚠ ${approvedIds.length - r.idea_count} idea(s) were not queued.` : "")
      );
      setApprovedIds([]);
    } catch (e: unknown) {
      setCreationMsg(e instanceof Error ? e.message : "Failed");
    } finally {
      setSendingToCreation(false);
    }
  };

  // ── render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4 pb-24">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Gate 1 — Ideas</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {loading
              ? "Loading…"
              : `${total} idea${total !== 1 ? "s" : ""}${
                  platformFilter ? ` · ${displayedIdeas.length} shown` : ""
                }${totalPages > 1 ? ` · page ${page} of ${totalPages}` : ""}`}
          </p>
        </div>
        <button
          onClick={() => refreshIdeas()}
          disabled={loading}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {/* Status tabs */}
      <div className="flex gap-0 border-b border-gray-200">
        {(["pending_approval", "approved", "rejected"] as StatusTab[]).map((t) => (
          <button
            key={t}
            onClick={() => {
              setTab(t);
              setPage(1);
              setSortBy(t === "pending_approval" ? "score_desc" : "date_desc");
              setPlatformFilter("");
            }}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            }`}
            style={tab === t ? { borderColor: "var(--brand)", color: "var(--brand-text)" } : undefined}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Platform filter */}
        <select
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
          disabled={loading || platforms.length === 0}
          className="text-sm border border-gray-300 rounded px-3 py-1.5 bg-white disabled:opacity-50"
        >
          <option value="">All platforms</option>
          {platforms.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>

        {/* Sort */}
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as SortOption)}
          className="text-sm border border-gray-300 rounded px-3 py-1.5 bg-white"
        >
          {(Object.entries(SORT_LABELS) as [SortOption, string][]).map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>

        {/* Reject all — pending tab only */}
        {tab === "pending_approval" && displayedIdeas.length > 0 && (
          <button
            onClick={handleRejectAll}
            disabled={rejectingAll || loading}
            className="ml-auto px-3 py-1.5 text-sm border border-red-200 text-red-600 rounded hover:bg-red-50 disabled:opacity-50"
          >
            {rejectingAll
              ? "Rejecting…"
              : `Reject all ${displayedIdeas.length}`}
          </button>
        )}
      </div>

      {/* Toast / error */}
      {toast && (
        <div className="px-4 py-2 rounded-md text-sm bg-green-50 text-green-700 border border-green-200">
          {toast}
        </div>
      )}
      {error && (
        <div className="px-4 py-2 rounded-md text-sm bg-red-50 text-red-700 border border-red-200">
          {error}
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && displayedIdeas.length === 0 && (
        <div className="text-center py-12 text-gray-400 text-sm">
          {tab === "pending_approval"
            ? "No pending ideas. All caught up!"
            : `No ${TAB_LABELS[tab].toLowerCase()} ideas.`}
        </div>
      )}

      {/* Cards (pending) or compact rows (approved/rejected) */}
      <div className="grid gap-3">
        {tab === "pending_approval"
          ? displayedIdeas.map((idea) => (
              <IdeaCard
                key={idea.id}
                idea={idea}
                onAction={handleAction}
                onApproved={handleApproved}
              />
            ))
          : displayedIdeas.map((idea) => (
              <ReadOnlyIdeaRow key={idea.id} idea={idea} />
            ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 pt-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1 || loading}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-40"
          >
            ← Prev
          </button>
          <span className="text-sm text-gray-500">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages || loading}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      )}

      {/* Sticky "send to creation" bar — appears once ideas are approved */}
      {approvedIds.length > 0 && (
        <div className="fixed bottom-0 left-56 right-0 bg-white border-t border-gray-200 shadow-lg px-6 py-3 flex items-center gap-3 flex-wrap z-40">
          <span className="text-sm font-medium text-gray-700">
            {approvedIds.length} idea{approvedIds.length !== 1 ? "s" : ""} approved
          </span>
          <select
            value={contentType}
            onChange={(e) => setContentType(e.target.value)}
            className="text-sm border border-gray-300 rounded px-3 py-1.5 bg-white"
          >
            <option value="news_driven">News-driven</option>
            <option value="kb_driven">KB-driven</option>
            <option value="combined">Combined</option>
          </select>
          <button
            onClick={handleSendToCreation}
            disabled={sendingToCreation}
            className="px-4 py-1.5 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 font-medium"
          >
            {sendingToCreation ? "Sending…" : "Send to Creation"}
          </button>
          <button
            onClick={() => { setApprovedIds([]); setCreationMsg(null); }}
            className="text-xs text-gray-400 hover:text-gray-600 px-1"
            title="Clear approved list"
          >
            × clear
          </button>
          {creationMsg && (
            <p className="text-xs text-gray-600 ml-2">{creationMsg}</p>
          )}
        </div>
      )}
    </div>
  );
}
