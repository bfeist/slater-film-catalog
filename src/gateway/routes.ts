// ---------------------------------------------------------------------------
// Home gateway routes — internal (catalog-to-gateway) + public (browser)
// ---------------------------------------------------------------------------

import { Router, type Request, type Response, type NextFunction } from "express";
import path from "node:path";
import fs from "node:fs";
import { config } from "../server/config.js";
import { ConsoleLogger, logActivity } from "../server/logger.js";
import { streamFile, heartbeat, deregisterStream } from "../server/streamingPipeline.js";
import {
  mintVideoToken,
  renewVideoToken,
  mintPdfToken,
  consumeVideoToken,
  consumePdfToken,
} from "./tokens.js";

// ---------------------------------------------------------------------------
// CORS — allow one or more configured origins (comma-separated PUBLIC_ORIGIN).
// Applies to public /stream and /pdf endpoints. /internal/* is server-to-server.
// ---------------------------------------------------------------------------
const allowedOrigins: Set<string> = new Set(
  config.publicOrigin
    ? config.publicOrigin
        .split(",")
        .map((o) => o.trim())
        .filter(Boolean)
    : []
);

function applyCors(req: Request, res: Response, next: NextFunction): void {
  const requestOrigin = req.headers.origin ?? "";
  if (allowedOrigins.size > 0) {
    // Echo back the matched origin so multi-origin configs work correctly.
    const matched = allowedOrigins.has(requestOrigin) ? requestOrigin : [...allowedOrigins][0];
    res.setHeader("Access-Control-Allow-Origin", matched);
    res.setHeader("Vary", "Origin");
    res.setHeader("Cross-Origin-Resource-Policy", "cross-origin");
  }
  if (req.method === "OPTIONS") {
    res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Authorization,Content-Type");
    res.status(204).end();
    return;
  }
  next();
}

// ---------------------------------------------------------------------------
// Shared-secret bearer guard for /internal/*
// ---------------------------------------------------------------------------
function requireSharedSecret(req: Request, res: Response, next: NextFunction): void {
  if (!config.gatewaySharedSecret) {
    res.status(500).json({ error: "gateway not configured" });
    return;
  }
  const auth = req.headers.authorization ?? "";
  const m = auth.match(/^Bearer\s+(\S+)$/i);
  if (!m || m[1] !== config.gatewaySharedSecret) {
    res.status(401).json({ error: "unauthorized" });
    return;
  }
  next();
}

// ===========================================================================
// /healthz
// ===========================================================================
export function healthRouter(): Router {
  const r = Router();
  r.get("/healthz", (_req, res) => {
    res.json({ ok: true, releaseVersion: config.releaseVersion });
  });
  return r;
}

// ===========================================================================
// /internal/sessions, /internal/sessions/:id/renew, /internal/pdf-tokens
// ===========================================================================
export function internalRouter(): Router {
  const r = Router();
  r.use(requireSharedSecret);

  r.post("/sessions", (req, res) => {
    const fileId = Number((req.body as { fileId?: unknown })?.fileId);
    const startSecs = Number((req.body as { startSecs?: unknown })?.startSecs ?? 0) || 0;
    const username = String((req.body as { username?: unknown })?.username ?? "guest");
    if (!Number.isFinite(fileId) || fileId <= 0) {
      res.status(400).json({ error: "fileId required" });
      return;
    }
    const minted = mintVideoToken({ fileId, startSecs, username });
    res.json({ ...minted, releaseVersion: config.releaseVersion });
  });

  r.post("/sessions/:id/renew", (req, res) => {
    const startSecs = Number((req.body as { startSecs?: unknown })?.startSecs ?? 0) || 0;
    const username = String((req.body as { username?: unknown })?.username ?? "guest");
    const renewed = renewVideoToken({ sessionId: req.params.id, startSecs, username });
    if (!renewed) {
      res.status(410).json({ error: "session expired" });
      return;
    }
    res.json({ ...renewed, releaseVersion: config.releaseVersion });
  });

  r.post("/pdf-tokens", (req, res) => {
    const filename = String((req.body as { filename?: unknown })?.filename ?? "");
    const username = String((req.body as { username?: unknown })?.username ?? "guest");
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
    // Verify the file exists locally before issuing a token.
    const local = path.join(config.shotlistPdfDir, filename);
    if (!fs.existsSync(local)) {
      res.status(404).json({ error: "PDF not found" });
      return;
    }
    const minted = mintPdfToken({ filename, username });
    res.json({ ...minted, releaseVersion: config.releaseVersion });
  });

  return r;
}

// ===========================================================================
// /stream/:token, /stream/heartbeat, /stream/stop
// ===========================================================================
export function streamRouter(): Router {
  const r = Router();
  r.use(applyCors);

  r.get("/heartbeat", (req, res) => {
    const streamId = req.query.streamId as string | undefined;
    if (!streamId || !heartbeat(streamId)) {
      res.status(404).json({ error: "Unknown streamId" });
      return;
    }
    res.json({ ok: true });
  });

  r.post("/stop", (req, res) => {
    const streamId = req.query.streamId as string | undefined;
    if (streamId) deregisterStream(streamId, "client stop");
    res.json({ ok: true });
  });

  r.get("/:token", (req, res) => {
    const data = consumeVideoToken(req.params.token);
    if (!data) {
      res.status(401).send("Invalid or expired token");
      return;
    }
    // Browser must supply its own streamId (same UUID it uses for heartbeat).
    // Falls back to sessionId so a single-shot fetch still works.
    const streamId = (req.query.streamId as string | undefined) ?? data.sessionId;
    const fail = streamFile(req, res, {
      fileId: data.fileId,
      startSecs: data.startSecs,
      streamId,
      username: data.username,
    });
    if (fail) res.status(fail.status).send(fail.message);
  });

  return r;
}

// ===========================================================================
// /pdf/:token
// ===========================================================================
export function pdfRouter(): Router {
  const r = Router();
  r.use(applyCors);

  r.get("/:token", (req, res) => {
    const data = consumePdfToken(req.params.token);
    if (!data) {
      res.status(401).json({ error: "Invalid or expired token" });
      return;
    }
    const pdfPath = path.join(config.shotlistPdfDir, data.filename);
    if (!fs.existsSync(pdfPath)) {
      res.status(404).json({ error: "PDF not found" });
      return;
    }
    const stat = fs.statSync(pdfPath);
    logActivity({
      action: "read_shotlist_pdf",
      username: data.username,
      details: `file=${data.filename} via=gateway`,
    });
    res.setHeader("Content-Type", "application/pdf");
    res.setHeader("Content-Length", stat.size);
    res.setHeader("Content-Disposition", "inline");
    res.setHeader("Cache-Control", "private, no-store");
    fs.createReadStream(pdfPath).pipe(res);
  });

  return r;
}

// ---------------------------------------------------------------------------
// (re-exported for the entry point)
// ---------------------------------------------------------------------------
export const _logRouterInfo = (mounted: string[]): void => {
  ConsoleLogger.info(`[gateway] mounted: ${mounted.join(", ")}`);
};
