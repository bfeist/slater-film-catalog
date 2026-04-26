// ---------------------------------------------------------------------------
// /api/video/sessions, /api/video/sessions/:id/renew,
// /api/pdf/sessions, /api/gateway/status
//
// In monolithic mode (no HOME_GATEWAY_BASE_URL): synthesize same-origin URLs
// pointing at the local Express. No real token is issued; the existing
// streamId / Authorization-token flow is preserved so VideoPlayer keeps
// working unchanged.
//
// In split mode: forward to the home gateway over the shared secret and
// return the gateway URL the browser should hit directly.
// ---------------------------------------------------------------------------

import { Router } from "express";
import path from "node:path";
import fs from "node:fs";
import { config } from "../config.js";
import { getRequestUser } from "../slater.js";
import { getDb } from "../db.js";
import {
  checkGatewayHealth,
  mintVideoSession,
  renewVideoSession,
  mintPdfToken,
  GatewayError,
} from "../gatewayClient.js";
import { ConsoleLogger } from "../logger.js";

const router = Router();

interface VideoSessionPayload {
  streamUrl: string;
  sessionId: string;
  expiresAtMs: number | null;
  mode: "monolithic" | "split";
}

/** Map a GatewayError or unhealthy GatewayHealth into a client-facing payload. */
function gatewayErrorPayload(
  resource: "video" | "pdf",
  reason: "timeout" | "unreachable" | "http_error",
  status: number | null,
  detail: string | null
): { error: string; reason: string; detail: string; gatewayStatus: number | null } {
  const messages: Record<typeof reason, string> = {
    timeout: `The home gateway did not respond in time. ${resource === "video" ? "Video streaming" : "PDF download"} is unavailable right now.`,
    unreachable: `Could not reach the home gateway. ${resource === "video" ? "Video streaming" : "PDF download"} is offline.`,
    http_error: `The home gateway rejected the ${resource} request${status ? ` (HTTP ${status})` : ""}.`,
  };
  return {
    error: resource === "video" ? "streaming_unavailable" : "pdfs_unavailable",
    reason,
    detail: detail ?? messages[reason],
    gatewayStatus: status,
  };
}

function buildLocalStreamUrl(fileId: number, streamId: string, startSecs: number): string {
  const params = new URLSearchParams({ streamId });
  if (startSecs > 0) params.set("start", startSecs.toFixed(1));
  return `/api/video/${fileId}/stream?${params.toString()}`;
}

function buildLocalPdfUrl(filename: string): string {
  return `/api/shotlist-pdf/${encodeURIComponent(filename)}`;
}

// ---- POST /api/video/sessions ---------------------------------------------
router.post("/video/sessions", async (req, res) => {
  const fileId = Number((req.body as { fileId?: unknown })?.fileId);
  const startSecs = Number((req.body as { startSecs?: unknown })?.startSecs ?? 0) || 0;
  if (!Number.isFinite(fileId) || fileId <= 0) {
    res.status(400).json({ error: "fileId required" });
    return;
  }

  // Always verify the file exists in the catalog DB before minting.
  const exists = getDb().prepare("SELECT 1 FROM files_on_disk WHERE id = ?").get(fileId);
  if (!exists) {
    res.status(404).json({ error: "File not found" });
    return;
  }

  const username = getRequestUser(req);

  if (config.gatewayMode === "monolithic") {
    const sessionId = crypto.randomUUID();
    const payload: VideoSessionPayload = {
      mode: "monolithic",
      sessionId,
      streamUrl: buildLocalStreamUrl(fileId, sessionId, startSecs),
      expiresAtMs: null, // no expiry in monolithic mode
    };
    res.json(payload);
    return;
  }

  // catalog (split) mode
  const health = await checkGatewayHealth();
  if (!health.ok) {
    res
      .status(503)
      .json(
        gatewayErrorPayload(
          "video",
          health.reason ?? "unreachable",
          health.status ?? null,
          health.detail ?? null
        )
      );
    return;
  }
  try {
    const session = await mintVideoSession({ fileId, startSecs, username });
    const streamUrl = `${config.gatewayBaseUrl}/stream/${encodeURIComponent(session.token)}`;
    const payload: VideoSessionPayload = {
      mode: "split",
      sessionId: session.sessionId,
      streamUrl,
      expiresAtMs: session.expiresAtMs,
    };
    res.json(payload);
  } catch (err) {
    ConsoleLogger.warn(
      `[sessions] mint video session failed: ${err instanceof Error ? err.message : String(err)}`
    );
    if (err instanceof GatewayError) {
      res.status(503).json(gatewayErrorPayload("video", err.reason, err.status, err.detail));
    } else {
      res.status(503).json({
        error: "streaming_unavailable",
        reason: "unknown",
        detail: err instanceof Error ? err.message : String(err),
      });
    }
  }
});

