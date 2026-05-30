const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export async function getIdeas(status = "pending") {
  return apiFetch<Idea[]>(`/ideas?status=${status}&limit=50`);
}

export async function approveIdea(
  id: string,
  data: { approval_status: string; edited_angle?: string }
) {
  return apiFetch<Idea>(`/ideas/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function getDrafts(status = "pending") {
  return apiFetch<Draft[]>(`/drafts?status=${status}&limit=50`);
}

export async function approveDraft(
  id: string,
  data: {
    approval_status: string;
    content_text?: string;
    scheduled_at?: string;
  }
) {
  return apiFetch<Draft>(`/drafts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function getStatus() {
  return apiFetch<{ recent_runs: RunLog[]; cost_log: CostLog[] }>(
    "/status?limit=10"
  );
}

export async function triggerResearch() {
  return apiFetch<{ job_id: string; status: string; agent: string }>(
    "/trigger/research",
    { method: "POST" }
  );
}

export async function triggerScoring() {
  return apiFetch<{ job_id: string; status: string; agent: string }>("/trigger/scoring", { method: "POST" });
}

export async function triggerCreation(ideaIds: string[]) {
  return apiFetch<{ job_id: string; status: string; agent: string; idea_count: number }>(
    "/trigger/creation",
    { method: "POST", body: JSON.stringify({ idea_ids: ideaIds }) }
  );
}

// Types
export interface Idea {
  id: string;
  platform: string;
  angle: string;
  edited_angle: string | null;
  agent_reasoning: string | null;
  score: number | null;
  recent_coverage_flag: boolean;
  approval_status: string;
  source_article_date: string | null;
  created_at: string;
}

export interface Draft {
  id: string;
  platform: string;
  content_text: string;
  agent_reasoning: string | null;
  finance_flags: Array<{
    flag_type: string;
    content: string;
    context: string;
  }> | null;
  approval_status: string;
  scheduled_at: string | null;
  source_idea_id: string | null;
  created_at: string;
}

export interface RunLog {
  id: string;
  agent_name: string;
  trigger_type: string;
  processed_count: number;
  success_count: number;
  failure_count: number;
  duration_seconds: number;
  token_cost: { total_usd?: number } | null;
  created_at: string;
}

export interface CostLog {
  id: string;
  agent_name: string;
  date: string;
  total_usd: number;
  token_count: number;
}
