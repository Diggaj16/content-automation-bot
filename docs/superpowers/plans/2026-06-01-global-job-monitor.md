# Global Job Status Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Job status (queued/running/done) persists across page navigation and tab switches so the user always sees what the pipeline is doing even after clicking away.

**Architecture:** A `jobStore.ts` module persists job records in `localStorage`. The existing `useJobStatus` hook writes to the store when a job starts. A new `GlobalJobMonitor` component (mounted once in the root layout sidebar) reads the store, polls active jobs every 2s, and shows live status badges. No backend changes needed.

**Tech Stack:** Next.js 16, React 19, TypeScript, localStorage

---

## File Map

- Create: `frontend/app/lib/jobStore.ts` — localStorage CRUD for job records
- Create: `frontend/app/components/GlobalJobMonitor.tsx` — sidebar live-status panel
- Modify: `frontend/app/hooks/useJobStatus.ts` — call `saveJob` on `start()`
- Modify: `frontend/app/layout.tsx` — mount `GlobalJobMonitor` in sidebar
- Modify: `frontend/app/page.tsx` — write to jobStore when triggering research/scoring
- Modify: `frontend/app/ideas/page.tsx` — write to jobStore when sending to creation

---

### Task 1: Create `jobStore.ts`

**Files:**
- Create: `frontend/app/lib/jobStore.ts`

- [ ] **Step 1: Create the file**

```typescript
// frontend/app/lib/jobStore.ts
/**
 * localStorage-backed job tracker.
 * Persists across page navigation, tab switches, and browser refresh.
 */

export interface JobRecord {
  job_id: string;
  agent: string;   // "research" | "scoring" | "creation"
  label: string;   // human-readable: "Research", "Scoring", "Creation (3 ideas)"
  status: "queued" | "in_progress" | "complete" | "failed";
  started_at: number;    // Date.now()
  finished_at?: number;
  result?: Record<string, unknown> | null;
}

const STORE_KEY = "pipeline_jobs";
const MAX_JOBS  = 20;

function read(): JobRecord[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(STORE_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function write(jobs: JobRecord[]): void {
  localStorage.setItem(STORE_KEY, JSON.stringify(jobs.slice(0, MAX_JOBS)));
}

/** Add or replace a job record (keyed on job_id). */
export function saveJob(job: JobRecord): void {
  const jobs = read().filter(j => j.job_id !== job.job_id);
  jobs.unshift(job);
  write(jobs);
}

/** Merge partial updates into an existing record. */
export function updateJob(job_id: string, updates: Partial<JobRecord>): void {
  write(read().map(j => j.job_id === job_id ? { ...j, ...updates } : j));
}

/** Jobs still in progress (queued or in_progress). */
export function getActiveJobs(): JobRecord[] {
  return read().filter(j => j.status === "queued" || j.status === "in_progress");
}

/**
 * Jobs from the last maxAgeMs milliseconds.
 * Default 4 hours — covers a full working session.
 */
export function getRecentJobs(maxAgeMs = 4 * 60 * 60 * 1000): JobRecord[] {
  const cutoff = Date.now() - maxAgeMs;
  return read().filter(j => j.started_at > cutoff);
}

/** Remove a job (called after the user dismisses a completed badge). */
export function removeJob(job_id: string): void {
  write(read().filter(j => j.job_id !== job_id));
}
```

- [ ] **Step 2: Verify TypeScript compiles (no test needed — pure utility)**

```powershell
cd D:\Intern\content-automation-bot\frontend
npx tsc --noEmit 2>&1 | Select-Object -Last 10
```
Expected: no errors

- [ ] **Step 3: Commit**

```powershell
git add frontend/app/lib/jobStore.ts
git commit -m "feat: add localStorage-backed job store for cross-tab persistence"
```

---

### Task 2: Update `useJobStatus` to write to the store

**Files:**
- Modify: `frontend/app/hooks/useJobStatus.ts`

The hook already polls a single job. We just need it to also call `saveJob` when started and `updateJob` as status changes, so the `GlobalJobMonitor` can pick it up.

- [ ] **Step 1: Update `useJobStatus.ts`**

Replace the entire file with:

```typescript
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
```

- [ ] **Step 2: Verify TypeScript compiles**

```powershell
npx tsc --noEmit 2>&1 | Select-Object -Last 10
```
Expected: no errors

- [ ] **Step 3: Commit**

```powershell
git add frontend/app/hooks/useJobStatus.ts
git commit -m "feat: useJobStatus writes to jobStore so GlobalJobMonitor tracks all jobs"
```

---

### Task 3: Update trigger buttons to pass agent/label to `start()`

**Files:**
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/ideas/page.tsx`

- [ ] **Step 1: Update Dashboard `page.tsx`**

In `frontend/app/page.tsx`, find:
```typescript
      const r = await triggerResearch();
      if (r.job_id) research.start(r.job_id);
```
Replace with:
```typescript
      const r = await triggerResearch();
      if (r.job_id) research.start(r.job_id, "research", "Research");
