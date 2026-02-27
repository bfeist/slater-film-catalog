// ---------------------------------------------------------------------------
// API client — fetch wrappers for the Vite middleware endpoints
// ---------------------------------------------------------------------------

import type {
  StatsResponse,
  PrefixCount,
  ReelSearchResponse,
  ReelDetailResponse,
  ShotlistPdfsResponse,
} from "../types";

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export function fetchStats(): Promise<StatsResponse> {
  return get<StatsResponse>("/stats");
}

export function fetchPrefixes(): Promise<PrefixCount[]> {
  return get<PrefixCount[]>("/prefixes");
}

export interface ReelSearchParams {
  q?: string;
  prefix?: string;
  page?: number;
  limit?: number;
  has_transfer?: boolean;
}

export function searchReels(params: ReelSearchParams): Promise<ReelSearchResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.prefix) sp.set("prefix", params.prefix);
  if (params.page) sp.set("page", String(params.page));
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.has_transfer) sp.set("has_transfer", "1");
  return get<ReelSearchResponse>(`/reels?${sp.toString()}`);
}

export function fetchReelDetail(identifier: string): Promise<ReelDetailResponse> {
  return get<ReelDetailResponse>(`/reels/${encodeURIComponent(identifier)}`);
}

export function fetchShotlistPdfs(identifier: string): Promise<ShotlistPdfsResponse> {
  return get<ShotlistPdfsResponse>(`/reels/${encodeURIComponent(identifier)}/shotlist-pdfs`);
}

/** Get the URL for serving a shotlist PDF */
export function shotlistPdfUrl(filename: string): string {
  return `${BASE}/shotlist-pdf/${encodeURIComponent(filename)}`;
}

/** Get the streaming URL for a given file ID, optionally starting at a seek position */
export function videoStreamUrl(fileId: number, startSecs?: number): string {
  const base = `${BASE}/video/${fileId}/stream`;
  if (startSecs && startSecs > 0) {
    return `${base}?start=${startSecs.toFixed(1)}`;
  }
  return base;
}
