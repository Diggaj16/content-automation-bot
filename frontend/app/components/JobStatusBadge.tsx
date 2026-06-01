"use client";

import type { JobState } from "../hooks/useJobStatus";

/** Formats a research/scoring/creation result dict into a short human-readable line. */
function summariseResult(result: Record<string, unknown> | null): string {
  if (!result) return "";
  const parts: string[] = [];

  // Research
  if (result.success !== undefined)
    parts.push(`${result.success} article${result.success !== 1 ? "s" : ""} stored`);
  if (result.skipped !== undefined && Number(result.skipped) > 0)
    parts.push(`${result.skipped} skipped`);

  // Scoring
  if (result.ideas_created !== undefined)
    parts.push(`${result.ideas_created} idea${result.ideas_created !== 1 ? "s" : ""} created`);

  // Creation
  if (result.drafts_created !== undefined)
    parts.push(`${result.drafts_created} draft${result.drafts_created !== 1 ? "s" : ""} created`);

  // Failures (only show if > 0)
  if (result.failures !== undefined && Number(result.failures) > 0)
    parts.push(`${result.failures} failed`);

  // Duration
  if (result.duration_seconds !== undefined)
    parts.push(`${Number(result.duration_seconds).toFixed(0)}s`);

  return parts.length ? parts.join(" · ") : "Done";
}

interface Props {
  state: JobState;
  onDismiss?: () => void;
}

export default function JobStatusBadge({ state, onDismiss }: Props) {
  if (state.phase === "idle") return null;

  const { phase, result, error, elapsed } = state;

  const base = "flex items-center gap-2 px-4 py-2 rounded-lg text-sm border";

  if (phase === "queued") {
    return (
      <div className={`${base} bg-gray-50 border-gray-200 text-gray-600`}>
        <span className="w-2 h-2 rounded-full bg-gray-400 animate-pulse" />
        Queued…
        {onDismiss && (
          <button onClick={onDismiss} className="ml-auto text-gray-400 hover:text-gray-600 text-xs">✕</button>
        )}
      </div>
    );
  }

  if (phase === "in_progress") {
    return (
      <div className={`${base} bg-blue-50 border-blue-200 text-blue-700`}>
        <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
        Running… {elapsed > 0 && <span className="text-blue-500">{elapsed}s</span>}
        {onDismiss && (
          <button onClick={onDismiss} className="ml-auto text-blue-400 hover:text-blue-600 text-xs">✕</button>
        )}
      </div>
    );
  }

  if (phase === "complete") {
    const summary = summariseResult(result);
    return (
      <div className={`${base} bg-green-50 border-green-200 text-green-700`}>
        <span className="text-green-500">✓</span>
        Done
        {summary && <span className="text-green-600">— {summary}</span>}
        {onDismiss && (
          <button onClick={onDismiss} className="ml-auto text-green-400 hover:text-green-600 text-xs">✕</button>
        )}
      </div>
    );
  }

  if (phase === "failed") {
    return (
      <div className={`${base} bg-red-50 border-red-200 text-red-700`}>
        <span className="text-red-500">✗</span>
        {error ?? "Job failed"}
        {onDismiss && (
          <button onClick={onDismiss} className="ml-auto text-red-400 hover:text-red-600 text-xs">✕</button>
        )}
      </div>
    );
  }

  return null;
}
