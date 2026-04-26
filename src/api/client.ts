// ---------------------------------------------------------------------------
// API client — fetch wrappers for the Vite middleware endpoints
// ---------------------------------------------------------------------------

import type {
  StatsResponse,
  ReelSearchResponse,
  ReelDetailResponse,
  ShotlistPdfsResponse,
  ShotlistTextResponse,
} from "../types";

const BASE = "/api";

/**
 * Structured API error. Server JSON bodies of the form
 * `{ error, reason?, detail?, gatewayStatus? }` populate the fields below;
 * plain-text bodies fall back to `detail` only.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly reason: string | null;
  readonly detail: string | null;
  readonly gatewayStatus: number | null;
  constructor(opts: {
    status: number;
    code?: string | null;
    reason?: string | null;
    detail?: string | null;
    gatewayStatus?: number | null;
    message?: string;
  }) {
    super(opts.message ?? opts.detail ?? opts.code ?? `API ${opts.status}`);
    this.name = "ApiError";
    this.status = opts.status;
    this.code = opts.code ?? null;
    this.reason = opts.reason ?? null;
    this.detail = opts.detail ?? null;
    this.gatewayStatus = opts.gatewayStatus ?? null;
  }
}

async function readError(res: Response): Promise<ApiError> {
  const text = await res.text().catch(() => "");
  try {
    const parsed = JSON.parse(text) as {
      error?: string;
      reason?: string;
      detail?: string;
      gatewayStatus?: number;
    };
    return new ApiError({
      status: res.status,
      code: parsed.error ?? null,
      reason: parsed.reason ?? null,
      detail: parsed.detail ?? null,
      gatewayStatus: parsed.gatewayStatus ?? null,
    });
  } catch {
    return new ApiError({ status: res.status, detail: text || `API ${res.status}` });
  }
}

/** Return auth header if a session token is stored. */
function authHeaders(): Record<string, string> {
  try {
    const token = globalThis.sessionStorage?.getItem("authToken");
    if (token) return { Authorization: `Bearer ${token}` };
  } catch {
    /* SSR / non-browser — ignore */
  }
  return {};
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) throw await readError(res);
  return res.json() as Promise<T>;
}

export function fetchStats(): Promise<StatsResponse> {
  return get<StatsResponse>("/stats");
}

export interface ReelSearchParams {
  q?: string;
  page?: number;
  limit?: number;
  has_transfer?: boolean;
  quality_bucket?: string;
  sort?: string;
  order?: "asc" | "desc";
}

export function searchReels(params: ReelSearchParams): Promise<ReelSearchResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.page) sp.set("page", String(params.page));
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.has_transfer) sp.set("has_transfer", "1");
  if (params.quality_bucket) sp.set("quality_bucket", params.quality_bucket);
  if (params.sort) sp.set("sort", params.sort);
  if (params.order) sp.set("order", params.order);
  return get<ReelSearchResponse>(`/reels?${sp.toString()}`);
}

export function fetchReelDetail(identifier: string): Promise<ReelDetailResponse> {
  return get<ReelDetailResponse>(`/reels/${encodeURIComponent(identifier)}`);
}

export function fetchShotlistPdfs(identifier: string): Promise<ShotlistPdfsResponse> {
  return get<ShotlistPdfsResponse>(`/reels/${encodeURIComponent(identifier)}/shotlist-pdfs`);
}

export function fetchShotlistText(identifier: string): Promise<ShotlistTextResponse> {
  return get<ShotlistTextResponse>(`/reels/${encodeURIComponent(identifier)}/shotlist-text`);
}

/** Get the URL for serving a shotlist PDF (legacy: same-origin only). */
export function shotlistPdfUrl(filename: string): string {
  return `${BASE}/shotlist-pdf/${encodeURIComponent(filename)}`;
}

// ---------------------------------------------------------------------------
// Session-based video and PDF access
//
// In monolithic mode the catalog API returns a same-origin URL (today's
// behavior). In split mode it returns an absolute URL pointing at the home
// gateway, plus an expiry timestamp the client uses to renew before seek.
// Either way the SPA just renders the returned URL — no branching needed
// in component code.
// ---------------------------------------------------------------------------