// ---- POST /api/video/sessions/:id/renew -----------------------------------
router.post("/video/sessions/:id/renew", async (req, res) => {
  const sessionId = req.params.id;
  const startSecs = Number((req.body as { startSecs?: unknown })?.startSecs ?? 0) || 0;
  const username = getRequestUser(req);

  if (config.gatewayMode === "monolithic") {
    // No real renewal; synthesize a fresh URL with a new streamId.
    const newId = crypto.randomUUID();
    const fileId = Number((req.body as { fileId?: unknown })?.fileId);
    if (!Number.isFinite(fileId) || fileId <= 0) {
      res.status(400).json({ error: "fileId required for monolithic renew" });
      return;
    }
    const payload: VideoSessionPayload = {
      mode: "monolithic",
      sessionId: newId,
      streamUrl: buildLocalStreamUrl(fileId, newId, startSecs),
      expiresAtMs: null,
    };
    res.json(payload);
    return;
  }

  const health = await checkGatewayHealth();
  if (!health.ok) {
    res
      .status(503)
      .json(
        gatewayErrorPayload(
          "video",
          health.reason ?? "unreachable",
          health.status ?? null,
          health.detail ?? null
        )
      );
    return;
  }
  try {
    const session = await renewVideoSession({ sessionId, startSecs, username });
    const streamUrl = `${config.gatewayBaseUrl}/stream/${encodeURIComponent(session.token)}`;
    const payload: VideoSessionPayload = {
      mode: "split",
      sessionId: session.sessionId,
      streamUrl,
      expiresAtMs: session.expiresAtMs,
    };
    res.json(payload);
  } catch (err) {
    ConsoleLogger.warn(
      `[sessions] renew video session failed: ${err instanceof Error ? err.message : String(err)}`
    );
    if (err instanceof GatewayError) {
      res.status(503).json(gatewayErrorPayload("video", err.reason, err.status, err.detail));
    } else {
      res.status(503).json({
        error: "streaming_unavailable",
        reason: "unknown",
        detail: err instanceof Error ? err.message : String(err),
      });
    }
  }
});

// ---- POST /api/pdf/sessions -----------------------------------------------
router.post("/pdf/sessions", async (req, res) => {
  const filename = String((req.body as { filename?: unknown })?.filename ?? "");
  if (
    !filename ||
    !filename.endsWith(".pdf") ||
    filename.includes("/") ||
    filename.includes("\\") ||
    filename.includes("..")
  ) {
    res.status(400).json({ error: "Invalid filename" });
    return;
  }
  const username = getRequestUser(req);

  if (config.gatewayMode === "monolithic") {
    // In monolithic mode the catalog process owns SHOTLIST_PDF_DIR — sanity
    // check the file exists locally before returning a same-origin URL.
    const local = path.join(config.shotlistPdfDir, filename);
    if (!fs.existsSync(local)) {
      res.status(404).json({ error: "PDF not found" });
      return;
    }
    res.json({
      mode: "monolithic",
      pdfUrl: buildLocalPdfUrl(filename),
      expiresAtMs: null,
    });
    return;
  }

  const health = await checkGatewayHealth();
  if (!health.ok) {
    res
      .status(503)
      .json(
        gatewayErrorPayload(
          "pdf",
          health.reason ?? "unreachable",
          health.status ?? null,
          health.detail ?? null
        )
      );
    return;
  }
  try {
    const tok = await mintPdfToken({ filename, username });
    res.json({
      mode: "split",
      pdfUrl: `${config.gatewayBaseUrl}/pdf/${encodeURIComponent(tok.token)}`,
      expiresAtMs: tok.expiresAtMs,
    });
  } catch (err) {
    ConsoleLogger.warn(
      `[sessions] mint pdf token failed: ${err instanceof Error ? err.message : String(err)}`
    );
    if (err instanceof GatewayError) {
      res.status(503).json(gatewayErrorPayload("pdf", err.reason, err.status, err.detail));
    } else {
      res.status(503).json({
        error: "pdfs_unavailable",
        reason: "unknown",
        detail: err instanceof Error ? err.message : String(err),
      });
    }
  }
});

// ---- GET /api/gateway/status ----------------------------------------------
router.get("/gateway/status", async (_req, res) => {
  if (config.gatewayMode === "monolithic") {
    res.json({ mode: "monolithic", available: true });
    return;
  }
  const h = await checkGatewayHealth();
  res.json({
    mode: "split",
    available: h.ok,
    releaseVersion: h.releaseVersion,
    checkedAtMs: h.checkedAtMs,
  });
});

export default router;
