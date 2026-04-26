// ---------------------------------------------------------------------------
// gatewayClient.ts — HTTP client used by the catalog API (split mode) to talk
// to the home video gateway. Uses a shared bearer secret. Caches /healthz so
// degraded UX shows up quickly instead of every request blocking on the home
// network.
// ---------------------------------------------------------------------------

import { config } from "./config.js";
import { ConsoleLogger } from "./logger.js";

export interface VideoSessionResponse {
  sessionId: string;
  token: string;
  expiresAtMs: number;
  releaseVersion: string;
}

export interface PdfTokenResponse {
  token: string;
  expiresAtMs: number;
  releaseVersion: string;
}

export interface GatewayHealth {
  ok: boolean;
  releaseVersion: string | null;
  checkedAtMs: number;
  /** Why the gateway is unhealthy (when ok=false). */
  reason?: "timeout" | "unreachable" | "http_error" | null;
  /** HTTP status if the gateway responded with non-2xx. */
  status?: number | null;
  /** Free-form detail from the gateway response or fetch error. */
  detail?: string | null;
}

/** Structured error thrown by mintVideoSession / renewVideoSession / mintPdfToken. */
export class GatewayError extends Error {
  constructor(
    public readonly reason: "timeout" | "unreachable" | "http_error",
    public readonly status: number | null,
    public readonly detail: string
  ) {
    super(`gateway ${reason}${status ? " " + status : ""}: ${detail}`);
    this.name = "GatewayError";
  }
}

let cachedHealth: GatewayHealth | null = null;

function authHeaders(): Record<string, string> {
  if (!config.gatewaySharedSecret) {
    throw new Error("HOME_GATEWAY_SHARED_SECRET is not configured on the catalog API");
  }
  return {
    Authorization: `Bearer ${config.gatewaySharedSecret}`,
    "Content-Type": "application/json",
    "X-Release-Version": config.releaseVersion,
  };
}

async function gatewayFetch(pathname: string, init: RequestInit = {}): Promise<Response> {
  if (!config.gatewayBaseUrl) {
    throw new Error("HOME_GATEWAY_BASE_URL is not configured");
  }
  const url = `${config.gatewayBaseUrl}${pathname}`;
  // 5s timeout — anything slower means home is effectively down.
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 5000);
  try {
    return await fetch(url, {
      ...init,
      signal: ctrl.signal,
      headers: { ...(init.headers as Record<string, string> | undefined), ...authHeaders() },
    });
  } finally {
    clearTimeout(timer);
  }
}

export async function checkGatewayHealth(force = false): Promise<GatewayHealth> {
  const now = Date.now();
  if (
    !force &&
    cachedHealth &&
    now - cachedHealth.checkedAtMs < config.gatewayHealthTtlSecs * 1000
  ) {
    return cachedHealth;
  }
  try {
    const r = await gatewayFetch("/healthz");
    if (!r.ok) {
      const body = await r.text().catch(() => "");
      cachedHealth = {
        ok: false,
        releaseVersion: null,
        checkedAtMs: now,
        reason: "http_error",
        status: r.status,
        detail: body.slice(0, 200) || `HTTP ${r.status}`,
      };
    } else {
      const body = (await r.json()) as { releaseVersion?: string };
      cachedHealth = {
        ok: true,
        releaseVersion: body.releaseVersion ?? null,
        checkedAtMs: now,
      };
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    const isTimeout = err instanceof Error && err.name === "AbortError";
    ConsoleLogger.warn(`[gateway] /healthz failed: ${msg}`);
    cachedHealth = {
      ok: false,
      releaseVersion: null,
      checkedAtMs: now,
      reason: isTimeout ? "timeout" : "unreachable",
      status: null,
      detail: isTimeout ? "Gateway did not respond within 5 seconds" : msg,
    };
  }
  return cachedHealth;
}

async function callMint<T>(pathname: string, body: unknown): Promise<T> {
  let r: Response;
  try {
    r = await gatewayFetch(pathname, { method: "POST", body: JSON.stringify(body) });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    const isTimeout = err instanceof Error && err.name === "AbortError";
    throw new GatewayError(
      isTimeout ? "timeout" : "unreachable",
      null,
      isTimeout ? "Gateway did not respond within 5 seconds" : msg
    );
  }
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new GatewayError("http_error", r.status, text.slice(0, 300) || `HTTP ${r.status}`);
  }
  return (await r.json()) as T;
}

export async function mintVideoSession(opts: {
  fileId: number;
  startSecs: number;
  username: string;
}): Promise<VideoSessionResponse> {
  return callMint<VideoSessionResponse>("/internal/sessions", opts);
}

export async function renewVideoSession(opts: {
  sessionId: string;
  startSecs: number;
  username: string;
}): Promise<VideoSessionResponse> {
  return callMint<VideoSessionResponse>(
    `/internal/sessions/${encodeURIComponent(opts.sessionId)}/renew`,
    { startSecs: opts.startSecs, username: opts.username }
  );
}

export async function mintPdfToken(opts: {
  filename: string;
  username: string;
}): Promise<PdfTokenResponse> {
  return callMint<PdfTokenResponse>("/internal/pdf-tokens", opts);
}
