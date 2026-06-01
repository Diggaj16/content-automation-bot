/**
 * Lightweight localStorage-backed job tracker.
 * Persists across page navigation, tab switches, and browser refresh.
 * Every trigger button writes here; GlobalJobMonitor reads and polls.
 */

export interface JobRecord {
  job_id: string;
  agent: string;   // "research" | "scoring" | "creation" | etc.
  label: string;   // human-readable: "Research", "Scoring", "Creation (3 ideas)"
  status: "queued" | "in_progress" | "complete" | "failed";
  started_at: number;   // Date.now()
  finished_at?: number;
  result?: Record<string, unknown> | null;
}

const STORE_KEY = "pipeline_jobs";
const MAX_JOBS  = 20;
const MAX_AGE_MS = 4 * 60 * 60 * 1000; // keep last 4h

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
  const jobs = read().map(j => j.job_id === job_id ? { ...j, ...updates } : j);
  write(jobs);
}

/** All jobs still in progress. */
export function getActiveJobs(): JobRecord[] {
  return read().filter(j => j.status === "queued" || j.status === "in_progress");
}

/** Jobs from the last maxAgeMs milliseconds (active + recently finished). */
export function getRecentJobs(maxAgeMs = MAX_AGE_MS): JobRecord[] {
  const cutoff = Date.now() - maxAgeMs;
  return read().filter(j => j.started_at > cutoff);
}

/** Remove a specific job from the store. */
export function removeJob(job_id: string): void {
  write(read().filter(j => j.job_id !== job_id));
}
