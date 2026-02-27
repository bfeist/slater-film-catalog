// ---------------------------------------------------------------------------
// Server configuration — environment-aware paths
// ---------------------------------------------------------------------------
//
// All path-dependent values are resolved here so the rest of the server code
// can just import `config` and not worry about which OS / deployment target
// it's running on.
//
// Environment variables (all optional, sensible defaults provided).
// Values are loaded from .env via dotenv (override: true — always wins over
// shell environment, quiet: true — no warnings if .env is absent).
// See .env.example for the full list and Docker/UNC examples.
//
//   PORT                  – HTTP port (default 3001)
//   NODE_ENV              – "production" | "development" (default "development")
//   DB_PATH               – Absolute path to the SQLite database
//   SHOTLIST_PDF_DIR      – Folder containing shotlist PDF scans
//   VIDEO_ARCHIVE_ROOT    – Base path for the NASA archive video share
//   WATERMARK_FONT_PATH   – Path to a TrueType font for ffmpeg watermark
//   VITE_DIST_DIR         – Path to the built Vite SPA (prod: served by Express)
// ---------------------------------------------------------------------------

import dotenv from "dotenv";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

// Load .env before any process.env reads below.
// override: true  — .env values always win over pre-existing shell variables
// quiet: true     — silently skip if .env doesn't exist (CI / Docker use real env vars)
dotenv.config({ override: true, quiet: true });

/**
 * Find the project root by walking up from the current file until we find
 * package.json.  This works whether running from source (`src/server/`) or
 * from the esbuild bundle (`.local/express/dist/`).
 */
function findProjectRoot(): string {
  let dir = path.dirname(fileURLToPath(import.meta.url));
  for (let i = 0; i < 10; i++) {
    if (fs.existsSync(path.join(dir, "package.json"))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) break; // filesystem root
    dir = parent;
  }
  // Fallback: assume cwd is the project root
  return process.cwd();
}

const PROJECT_ROOT = process.env.PROJECT_ROOT ?? findProjectRoot();

/** Resolve a path relative to project root */
function fromRoot(...segments: string[]): string {
  return path.resolve(PROJECT_ROOT, ...segments);
}

// ---------------------------------------------------------------------------
// Detect platform to pick sensible defaults for the archive path
// ---------------------------------------------------------------------------
function defaultArchiveRoot(): string {
  // Docker / Linux — the share is mounted as a volume
  // e.g.  docker run -v /mnt/user/NASA\ Archive:/archive ...
  if (process.platform === "linux") {
    return "/archive";
  }

  // Windows — mapped drive O:\ or UNC path
  // GitBash rewrites /o/ → O:\ automatically, but running under plain Node
  // the drive letter form is more reliable.
  if (process.platform === "win32") {
    return "O:\\";
  }

  // macOS — unlikely, but just in case
  return "/Volumes/NASA Archive";
}

// ---------------------------------------------------------------------------
// Exported config
// ---------------------------------------------------------------------------

const env = process.env.NODE_ENV ?? "development";

export const config = {
  env,
  isDev: env === "development",
  isProd: env === "production",
  port: parseInt(process.env.PORT ?? "3001", 10),

  /** Path to the SQLite catalog database */
  dbPath: process.env.DB_PATH ?? fromRoot("data", "01b_excel.db"),

  /** Directory containing the scanned shotlist PDFs */
  shotlistPdfDir:
    process.env.SHOTLIST_PDF_DIR ?? fromRoot("input_indexes", "MASTER FR shotlist folder"),

  /** Root of the NASA video archive share */
  videoArchiveRoot: process.env.VIDEO_ARCHIVE_ROOT ?? defaultArchiveRoot(),

  /** Font for the ffmpeg watermark overlay */
  watermarkFontPath:
    process.env.WATERMARK_FONT_PATH ??
    (process.platform === "win32"
      ? "C:/Windows/Fonts/arial.ttf"
      : "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),

  /** Built Vite SPA assets (served by Express in production) */
  viteDistDir: process.env.VITE_DIST_DIR ?? fromRoot(".local", "vite", "dist"),
} as const;

export type Config = typeof config;
