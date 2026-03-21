// ---------------------------------------------------------------------------
// Server logging — console logger + file-based activity logger
// ---------------------------------------------------------------------------

import fs from "node:fs";
import path from "node:path";
import { config } from "./config.js";

// ---------------------------------------------------------------------------
// Console Logger — leveled console output with ANSI colors
// ---------------------------------------------------------------------------

export type LogLevel = "off" | "error" | "warn" | "notice" | "info" | "debug";

const LOG_LEVEL_PRIORITY: Record<LogLevel, number> = {
  off: 0,
  error: 1,
  warn: 2,
  notice: 3,
  info: 4,
  debug: 5,
};

const COLORS = {
  reset: "\x1b[0m",
  red: "\x1b[31m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  blue: "\x1b[34m",
  gray: "\x1b[90m",
};

const LEVEL_COLORS: Record<Exclude<LogLevel, "off">, string> = {
  error: COLORS.red,
  warn: COLORS.yellow,
  notice: COLORS.blue,
  info: COLORS.green,
  debug: COLORS.gray,
};

export class ConsoleLogger {
  private static level: LogLevel = "off";
  private static initialized = false;

  private static initialize(): void {
    if (this.initialized) return;
    this.initialized = true;
    this.level = (process.env.LOG_LEVEL as LogLevel) || "info";
  }

  private static getTimestamp(): string {
    const iso = new Date().toISOString();
    return `[${iso.slice(5, 10)} ${iso.slice(11, 23)}]`;
  }

  private static shouldLog(messageLevel: LogLevel): boolean {
    this.initialize();
    return LOG_LEVEL_PRIORITY[messageLevel] <= LOG_LEVEL_PRIORITY[this.level];
  }

  static setLevel(level: LogLevel): void {
    this.level = level;
    this.initialized = true;
  }

  static error(...args: unknown[]): void {
    if (this.shouldLog("error")) {
      console.error(`${LEVEL_COLORS.error}${this.getTimestamp()} [ERROR]${COLORS.reset}`, ...args);
    }
  }

  static warn(...args: unknown[]): void {
    if (this.shouldLog("warn")) {
      console.warn(`${LEVEL_COLORS.warn}${this.getTimestamp()} [WARN]${COLORS.reset}`, ...args);
    }
  }

  static notice(...args: unknown[]): void {
    if (this.shouldLog("notice")) {
      console.log(`${LEVEL_COLORS.notice}${this.getTimestamp()} [NOTICE]${COLORS.reset}`, ...args);
    }
  }

  static info(...args: unknown[]): void {
    if (this.shouldLog("info")) {
      console.log(`${LEVEL_COLORS.info}${this.getTimestamp()} [INFO]${COLORS.reset}`, ...args);
    }
  }

  static debug(...args: unknown[]): void {
    if (this.shouldLog("debug")) {
      console.debug(`${LEVEL_COLORS.debug}${this.getTimestamp()} [DEBUG]${COLORS.reset}`, ...args);
    }
  }
}

// ---------------------------------------------------------------------------
// Activity Logger — append-only file logging for user activity tracking
// ---------------------------------------------------------------------------

/**
 * Append a line to the activity log file. Creates the log directory and file
 * if they don't exist. Each line is a tab-separated record:
 *   timestamp \t action \t identifier \t details
 *
 * Log location is determined by LOG_DIR env var:
 *   - Docker: /app/logs  (mounted as a volume)
 *   - Dev:    .local/logs (inside project, gitignored)
 */
function getLogDir(): string {
  return config.logDir;
}

function getLogFilePath(): string {
  const now = new Date();
  const dateStr = now.toISOString().slice(0, 10); // YYYY-MM-DD
  return path.join(getLogDir(), `activity-${dateStr}.log`);
}

function ensureLogDir(): void {
  const dir = getLogDir();
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

export type ActivityAction =
  | "view_reel"
  | "play_video"
  | "stop_video"
  | "auth_login"
  | "auth_logout"
  | "search";

interface ActivityEntry {
  action: ActivityAction;
  identifier?: string;
  username: string;
  details?: string;
}

export function logActivity(entry: ActivityEntry): void {
  try {
    ensureLogDir();
    const timestamp = new Date().toISOString();
    const identifier = entry.identifier ?? "-";
    const details = entry.details ?? "";
    const line = `${timestamp}\t${entry.action}\t${entry.username}\t${identifier}\t${details}\n`;
    fs.appendFileSync(getLogFilePath(), line, "utf-8");
  } catch (err) {
    // Don't let logging failures crash the server
    ConsoleLogger.error("[activity-log] Failed to write:", err);
  }
}
