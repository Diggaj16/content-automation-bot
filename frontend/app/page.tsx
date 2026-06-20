"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import {
  getStatus,
  triggerResearch,
  triggerScoring,
} from "./lib/api";
import { useJobStatus } from "./hooks/useJobStatus";
import JobStatusBadge from "./components/JobStatusBadge";

export default function DashboardPage() {
  const [triggerError, setTriggerError] = useState<string | null>(null);

  const research = useJobStatus();
  const scoring = useJobStatus();

  const {
    data: status,
    isLoading: loading,
    error: swrError,
    mutate: refreshStatus,
  } = useSWR(
    "/api/proxy/status?limit=10",
    () => getStatus(),
    { revalidateOnFocus: false, dedupingInterval: 5000 }
  );

  const error = swrError instanceof Error ? swrError.message : swrError ? "Failed to load" : null;

  // Auto-refresh run logs when a job completes
  useEffect(() => {
    if (research.state.phase === "complete" || scoring.state.phase === "complete") {
      refreshStatus();
    }
  }, [research.state.phase, scoring.state.phase, refreshStatus]);

  const handleTriggerResearch = async () => {
    research.reset();
    setTriggerError(null);
    try {
      const r = await triggerResearch();
      if (r.job_id) research.start(r.job_id, "research", "Research");
    } catch (e: unknown) {
      setTriggerError(e instanceof Error ? e.message : "Failed to trigger research");
    }
  };

  const handleTriggerScoring = async () => {
    scoring.reset();
    setTriggerError(null);
    try {
      const r = await triggerScoring();
      if (r.job_id) scoring.start(r.job_id, "scoring", "Scoring");
    } catch (e: unknown) {
      setTriggerError(e instanceof Error ? e.message : "Failed to trigger scoring");
    }
  };

  const researchBusy = research.state.phase === "queued" || research.state.phase === "in_progress";
  const scoringBusy = scoring.state.phase === "queued" || scoring.state.phase === "in_progress";

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>
        <button
          onClick={() => refreshStatus()}
          disabled={loading}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {/* Trigger buttons */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-3 flex-wrap">
          <button
            onClick={handleTriggerResearch}
            disabled={researchBusy}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 font-medium"
          >
            {researchBusy ? "Running…" : "▶ Trigger Research"}
          </button>
          <button
            onClick={handleTriggerScoring}
            disabled={scoringBusy}
            className="px-4 py-2 text-sm bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:opacity-50 font-medium"
          >
            {scoringBusy ? "Running…" : "▶ Trigger Scoring"}
          </button>
        </div>

        {/* Live job status badges */}
        {research.state.phase !== "idle" && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 w-20">Research</span>
            <JobStatusBadge state={research.state} onDismiss={research.reset} />
          </div>
        )}
        {scoring.state.phase !== "idle" && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 w-20">Scoring</span>
            <JobStatusBadge state={scoring.state} onDismiss={scoring.reset} />
          </div>
        )}
      </div>

      {error && (
        <div className="px-4 py-3 rounded-md text-sm bg-red-50 text-red-700 border border-red-200">
          {error}
        </div>
      )}
      {triggerError && (
        <div className="px-4 py-3 rounded-md text-sm bg-red-50 text-red-700 border border-red-200">
          {triggerError}
        </div>
      )}

      {loading && !status && (
        <div className="text-sm text-gray-500">Loading…</div>
      )}

      {status && (
        <>
          {/* Recent Runs Table */}
          <section>
            <h2 className="text-lg font-medium text-gray-800 mb-3">Recent Agent Runs</h2>
            {status.recent_runs.length === 0 ? (
              <p className="text-sm text-gray-500">No runs yet.</p>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-gray-200">
                <table className="min-w-full text-sm">
                  <thead className="bg-gray-50 text-gray-600 uppercase text-xs tracking-wide">
                    <tr>
                      <th className="px-4 py-2 text-left">Agent</th>
                      <th className="px-4 py-2 text-left">Trigger</th>
                      <th className="px-4 py-2 text-right">Processed</th>
                      <th className="px-4 py-2 text-right">Success</th>
                      <th className="px-4 py-2 text-right">Failure</th>
                      <th className="px-4 py-2 text-right">Duration (s)</th>
                      <th className="px-4 py-2 text-right">Cost</th>
                      <th className="px-4 py-2 text-left">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white">
                    {status.recent_runs.map((run) => (
                      <tr key={run.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 font-medium text-gray-900">{run.agent_name}</td>
                        <td className="px-4 py-2 text-gray-600">{run.trigger_type}</td>
                        <td className="px-4 py-2 text-right text-gray-700">{run.processed_count}</td>
                        <td className="px-4 py-2 text-right text-green-600 font-medium">{run.success_count}</td>
                        <td className="px-4 py-2 text-right text-red-500">
                          {run.failure_count > 0 ? run.failure_count : <span className="text-gray-300">0</span>}
                        </td>
                        <td className="px-4 py-2 text-right text-gray-600">{run.duration_seconds.toFixed(1)}</td>
                        <td className="px-4 py-2 text-right text-gray-600">
                          {run.token_cost?.total_usd != null
                            ? `$${run.token_cost.total_usd.toFixed(4)}`
                            : "—"}
                        </td>
                        <td className="px-4 py-2 text-gray-500 text-xs whitespace-nowrap">
                          {new Date(run.created_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Cost Log */}
          <section>
            <h2 className="text-lg font-medium text-gray-800 mb-3">Cost Log</h2>
            {status.cost_log.length === 0 ? (
              <p className="text-sm text-gray-500">No cost records yet.</p>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-gray-200">
                <table className="min-w-full text-sm">
                  <thead className="bg-gray-50 text-gray-600 uppercase text-xs tracking-wide">
                    <tr>
                      <th className="px-4 py-2 text-left">Date</th>
                      <th className="px-4 py-2 text-left">Agent</th>
                      <th className="px-4 py-2 text-right">Cost (USD)</th>
                      <th className="px-4 py-2 text-right">Tokens</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white">
                    {status.cost_log.map((entry) => (
                      <tr key={entry.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 text-gray-700">{entry.date}</td>
                        <td className="px-4 py-2 font-medium text-gray-900">{entry.agent_name}</td>
                        <td className="px-4 py-2 text-right text-gray-700">
                          ${(entry.estimated_cost_usd ?? 0).toFixed(4)}
                        </td>
                        <td className="px-4 py-2 text-right text-gray-600">
                          {entry.token_count.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
