// Use the Next.js proxy so the browser always calls the same origin.
// /api/proxy/* is forwarded server-side to the FastAPI backend.
const API_BASE = "/api/proxy";

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

export async function getIdeas(status = "pending_approval") {
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

export interface DraftsResponse {
  data: Draft[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export async function getDrafts(status = "pending_approval", page = 1, limit = 50) {
  return apiFetch<DraftsResponse>(`/drafts?status=${status}&limit=${limit}&page=${page}`);
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

export interface JobStatusResponse {
  job_id: string;
  /** "queued" | "in_progress" | "complete" | "not_found" | "deferred" */
  status: string;
  result: Record<string, unknown> | null;
}

export async function getJobStatus(jobId: string) {
  return apiFetch<JobStatusResponse>(`/jobs/${jobId}`);
}

export async function triggerCreation(ideaIds: string[], contentType: string = "news_driven") {
  return apiFetch<{ job_id: string; status: string; agent: string; idea_count: number; content_type: string }>(
    "/trigger/creation",
    { method: "POST", body: JSON.stringify({ idea_ids: ideaIds, content_type: contentType }) }
  );
}

// --- Subscribers ---

export interface Subscriber {
  id: string;
  email: string;
  name: string | null;
  subscribed_date: string;
  source: string;
  active: boolean;
  unsubscribe_token: string | null;
  created_at: string;
}

export async function getSubscribers(active?: boolean) {
  const qs = active !== undefined ? `?active=${active}` : "";
  return apiFetch<Subscriber[]>(`/subscribers${qs}`);
}

export async function addSubscriber(data: { email: string; name?: string }) {
  return apiFetch<Subscriber>("/subscribers", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateSubscriber(
  id: string,
  data: { name?: string; active?: boolean }
) {
  return apiFetch<Subscriber>(`/subscribers/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteSubscriber(id: string) {
  return apiFetch<{ deleted: boolean; id: string }>(`/subscribers/${id}`, {
    method: "DELETE",
  });
}

// Types
export interface SourceArticle {
  id: string;
  url: string;
  title: string;
  source_name: string;
  publication_date: string | null;
  full_text: string;
  structured_summary: {
    story_narrative: string;
    key_data_points: string[];
    mechanism: string;
    implications: string;
    content_angles: string[];
  } | null;
  word_count: number;
  pre_score: number | null;
  vision_fallback_used: boolean;
  paywall_detected: boolean;
}

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
  source_article: SourceArticle | null;
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
  estimated_cost_usd: number;
  token_count: number;
}

// --- Knowledge Base ---

export interface KbFile {
  source_file: string;
  chunk_count: number;
  created_at: string;
}

export async function uploadKbFile(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/knowledge-base/upload`, {
    method: "POST",
    body: formData,
    // No Content-Type header — browser sets multipart boundary automatically
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload failed ${res.status}: ${text}`);
  }
  return res.json() as Promise<{ source_file: string; chunks_ingested: number }>;
}

export async function listKbFiles() {
  return apiFetch<KbFile[]>("/knowledge-base");
}

export async function deleteKbFile(sourceFile: string) {
  return apiFetch<{ deleted: boolean; source_file: string }>(
    `/knowledge-base/${encodeURIComponent(sourceFile)}`,
    { method: "DELETE" }
  );
}

// --- Orchestrator ---

export interface OrchestratorResponse {
  response: string;
  tools_used: string[];
  thread_id: string;
}

export async function orchestrate(message: string, threadId: string) {
  return apiFetch<OrchestratorResponse>("/orchestrate", {
    method: "POST",
    body: JSON.stringify({ message, thread_id: threadId }),
  });
}

// --- Generic table browser ---

export interface TableListResponse {
  table: string;
  rows: Record<string, unknown>[];
  count: number | null;
  limit: number;
  offset: number;
  columns: string[];      // column names from first row (excludes vector columns)
  default_sort: string;   // backend-recommended sort column for this table
}

export async function listTables() {
  return apiFetch<string[]>("/tables");
}

export async function getTableRows(
  tableName: string,
  opts: {
    limit?: number;
    offset?: number;
    orderBy?: string;
    orderDesc?: boolean;
    filterColumn?: string;
    filterValue?: string;
  } = {}
) {
  const params = new URLSearchParams();
  if (opts.limit !== undefined) params.set("limit", String(opts.limit));
  if (opts.offset !== undefined) params.set("offset", String(opts.offset));
  if (opts.orderBy) params.set("order_by", opts.orderBy);
  if (opts.orderDesc !== undefined) params.set("order_desc", String(opts.orderDesc));
  if (opts.filterColumn) params.set("filter_column", opts.filterColumn);
  if (opts.filterValue !== undefined) params.set("filter_value", opts.filterValue);
  const qs = params.toString();
  return apiFetch<TableListResponse>(`/tables/${tableName}${qs ? `?${qs}` : ""}`);
}

export async function getTableRow(tableName: string, rowId: string) {
  return apiFetch<Record<string, unknown>>(`/tables/${tableName}/${rowId}`);
}

export async function insertTableRow(tableName: string, payload: Record<string, unknown>) {
  return apiFetch<Record<string, unknown>>(`/tables/${tableName}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateTableRow(tableName: string, rowId: string, payload: Record<string, unknown>) {
  return apiFetch<Record<string, unknown>>(`/tables/${tableName}/${rowId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteTableRow(tableName: string, rowId: string) {
  return apiFetch<{ deleted: boolean; id: string }>(`/tables/${tableName}/${rowId}`, {
    method: "DELETE",
  });
}
