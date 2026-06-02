// frontend/app/components/GlobalJobMonitor.tsx
"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { getJobStatus } from "../lib/api";
import {
  getActiveJobs,
  getRecentJobs,
  updateJob,
  removeJob,
  type JobRecord,
} from "../lib/jobStore";

const POLL_MS            = 2000;
const SHOW_AFTER_DONE_MS = 60_000;       // keep completed jobs visible for 60s
const JOB_TIMEOUT_MS     = 30 * 60_000; // mark stuck queued/in_progress as failed after 30 min

function elapsed(job: JobRecord): number {
  const end = job.finished_at ?? Date.now();
  return Math.round((end - job.started_at) / 1000);
}

function summarise(result: Record<string, unknown> | null | undefined): string {
  if (!result) return "";
  const parts: string[] = [];
  if (result.success !== undefined)       parts.push(`${result.success} stored`);
  if (result.skipped !== undefined && Number(result.skipped) > 0)
                                          parts.push(`${result.skipped} skipped`);
  if (result.ideas_created !== undefined) parts.push(`${result.ideas_created} ideas`);
  if (result.drafts_created !== undefined)parts.push(`${result.drafts_created} drafts`);
  if (result.failures !== undefined && Number(result.failures) > 0)
                                          parts.push(`${result.failures} failed`);
  if (result.duration_seconds !== undefined)
                                          parts.push(`${Number(result.duration_seconds).toFixed(0)}s`);
  return parts.join(" · ");
}

export default function GlobalJobMonitor() {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const intervalRef  = useRef<ReturnType<typeof setInterval> | null>(null);
  const tickingRef   = useRef(false); // guard against concurrent tick() calls
  const mountedRef   = useRef(true);

  // Reload from localStorage and poll active jobs
  const tick = useCallback(async () => {
    // Skip this tick if the previous one is still in flight
    if (tickingRef.current) return;
    tickingRef.current = true;

    try {
      const now    = Date.now();
      const active = getActiveJobs();

      // Expire stuck jobs that have been active longer than JOB_TIMEOUT_MS
      for (const job of active) {
        if (now - job.started_at > JOB_TIMEOUT_MS) {
          updateJob(job.job_id, { status: "failed", finished_at: now });
        }
      }

      // Poll jobs that are still active after the timeout check
      await Promise.all(
        getActiveJobs().map(async job => {
          try {
            const res = await getJobStatus(job.job_id);
            if (res.status === "complete") {
              updateJob(job.job_id, {
                status: "complete",
                finished_at: Date.now(),
                result: res.result ?? undefined,
              });
            } else if (res.status === "not_found") {
              updateJob(job.job_id, { status: "failed", finished_at: Date.now() });
            } else if (res.status === "in_progress") {
              updateJob(job.job_id, { status: "in_progress" });
            }
          } catch {
            // network blip — leave as-is
          }
        })
      );

      // Auto-remove completed/failed jobs older than SHOW_AFTER_DONE_MS
      getRecentJobs(SHOW_AFTER_DONE_MS)
        .filter(j => (j.status === "complete" || j.status === "failed")
                 && j.finished_at
                 && Date.now() - j.finished_at > SHOW_AFTER_DONE_MS)
        .forEach(j => removeJob(j.job_id));

      if (mountedRef.current) {
        setJobs(getRecentJobs(SHOW_AFTER_DONE_MS));
      }
    } finally {
      tickingRef.current = false;
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void tick();
    intervalRef.current = setInterval(tick, POLL_MS);
    return () => {
      mountedRef.current = false;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [tick]);

  if (jobs.length === 0) return null;

  return (
    <div className="px-3 py-2 border-t border-gray-100 space-y-1.5">
      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider px-1">
        Pipeline
      </p>
      {jobs.map(job => (
        <div key={job.job_id} className="flex items-start gap-1.5 group">
          {/* Status dot */}
          <span className={`mt-1 flex-shrink-0 w-1.5 h-1.5 rounded-full ${
            job.status === "in_progress" ? "bg-blue-500 animate-pulse" :
            job.status === "queued"      ? "bg-gray-400 animate-pulse" :
            job.status === "complete"    ? "bg-green-500" :
                                           "bg-red-400"
          }`} />

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-1">
              <span className="text-xs font-medium text-gray-700 truncate">
                {job.label}
              </span>
              <button
                onClick={() => {
                  removeJob(job.job_id);
                  setJobs(prev => prev.filter(j => j.job_id !== job.job_id));
                }}
                className="opacity-0 group-hover:opacity-100 text-gray-300 hover:text-gray-500 text-[10px] flex-shrink-0"
              >
                ✕
              </button>
            </div>
            <p className="text-[10px] text-gray-500 truncate">
              {job.status === "queued"      && "Queued…"}
              {job.status === "in_progress" && `Running… ${elapsed(job)}s`}
              {job.status === "complete"    && (summarise(job.result) || `Done · ${elapsed(job)}s`)}
              {job.status === "failed"      && "Failed"}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
