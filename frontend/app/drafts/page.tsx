"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { getDrafts, approveDraft, type Draft } from "../lib/api";
import type { DraftsResponse } from "../lib/api";

// ─── shared ───────────────────────────────────────────────────────────────────

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

function getTomorrowAt9AM(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(9, 0, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// ─── draft card (pending only) ────────────────────────────────────────────────

function DraftCard({ draft, onAction }: { draft: Draft; onAction: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const [approving, setApproving] = useState(false);
  const [contentText, setContentText] = useState(draft.content_text);
  const [scheduledAt, setScheduledAt] = useState(getTomorrowAt9AM());
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const handleApprove = async () => {
    setBusy(true); setLocalError(null);
    try {
      await approveDraft(draft.id, {
        approval_status: "approved",
        content_text: contentText !== draft.content_text ? contentText : undefined,
        scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : undefined,
      });
      onAction(draft.id);
    } catch (e: unknown) {
      setLocalError(e instanceof Error ? e.message : "Failed to approve");
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async () => {
    setBusy(true); setLocalError(null);
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
          {draft.target_persona && (
            <span className="px-2 py-0.5 rounded text-[10px] uppercase font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
              {draft.target_persona}
            </span>
          )}
          {draft.compliance_status && (
            <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-semibold border ${
              draft.compliance_status === 'approved' ? 'bg-green-50 text-green-700 border-green-200' :
              draft.compliance_status === 'flagged' ? 'bg-amber-50 text-amber-700 border-amber-200' :
              'bg-red-50 text-red-700 border-red-200'
            }`}>
              Compliance: {draft.compliance_status}
            </span>
          )}
          {draft.finance_flags && draft.finance_flags.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              {draft.finance_flags.map((flag, i) => (
                <span key={i} title={flag.context}
                  className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800 border border-yellow-200">
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

      <div className="text-sm text-gray-800 leading-relaxed">
        <p>{expanded ? draft.content_text : preview}{!expanded && hasMore && "…"}</p>
        {hasMore && (
          <button onClick={() => setExpanded((v) => !v)} className="text-xs text-blue-600 hover:underline mt-1">
            {expanded ? "Show less" : "Show more"}
          </button>
        )}
      </div>

      {draft.agent_reasoning && (
        <details className="text-xs">
          <summary className="cursor-pointer text-blue-600 hover:underline">Agent reasoning</summary>
          <p className="mt-1 text-gray-600 bg-gray-50 rounded p-2 leading-relaxed">{draft.agent_reasoning}</p>
        </details>
      )}

      {approving ? (
        <div className="space-y-3 pt-1 border-t border-gray-100">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Edit content before approving</label>
            <textarea className="w-full text-sm border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={8} value={contentText} onChange={(e) => setContentText(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Schedule at</label>
            <input type="datetime-local"
              className="text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} />
          </div>
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
}

// ─── read-only row (approved / rejected tabs) ─────────────────────────────────

function ReadOnlyDraftRow({ draft }: { draft: Draft }) {
  const [expanded, setExpanded] = useState(false);
  const preview = draft.content_text.slice(0, 160);
  const hasMore = draft.content_text.length > 160;

  return (
    <div className="bg-white border border-gray-100 rounded-lg px-4 py-3 space-y-1">
      <div className="flex items-center gap-3 flex-wrap">
        <PlatformBadge platform={draft.platform} />
        {draft.target_persona && (
          <span className="px-2 py-0.5 rounded text-[10px] uppercase font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
            {draft.target_persona}
          </span>
        )}
        {draft.compliance_status && (
          <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-semibold border ${
            draft.compliance_status === 'approved' ? 'bg-green-50 text-green-700 border-green-200' :
            draft.compliance_status === 'flagged' ? 'bg-amber-50 text-amber-700 border-amber-200' :
            'bg-red-50 text-red-700 border-red-200'
          }`}>
            Compliance: {draft.compliance_status}
          </span>
        )}
        <p className="flex-1 text-sm text-gray-800 w-full mt-1">
          {expanded ? draft.content_text : preview}{!expanded && hasMore && "…"}
        </p>
        <span className="text-xs text-gray-400 whitespace-nowrap">
          {new Date(draft.created_at).toLocaleDateString()}
        </span>
      </div>
      {hasMore && (
        <button onClick={() => setExpanded((v) => !v)} className="text-xs text-blue-600 hover:underline ml-1">
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}

// ─── pagination component ─────────────────────────────────────────────────────

function PaginationBar({
  currentPage,
  totalPages,
  onPageChange,
}: {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}) {
  if (totalPages <= 1) return null;

  // Build a smart page list: show first, last, current pages with gaps
  const pages: (number | "ellipsis")[] = [];
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= currentPage - 1 && i <= currentPage + 1)) {
      pages.push(i);
    } else if (pages[pages.length - 1] !== "ellipsis") {
      pages.push("ellipsis");
    }
  }

  return (
    <div className="flex items-center justify-center gap-1 pt-4">
      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage <= 1}
        className="px-3 py-1.5 text-sm border border-gray-300 rounded text-gray-700 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
      >
        ◀ Prev
      </button>
      {pages.map((p, i) =>
        p === "ellipsis" ? (
          <span key={`e-${i}`} className="px-2 text-gray-400 text-sm">…</span>
        ) : (
          <button
            key={p}
            onClick={() => onPageChange(p)}
            className={`px-3 py-1.5 text-sm border rounded ${
              p === currentPage
                ? "bg-blue-600 text-white border-blue-600"
                : "border-gray-300 text-gray-700 hover:bg-gray-50"
            }`}
          >
            {p}
          </button>
        )
      )}
      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage >= totalPages}
        className="px-3 py-1.5 text-sm border border-gray-300 rounded text-gray-700 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
      >
        Next ▶
      </button>
    </div>
  );
}

// ─── types ────────────────────────────────────────────────────────────────────

type StatusTab = "pending_approval" | "approved" | "rejected";
type SortOption = "date_desc" | "date_asc" | "platform_az";

const SORT_LABELS: Record<SortOption, string> = {
  date_desc:   "Date ↓",
  date_asc:    "Date ↑",
  platform_az: "Platform A→Z",
};

const TAB_LABELS: Record<StatusTab, string> = {
  pending_approval: "Pending",
  approved:         "Approved",
  rejected:         "Rejected",
};

const PAGE_SIZE = 50;

// ─── main page ────────────────────────────────────────────────────────────────

export default function DraftsPage() {
  const [tab, setTab] = useState<StatusTab>("pending_approval");
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [sortBy, setSortBy] = useState<SortOption>("date_desc");
  const [platformFilter, setPlatformFilter] = useState<string>("");

  // ── pagination state ──────────────────────────────────────────────────────
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);

  // ── toast ──────────────────────────────────────────────────────────────────
  const showToast = useCallback((msg: string) => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast(msg);
    toastTimerRef.current = setTimeout(() => setToast(null), 3000);
  }, []);

  useEffect(() => {
    return () => { if (toastTimerRef.current) clearTimeout(toastTimerRef.current); };
  }, []);

  // ── fetch ──────────────────────────────────────────────────────────────────
  const fetchDrafts = useCallback(async (page: number = 1) => {
    setLoading(true);
    setError(null);
    setPlatformFilter("");
    try {
      const resp: DraftsResponse = await getDrafts(tab, page, PAGE_SIZE);
      setDrafts(resp.data);
      setTotalPages(resp.total_pages);
      setTotalItems(resp.total);
      setCurrentPage(resp.page);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load drafts");
    } finally {
      setLoading(false);
    }
  }, [tab]);

  // Re-fetch when tab changes, resetting to page 1
  useEffect(() => {
    setCurrentPage(1);
    fetchDrafts(1);
  }, [fetchDrafts]);

  // ── page change handler ────────────────────────────────────────────────────
  const handlePageChange = useCallback((page: number) => {
    setCurrentPage(page);
    fetchDrafts(page);
  }, [fetchDrafts]);

  // ── derived state ──────────────────────────────────────────────────────────
  const platforms = useMemo(
    () => Array.from(new Set(drafts.map((d) => d.platform))).sort(),
    [drafts]
  );

  const displayedDrafts = useMemo(() => {
    let list = platformFilter ? drafts.filter((d) => d.platform === platformFilter) : drafts;
    const sorted = [...list];
    switch (sortBy) {
      case "date_desc":   sorted.sort((a, b) => b.created_at.localeCompare(a.created_at)); break;
      case "date_asc":    sorted.sort((a, b) => a.created_at.localeCompare(b.created_at)); break;
      case "platform_az": sorted.sort((a, b) => a.platform.localeCompare(b.platform)); break;
    }
    return sorted;
  }, [drafts, platformFilter, sortBy]);

  // ── handler ────────────────────────────────────────────────────────────────
  const handleAction = useCallback((id: string) => {
    setDrafts((prev) => prev.filter((d) => d.id !== id));
    showToast("Action recorded.");
  }, [showToast]);

  // ── render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Gate 2 — Drafts</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {loading
              ? "Loading…"
              : `${totalItems} draft${totalItems !== 1 ? "s" : ""}${
                  totalPages > 1 ? ` · Page ${currentPage} of ${totalPages}` : ""
                }${
                  platformFilter ? ` · ${displayedDrafts.length} shown` : ""
                }`}
          </p>
        </div>
        <button
          onClick={() => fetchDrafts(currentPage)}
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
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? "border-blue-600 text-blue-700"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            }`}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-2 flex-wrap">
        <select
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
          disabled={loading || platforms.length === 0}
          className="text-sm border border-gray-300 rounded px-3 py-1.5 bg-white disabled:opacity-50"
        >
          <option value="">All platforms</option>
          {platforms.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as SortOption)}
          className="text-sm border border-gray-300 rounded px-3 py-1.5 bg-white"
        >
          {(Object.entries(SORT_LABELS) as [SortOption, string][]).map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>
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
      {!loading && !error && displayedDrafts.length === 0 && (
        <div className="text-center py-12 text-gray-400 text-sm">
          {tab === "pending_approval"
            ? "No pending drafts. All caught up!"
            : `No ${TAB_LABELS[tab].toLowerCase()} drafts.`}
        </div>
      )}

      {/* Cards (pending) or compact rows (approved/rejected) */}
      <div className="grid gap-3">
        {tab === "pending_approval"
          ? displayedDrafts.map((draft) => (
              <DraftCard key={draft.id} draft={draft} onAction={handleAction} />
            ))
          : displayedDrafts.map((draft) => (
              <ReadOnlyDraftRow key={draft.id} draft={draft} />
            ))}
      </div>

      {/* Pagination */}
      {!loading && totalPages > 1 && (
        <PaginationBar
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={handlePageChange}
        />
      )}
    </div>
  );
}