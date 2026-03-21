// ---------------------------------------------------------------------------
// Express application — mounts all API routes
// ---------------------------------------------------------------------------

import express from "express";
import path from "node:path";
import fs from "node:fs";
import { config } from "./config.js";
import { ConsoleLogger } from "./logger.js";

// Route modules
import statsRouter from "./routes/stats.js";
import reelsRouter from "./routes/reels.js";
import videoRouter from "./routes/video.js";
import shotlistPdfRouter from "./routes/shotlistPdf.js";
import authRouter from "./routes/auth.js";
import { initSlaterMap } from "./slater.js";

export function createApp(): express.Application {
  const app = express();

  // Build the identifier ↔ slater-number lookup table
  initSlaterMap();

  // JSON body parsing for auth endpoints
  app.use(express.json());

  // ---------------------------------------------------------------------------
  // API routes
  // ---------------------------------------------------------------------------
  app.use("/api/auth", authRouter);
  app.use("/api/stats", statsRouter);
  app.use("/api/reels", reelsRouter);
  app.use("/api/video", videoRouter);
  app.use("/api/shotlist-pdf", shotlistPdfRouter);

  // ---------------------------------------------------------------------------
  // Production: serve the built Vite SPA
  // Skipped when SERVE_FRONTEND=false (Docker mode: Nginx handles the SPA)
  // ---------------------------------------------------------------------------
  if (config.isProd && config.serveFrontend) {
    const distDir = config.viteDistDir;
    if (fs.existsSync(distDir)) {
      app.use(express.static(distDir));
      // SPA fallback — any non-API route serves index.html
      app.get("*", (_req, res) => {
        res.sendFile(path.join(distDir, "index.html"));
      });
    } else {
      ConsoleLogger.warn(`Warning: Vite dist not found at ${distDir}`);
      ConsoleLogger.warn("Run 'npm run build' first, or set VITE_DIST_DIR.");
    }
  }

  return app;
}
