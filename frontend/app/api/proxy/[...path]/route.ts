/**
 * Catch-all proxy: forwards /api/proxy/** → FastAPI at BACKEND_URL/**
 * Runs server-side so it always uses 127.0.0.1 (no browser env-var issues).
 *
 * Security: only whitelisted path prefixes are forwarded; all others return 403.
 */
import { type NextRequest, NextResponse } from "next/server";

const BACKEND      = process.env.BACKEND_URL      ?? "http://127.0.0.1:8000";
const BACKEND_KEY  = process.env.BACKEND_API_KEY  ?? "";

/**
 * First path-segment allowlist. Every legitimate frontend request maps to
 * one of these backend route prefixes.
 */
const ALLOWED_PREFIXES = new Set([
  "ideas",
  "drafts",
  "trigger",
  "jobs",
  "status",
  "tables",
  "subscribers",
  "knowledge-base",
  "orchestrate",
]);

async function handler(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;

  // Reject any path whose first segment is not in the allowlist
  const firstSegment = path[0] ?? "";
  if (!ALLOWED_PREFIXES.has(firstSegment)) {
    return new NextResponse(JSON.stringify({ detail: "Forbidden" }), {
      status: 403,
      headers: { "Content-Type": "application/json" },
    });
  }

  const url = new URL(req.url);
  const target = `${BACKEND}/${path.join("/")}${url.search}`;

  const headers = new Headers(req.headers);
  headers.delete("host");

  // Forward API key when configured
  if (BACKEND_KEY) {
    headers.set("X-Api-Key", BACKEND_KEY);
  }

  // Use ArrayBuffer for all non-GET/HEAD bodies so that binary content
  // (e.g. PDF uploads) is forwarded byte-for-byte without UTF-8 corruption.
  const body =
    req.method === "GET" || req.method === "HEAD"
      ? undefined
      : await req.arrayBuffer();

  const backendRes = await fetch(target, {
    method: req.method,
    headers,
    body: body ?? undefined,
  });

  const data = await backendRes.arrayBuffer();
  return new NextResponse(data, {
    status: backendRes.status,
    headers: { "Content-Type": backendRes.headers.get("Content-Type") ?? "application/json" },
  });
}

export const GET    = handler;
export const POST   = handler;
export const PATCH  = handler;
export const DELETE = handler;