```

Find:
```typescript
      const r = await triggerScoring();
      if (r.job_id) scoring.start(r.job_id);
```
Replace with:
```typescript
      const r = await triggerScoring();
      if (r.job_id) scoring.start(r.job_id, "scoring", "Scoring");
```

- [ ] **Step 2: Update Ideas `page.tsx`**

In `frontend/app/ideas/page.tsx`, find `useJobStatus` usage. The ideas page doesn't use `useJobStatus` yet — it uses a local state pattern. Add the hook and wire it up.

At top of `IdeasPage`, add:
```typescript
  const creationJob = useJobStatus();
```

Add import at top of file:
```typescript
import { useJobStatus } from "../hooks/useJobStatus";
```

In `handleSendToCreation`, after getting the result:
```typescript
  const handleSendToCreation = async () => {
    setSendingToCreation(true);
    setCreationMsg(null);
    try {
      const r = await triggerCreation(approvedIds, contentType);
      if (r.job_id) {
        creationJob.start(
          r.job_id,
          "creation",
          `Creation (${approvedIds.length} idea${approvedIds.length !== 1 ? "s" : ""})`
        );
      }
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
```

- [ ] **Step 3: Verify TypeScript**

```powershell
npx tsc --noEmit 2>&1 | Select-Object -Last 10
```

- [ ] **Step 4: Commit**

```powershell
git add frontend/app/page.tsx frontend/app/ideas/page.tsx
git commit -m "feat: pass agent/label to useJobStatus.start() for GlobalJobMonitor display"
```

---

### Task 4: Create `GlobalJobMonitor` component

**Files:**
- Create: `frontend/app/components/GlobalJobMonitor.tsx`

- [ ] **Step 1: Create the component**

```typescript
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

const POLL_MS    = 2000;
const SHOW_AFTER_DONE_MS = 60_000; // keep completed jobs visible for 60s

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
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Reload from localStorage and poll active jobs
  const tick = useCallback(async () => {
    const active  = getActiveJobs();
    const recent  = getRecentJobs(SHOW_AFTER_DONE_MS);

    // Poll each active job
    await Promise.all(
      active.map(async job => {
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

    // Auto-remove completed jobs older than SHOW_AFTER_DONE_MS
    getRecentJobs(SHOW_AFTER_DONE_MS)
      .filter(j => (j.status === "complete" || j.status === "failed")
               && j.finished_at
               && Date.now() - j.finished_at > SHOW_AFTER_DONE_MS)
      .forEach(j => removeJob(j.job_id));

    setJobs(getRecentJobs(SHOW_AFTER_DONE_MS));
  }, []);

  useEffect(() => {
    void tick();
    intervalRef.current = setInterval(tick, POLL_MS);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
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
                onClick={() => removeJob(job.job_id)}
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
```

- [ ] **Step 2: Verify TypeScript**

```powershell
npx tsc --noEmit 2>&1 | Select-Object -Last 10
```
Expected: no errors

- [ ] **Step 3: Commit**

```powershell
git add frontend/app/components/GlobalJobMonitor.tsx
git commit -m "feat: add GlobalJobMonitor sidebar component for cross-tab job status"
```

---

### Task 5: Mount `GlobalJobMonitor` in the layout

**Files:**
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Add import and mount**

At the top of `frontend/app/layout.tsx`, add:
```typescript
import GlobalJobMonitor from "./components/GlobalJobMonitor";
```

Inside the `<aside>` element, add `GlobalJobMonitor` after the `<nav>` closing tag:
```tsx
          {/* Sidebar */}
          <aside className="w-56 bg-white border-r border-gray-200 flex-shrink-0 overflow-y-auto flex flex-col">
            <div className="px-4 py-4 border-b border-gray-100">
              <Link href="/" className="font-semibold text-gray-900 text-sm">
                Content Automation
              </Link>
            </div>
            <nav className="py-2 flex-1">
              {NAV_SECTIONS.map((section) => (
                /* ... existing nav links ... */
              ))}
            </nav>
            {/* Live pipeline status — persists across page navigation */}
            <GlobalJobMonitor />
          </aside>
```

Note: also add `flex flex-col` to the `<aside>` className so the monitor sticks to the bottom of the nav.

- [ ] **Step 2: Verify TypeScript and dev server**

```powershell
npx tsc --noEmit 2>&1 | Select-Object -Last 5
```

- [ ] **Step 3: Manual test**
1. Open http://localhost:3000
2. Click "Trigger Research" — badge appears in sidebar at the bottom
3. Navigate to `/ideas` page — badge still visible and updating
4. Navigate back to Dashboard — badge still there
5. When complete: shows "Research · 5 stored · 3 skipped · 42s"
6. After 60 seconds: disappears automatically

- [ ] **Step 4: Commit**

```powershell
git add frontend/app/layout.tsx
git commit -m "feat: mount GlobalJobMonitor in sidebar for persistent cross-tab job status"
```
