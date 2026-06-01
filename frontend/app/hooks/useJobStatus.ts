"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { getJobStatus, type JobStatusResponse } from "../lib/api";

export type JobPhase = "idle" | "queued" | "in_progress" | "complete" | "failed";

export interface JobState {
  phase: JobPhase;
  result: Record<string, unknown> | null;
  error: string | null;
  /** Elapsed seconds since the job was enqueued (updated while running) */
  elapsed: number;
}

const TERMINAL_STATUSES = new Set(["complete", "not_found"]);
const POLL_MS = 2000;

/**
 * Poll a job's status every 2 seconds until it completes or fails.
 *
 * Usage:
 *   const { start, state, reset } = useJobStatus();
 *   // trigger something, get job_id back, then:
 *   start(job_id);
 */
export function useJobStatus() {
  const [state, setState] = useState<JobState>({
    phase: "idle",
    result: null,
    error: null,
    elapsed: 0,
  });

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);
  const jobIdRef = useRef<string | null>(null);

  const stop = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    stop();
    jobIdRef.current = null;
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
      // network blip — keep polling, don't fail immediately
      setState((prev) => ({ ...prev, elapsed }));
      return;
    }

    if (res.status === "complete") {
      stop();
      setState({ phase: "complete", result: res.result, error: null, elapsed });
    } else if (res.status === "not_found") {
      stop();
      setState({ phase: "failed", result: null, error: "Job not found", elapsed });
    } else if (res.status === "in_progress") {
      setState({ phase: "in_progress", result: null, error: null, elapsed });
    } else {
      // queued / deferred
      setState({ phase: "queued", result: null, error: null, elapsed });
    }
  }, [stop]);

  const start = useCallback(
    (jobId: string) => {
      stop();
      jobIdRef.current = jobId;
      startTimeRef.current = Date.now();
      setState({ phase: "queued", result: null, error: null, elapsed: 0 });
      // Poll immediately, then every POLL_MS
      void poll();
      intervalRef.current = setInterval(poll, POLL_MS);
    },
    [stop, poll]
  );

  // Cleanup on unmount
  useEffect(() => () => stop(), [stop]);

  return { start, reset, state };
}
