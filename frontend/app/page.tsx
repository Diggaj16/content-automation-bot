"use client";

import { useState, useEffect } from "react";
import {
  getStatus,
  triggerResearch,
  triggerScoring,
  type RunLog,
  type CostLog,
} from "./lib/api";

export default function DashboardPage() {
  const [status, setStatus] = useState<{
    recent_runs: RunLog[];
    cost_log: CostLog[];
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState<string | null>(null);
  const [triggeringScore, setTriggeringScore] = useState(false);
  const [triggerScoreMsg, setTriggerScoreMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      setStatus(await getStatus());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleTrigger = async () => {
    setTriggering(true);
    setTriggerMsg(null);
    try {
      const r = await triggerResearch();
      setTriggerMsg(`Research job enqueued — job_id: ${r.job_id ?? "n/a"}`);
    } catch (e: unknown) {
      setTriggerMsg(
        e instanceof Error ? `Error: ${e.message}` : "Failed to trigger"
      );
    } finally {
      setTriggering(false);
    }
  };

  const handleTriggerScoring = async () => {
    setTriggeringScore(true); setTriggerScoreMsg(null);
    try {
      const r = await triggerScoring();
      setTriggerScoreMsg(`Scoring job enqueued — job_id: ${r.job_id ?? "n/a"}`);
    } catch (e: unknown) {
      setTriggerScoreMsg(e instanceof Error ? `Error: ${e.message}` : "Failed");
    } finally { setTriggeringScore(false); }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchStatus}
            disabled={loading}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {loading ? "Loading..." : "Refresh"}
          </button>
          <button
            onClick={handleTrigger}
            disabled={triggering}
            className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {triggering ? "Triggering..." : "Trigger Research"}
          </button>
          <button onClick={handleTriggerScoring} disabled={triggeringScore}
            className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded">
            {triggeringScore ? "Enqueueing…" : "Trigger Scoring"}
          </button>
        </div>
      </div>

      {triggerScoreMsg && (
        <div
          className={`px-4 py-3 rounded-md text-sm ${
            triggerScoreMsg.startsWith("Error")
              ? "bg-red-50 text-red-700 border border-red-200"
              : "bg-green-50 text-green-700 border border-green-200"
          }`}
        >
          {triggerScoreMsg}
        </div>
      )}

      {triggerMsg && (
        <div
          className={`px-4 py-3 rounded-md text-sm ${
            triggerMsg.startsWith("Error")
              ? "bg-red-50 text-red-700 border border-red-200"
              : "bg-green-50 text-green-700 border border-green-200"
          }`}
        >
          {triggerMsg}
        </div>
      )}

      {error && (
        <div className="px-4 py-3 rounded-md text-sm bg-red-50 text-red-700 border border-red-200">
          {error}
        </div>
      )}

      {loading && !status && (
        <div className="text-sm text-gray-500">Loading status...</div>
      )}

      {status && (
        <>
          {/* Recent Runs Table */}
          <section>
            <h2 className="text-lg font-medium text-gray-800 mb-3">
              Recent Agent Runs
            </h2>
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
                      <th className="px-4 py-2 text-right">Cost (USD)</th>
                      <th className="px-4 py-2 text-left">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white">
                    {status.recent_runs.map((run) => (
                      <tr key={run.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 font-medium text-gray-900">
                          {run.agent_name}
                        </td>
                        <td className="px-4 py-2 text-gray-600">
                          {run.trigger_type}
                        </td>
                        <td className="px-4 py-2 text-right text-gray-700">
                          {run.processed_count}
                        </td>
                        <td className="px-4 py-2 text-right text-green-600">
                          {run.success_count}
                        </td>
                        <td className="px-4 py-2 text-right text-red-500">
                          {run.failure_count}
                        </td>
                        <td className="px-4 py-2 text-right text-gray-600">
                          {run.duration_seconds.toFixed(1)}
                        </td>
                        <td className="px-4 py-2 text-right text-gray-600">
                          {run.token_cost?.total_usd != null
                            ? `$${run.token_cost.total_usd.toFixed(4)}`
                            : "—"}
                        </td>
                        <td className="px-4 py-2 text-gray-500 text-xs">
                          {new Date(run.created_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Cost Log Table */}
          <section>
            <h2 className="text-lg font-medium text-gray-800 mb-3">
              Cost Log
            </h2>
            {status.cost_log.length === 0 ? (
              <p className="text-sm text-gray-500">No cost records yet.</p>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-gray-200">
                <table className="min-w-full text-sm">
                  <thead className="bg-gray-50 text-gray-600 uppercase text-xs tracking-wide">
                    <tr>
                      <th className="px-4 py-2 text-left">Date</th>
                      <th className="px-4 py-2 text-left">Agent</th>
                      <th className="px-4 py-2 text-right">Total USD</th>
                      <th className="px-4 py-2 text-right">Tokens</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white">
                    {status.cost_log.map((entry) => (
                      <tr key={entry.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 text-gray-700">
                          {entry.date}
                        </td>
                        <td className="px-4 py-2 font-medium text-gray-900">
                          {entry.agent_name}
                        </td>
                        <td className="px-4 py-2 text-right text-gray-700">
                          ${entry.total_usd.toFixed(4)}
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
