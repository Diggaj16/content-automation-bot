"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { getIdeas, approveIdea, triggerCreation, type Idea } from "../lib/api";

// ─── shared ──────────────────────────────────────────────────────────────────

const platformColors: Record<string, string> = {
  linkedin: "bg-blue-100 text-blue-700",
  twitter:  "bg-sky-100 text-sky-700",
  blog:     "bg-purple-100 text-purple-700",
  email:    "bg-amber-100 text-amber-700",
};

function PlatformBadge({ platform }: { platform: string }) {
  const cls = platformColors[platform] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {platform}
    </span>
  );
}

// ─── source article panel ─────────────────────────────────────────────────────

function SourceArticlePanel({ article }: { article: NonNullable<Idea["source_article"]> }) {
  const [showFull, setShowFull] = useState(false);
  const summary = article.structured_summary;

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 space-y-2 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div className="font-medium text-gray-900 text-sm">{article.title}</div>
        <span className="text-gray-400 whitespace-nowrap text-[10px]">{article.word_count} words</span>
      </div>

      <div className="flex items-center gap-2 text-gray-500 flex-wrap">
        <span>{article.source_name}</span>
        <span>|</span>
        <a href={article.url} target="_blank" rel="noopener noreferrer"
           className="text-blue-600 hover:underline truncate max-w-md">
          {article.url}
        </a>
        {article.pre_score != null && (
          <><span>|</span><span>Pre-score: {article.pre_score.toFixed(1)}</span></>
        )}
        {article.vision_fallback_used && (
          <span className="bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded">Vision fallback</span>
        )}
        {article.paywall_detected && (
          <span className="bg-red-100 text-red-600 px-1.5 py-0.5 rounded">Paywall detected</span>
        )}
      </div>

      {summary && (
        <div className="space-y-1.5 pt-1 border-t border-gray-200">
          <div><span className="font-semibold text-gray-700">Story: </span><span className="text-gray-600">{summary.story_narrative}</span></div>
          {summary.key_data_points.length > 0 && (
            <div><span className="font-semibold text-gray-700">Key data: </span><span className="text-gray-600">{summary.key_data_points.join(" | ")}</span></div>
          )}
          {summary.mechanism && (
            <div><span className="font-semibold text-gray-700">Mechanism: </span><span className="text-gray-600">{summary.mechanism}</span></div>
          )}
          {summary.implications && (
            <div><span className="font-semibold text-gray-700">Implications: </span><span className="text-gray-600">{summary.implications}</span></div>
          )}
        </div>
      )}

      <div>
        <button onClick={() => setShowFull((v) => !v)} className="text-blue-600 hover:underline text-xs">
          {showFull ? "Hide scraped text" : "Show full scraped text"}
        </button>
        {showFull && (
          <pre className="mt-2 bg-white border border-gray-200 rounded p-2 max-h-64 overflow-auto whitespace-pre-wrap text-xs text-gray-700 leading-relaxed">
            {article.full_text}
          </pre>
        )}
      </div>
    </div>
  );
}

// ─── idea card (pending only) ─────────────────────────────────────────────────

function IdeaCard({
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
          <button onClick={() => setShowReasoning((v) => !v)} className="text-xs text-blue-600 hover:underline">
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
            className="w-full text-sm border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
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
}

// ─── read-only row (approved / rejected tabs) ─────────────────────────────────

function ReadOnlyIdeaRow({ idea }: { idea: Idea }) {
  return (
    <div className="flex items-center gap-3 py-2.5 px-4 bg-white border border-gray-100 rounded-lg">
      <PlatformBadge platform={idea.platform} />
      {idea.score != null && (
        <span className="text-xs text-gray-400 tabular-nums whitespace-nowrap">
          {idea.score.toFixed(1)}
        </span>
      )}
      <p className="flex-1 text-sm text-gray-800 truncate">
        {idea.edited_angle || idea.angle}
      </p>
      <span className="text-xs text-gray-400 whitespace-nowrap">
        {new Date(idea.created_at).toLocaleDateString()}
      </span>
    </div>
  );
}

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
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [sortBy, setSortBy] = useState<SortOption>("score_desc");
  const [platformFilter, setPlatformFilter] = useState<string>("");

  const [approvedIds, setApprovedIds] = useState<string[]>([]);
  const [contentType, setContentType] = useState("news_driven");
  const [creationMsg, setCreationMsg] = useState<string | null>(null);
  const [sendingToCreation, setSendingToCreation] = useState(false);

  const [rejectingAll, setRejectingAll] = useState(false);

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
  const fetchIdeas = useCallback(async () => {
    setLoading(true);
    setError(null);
    setPlatformFilter("");
    try {
      setIdeas(await getIdeas(tab));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load ideas");
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => { fetchIdeas(); }, [fetchIdeas]);

  // ── derived state ──────────────────────────────────────────────────────────
  const platforms = useMemo(
    () => Array.from(new Set(ideas.map((i) => i.platform))).sort(),
    [ideas]
  );

  const displayedIdeas = useMemo(() => {
    let list = platformFilter ? ideas.filter((i) => i.platform === platformFilter) : ideas;
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
    setIdeas((prev) => prev.filter((i) => i.id !== id));
    showToast("Action recorded.");
  }, [showToast]);

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
        setIdeas((prev) => prev.filter((i) => i.id !== id));
        count++;
      } catch {
        // continue with others
      }
    }
    showToast(`Rejected ${count} idea${count !== 1 ? "s" : ""}.`);
    setRejectingAll(false);
  };

  const handleSendToCreation = async () => {
    setSendingToCreation(true);
    setCreationMsg(null);
    try {
      const r = await triggerCreation(approvedIds, contentType);
      setCreationMsg(
        `Queued ${r.idea_count} idea${r.idea_count !== 1 ? "s" : ""} as ${r.content_type} — job: ${r.job_id ?? "n/a"}`
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
              : `${ideas.length} idea${ideas.length !== 1 ? "s" : ""}${
                  platformFilter ? ` · ${displayedIdeas.length} shown` : ""
                }`}
          </p>
        </div>
        <button
          onClick={fetchIdeas}
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
            onClick={() => { setTab(t); setSortBy(t === "pending_approval" ? "score_desc" : "date_desc"); }}
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
                onApproved={(id) => setApprovedIds((prev) => [...prev, id])}
              />
            ))
          : displayedIdeas.map((idea) => (
              <ReadOnlyIdeaRow key={idea.id} idea={idea} />
            ))}
      </div>

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
