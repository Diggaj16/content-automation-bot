/**
 * Catch-all proxy: forwards /api/proxy/** → FastAPI at BACKEND_URL/**
 * Runs server-side so it always uses 127.0.0.1 (no browser env-var issues).
 */
import { type NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8001";

async function handler(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const url = new URL(req.url);
  const target = `${BACKEND}/${path.join("/")}${url.search}`;

  const headers = new Headers(req.headers);
  headers.delete("host");

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

export const GET = handler;
export const POST = handler;
export const PATCH = handler;
export const DELETE = handler;