export interface VideoSession {
  mode: "monolithic" | "split";
  sessionId: string;
  streamUrl: string;
  /** Absolute UTC ms when the playback-start window expires; null in monolithic mode. */
  expiresAtMs: number | null;
}

export interface PdfSession {
  mode: "monolithic" | "split";
  pdfUrl: string;
  expiresAtMs: number | null;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await readError(res);
  return res.json() as Promise<T>;
}

/**
 * Request a playback-start session. Append `streamId` (a fresh UUID per seek)
 * to the returned `streamUrl` so the heartbeat / stop registry can find this
 * playback on either monolithic Express or the home gateway.
 */
export async function requestVideoSession(
  fileId: number,
  startSecs: number,
  streamId: string
): Promise<VideoSession> {
  const session = await postJson<VideoSession>("/video/sessions", { fileId, startSecs });
  return appendStreamParams(session, streamId);
}

/** Renew a video session (used when the playback-start window is about to lapse mid-seek). */
export async function renewVideoSession(
  sessionId: string,
  fileId: number,
  startSecs: number,
  streamId: string
): Promise<VideoSession> {
  const session = await postJson<VideoSession>(
    `/video/sessions/${encodeURIComponent(sessionId)}/renew`,
    { fileId, startSecs }
  );
  return appendStreamParams(session, streamId);
}

function appendStreamParams(session: VideoSession, streamId: string): VideoSession {
  const url = new URL(session.streamUrl, globalThis.location?.origin ?? "http://localhost");
  url.searchParams.set("streamId", streamId);
  // Same-origin URLs need the auth token in the query (video tags can't set headers).
  if (session.mode === "monolithic") {
    try {
      const token = globalThis.sessionStorage?.getItem("authToken");
      if (token) url.searchParams.set("token", token);
    } catch {
      /* SSR */
    }
  }
  // For monolithic same-origin URLs return relative form so dev proxy works.
  return {
    ...session,
    streamUrl: session.mode === "monolithic" ? `${url.pathname}${url.search}` : url.toString(),
  };
}

/** Request a PDF session. Returns a URL the PDF viewer can load directly. */
export async function requestPdfSession(filename: string): Promise<PdfSession> {
  return postJson<PdfSession>("/pdf/sessions", { filename });
}

/** Best-effort gateway availability check (used to disable buttons in split mode). */
export async function fetchGatewayStatus(): Promise<{
  mode: "monolithic" | "split";
  available: boolean;
}> {
  return get<{ mode: "monolithic" | "split"; available: boolean }>("/gateway/status");
}

// ---------------------------------------------------------------------------
// Heartbeat / stop targets
//
// Monolithic mode: hits same-origin /api/video/heartbeat.
// Split mode: hits the home gateway directly (CORS allows it).
// The component passes the gateway origin parsed from the streamUrl.
// ---------------------------------------------------------------------------

function originFromStreamUrl(streamUrl: string): string {
  try {
    const u = new URL(streamUrl, globalThis.location?.origin ?? "http://localhost");
    // Same-origin streams keep using /api/...
    if (!streamUrl.startsWith("http")) return BASE + "/video";
    return `${u.origin}/stream`;
  } catch {
    return BASE + "/video";
  }
}

/** Heartbeat — call every few seconds while a stream is active */
export async function videoHeartbeat(streamUrl: string, streamId: string): Promise<void> {
  const base = originFromStreamUrl(streamUrl);
  await fetch(`${base}/heartbeat?streamId=${encodeURIComponent(streamId)}`, {
    headers: authHeaders(),
  });
}

/** Explicit stop — call when the player unmounts or seeks away */
export async function videoStop(streamUrl: string, streamId: string): Promise<void> {
  const base = originFromStreamUrl(streamUrl);
  await fetch(`${base}/stop?streamId=${encodeURIComponent(streamId)}`, {
    method: "POST",
    headers: authHeaders(),
  });
}
