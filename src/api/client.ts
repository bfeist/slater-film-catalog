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
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
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
}

export function searchReels(params: ReelSearchParams): Promise<ReelSearchResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.page) sp.set("page", String(params.page));
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.has_transfer) sp.set("has_transfer", "1");
  if (params.quality_bucket) sp.set("quality_bucket", params.quality_bucket);
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

/** Get the URL for serving a shotlist PDF */
export function shotlistPdfUrl(filename: string): string {
  return `${BASE}/shotlist-pdf/${encodeURIComponent(filename)}`;
}

/** Get the streaming URL for a given file ID with an explicit streamId for heartbeat tracking */
export function videoStreamUrl(fileId: number, streamId: string, startSecs?: number): string {
  const base = `${BASE}/video/${fileId}/stream`;
  const params = new URLSearchParams({ streamId });
  if (startSecs && startSecs > 0) params.set("start", startSecs.toFixed(1));
  return `${base}?${params.toString()}`;
}

/** Heartbeat — call every few seconds while a stream is active */
export async function videoHeartbeat(streamId: string): Promise<void> {
  await fetch(`${BASE}/video/heartbeat?streamId=${encodeURIComponent(streamId)}`);
}

/** Explicit stop — call when the player unmounts or seeks away from a stream */
export async function videoStop(streamId: string): Promise<void> {
  await fetch(`${BASE}/video/stop?streamId=${encodeURIComponent(streamId)}`, { method: "POST" });
}
