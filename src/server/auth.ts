// ---------------------------------------------------------------------------
// User authentication — config-file-based user management with session tokens
// ---------------------------------------------------------------------------

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

export type UserRole = "full" | "guest";

interface UserEntry {
  username: string;
  password: string;
  role: UserRole;
}

interface AuthConfig {
  users: UserEntry[];
}

interface Session {
  username: string;
  role: UserRole;
  createdAt: number;
}

// In-memory session store (keyed by token)
const sessions = new Map<string, Session>();

// Session TTL: 24 hours
const SESSION_TTL_MS = 24 * 60 * 60 * 1000;

/** Find the project root by walking up from the current file. */
function findProjectRoot(): string {
  let dir = path.dirname(new URL(import.meta.url).pathname);
  // On Windows, strip leading / from /C:/... paths
  if (process.platform === "win32" && dir.startsWith("/")) {
    dir = dir.slice(1);
  }
  for (let i = 0; i < 10; i++) {
    if (fs.existsSync(path.join(dir, "package.json"))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return process.cwd();
}

const AUTH_CONFIG_PATH =
  process.env.AUTH_CONFIG_PATH ?? path.join(findProjectRoot(), "auth.config.json");

/** Read auth config fresh from disk on every call — no caching. */
function getAuthConfig(): AuthConfig {
  if (!fs.existsSync(AUTH_CONFIG_PATH)) {
    console.warn(`[auth] No auth config found at ${AUTH_CONFIG_PATH} — no users configured`);
    return { users: [] };
  }
  const raw = fs.readFileSync(AUTH_CONFIG_PATH, "utf-8");
  return JSON.parse(raw) as AuthConfig;
}

/**
 * Authenticate a username/password pair. Returns a session token on success,
 * or null on failure.
 */
export function authenticate(
  username: string,
  password: string
): { token: string; username: string; role: UserRole } | null {
  const config = getAuthConfig();
  const user = config.users.find((u) => u.username.toLowerCase() === username.toLowerCase().trim());
  if (!user) return null;

  if (user.password !== password) return null;

  // Create session
  const token = crypto.randomBytes(32).toString("hex");
  sessions.set(token, {
    username: user.username,
    role: user.role,
    createdAt: Date.now(),
  });

  return { token, username: user.username, role: user.role };
}

/** Look up a session by token. Returns null if expired or unknown. */
export function getSession(token: string): Session | null {
  const session = sessions.get(token);
  if (!session) return null;
  if (Date.now() - session.createdAt > SESSION_TTL_MS) {
    sessions.delete(token);
    return null;
  }
  return session;
}

/** Destroy a session (logout). */
export function destroySession(token: string): void {
  sessions.delete(token);
}

/** Periodic cleanup of expired sessions. */
setInterval(
  () => {
    const now = Date.now();
    for (const [token, session] of sessions) {
      if (now - session.createdAt > SESSION_TTL_MS) {
        sessions.delete(token);
      }
    }
  },
  60 * 60 * 1000
); // Every hour
