// frontend/app/hooks/useJobStatus.ts
"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { getJobStatus, type JobStatusResponse } from "../lib/api";
import { saveJob, updateJob, type JobRecord } from "../lib/jobStore";

export type JobPhase = "idle" | "queued" | "in_progress" | "complete" | "failed";

export interface JobState {
  phase: JobPhase;
  result: Record<string, unknown> | null;
  error: string | null;
  elapsed: number;
}

const POLL_MS = 2000;

export function useJobStatus() {
  const [state, setState] = useState<JobState>({
    phase: "idle",
    result: null,
    error: null,
    elapsed: 0,
  });

  const intervalRef   = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef  = useRef<number>(0);
  const jobIdRef      = useRef<string | null>(null);
  const metaRef       = useRef<{ agent: string; label: string } | null>(null);

  const stop = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    stop();
    jobIdRef.current = null;
    metaRef.current = null;
    setState({ phase: "idle", result: null, error: null, elapsed: 0 });
  }, [stop]);

  const poll = useCallback(async () => {
    const jobId = jobIdRef.current;
    if (!jobId) return;
    const elapsed = Math.round((Date.now() - startTimeRef.current) / 1000);

    let res: JobStatusResponse;
    try {
      res = await getJobStatus(jobId);
    } catch {
      setState(prev => ({ ...prev, elapsed }));
      return;
    }

    const phase: JobPhase =
      res.status === "complete"   ? "complete"    :
      res.status === "not_found"  ? "failed"      :
      res.status === "in_progress"? "in_progress" : "queued";

    // Sync to global store so GlobalJobMonitor reflects the latest state
    if (metaRef.current) {
      updateJob(jobId, {
        status: phase === "failed" ? "failed" : res.status as JobRecord["status"],
        ...(phase === "complete" || phase === "failed" ? { finished_at: Date.now(), result: res.result } : {}),
      });
    }

    if (phase === "complete") {
      stop();
      setState({ phase: "complete", result: res.result, error: null, elapsed });
    } else if (phase === "failed") {
      stop();
      setState({ phase: "failed", result: null, error: "Job not found", elapsed });
    } else {
      setState({ phase, result: null, error: null, elapsed });
    }
  }, [stop]);

  /**
   * Start tracking a job. agent + label are used by GlobalJobMonitor
   * to show meaningful status in the sidebar.
   */
  const start = useCallback(
    (jobId: string, agent = "unknown", label = "Job") => {
      stop();
      jobIdRef.current   = jobId;
      metaRef.current    = { agent, label };
      startTimeRef.current = Date.now();
      setState({ phase: "queued", result: null, error: null, elapsed: 0 });

      // Persist to store so GlobalJobMonitor picks it up on any page
      saveJob({ job_id: jobId, agent, label, status: "queued", started_at: Date.now() });

      void poll();
      intervalRef.current = setInterval(poll, POLL_MS);
    },
    [stop, poll]
  );

  useEffect(() => () => stop(), [stop]);

  return { start, reset, state };
}
