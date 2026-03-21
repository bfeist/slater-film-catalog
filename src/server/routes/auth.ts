// ---------------------------------------------------------------------------
// /api/auth/* — login, logout, session check
// ---------------------------------------------------------------------------

import { Router } from "express";
import { authenticate, getSession, destroySession } from "../auth.js";
import { logActivity } from "../logger.js";
import { ConsoleLogger } from "../logger.js";

const router = Router();

// Parse JSON bodies for POST requests
router.use((req, res, next) => {
  if (req.method === "POST" && !req.is("json")) {
    res.status(415).json({ error: "Content-Type must be application/json" });
    return;
  }
  next();
});

/** Extract bearer token from Authorization header. */
function extractToken(authHeader: string | undefined): string | null {
  if (!authHeader) return null;
  const m = authHeader.match(/^Bearer\s+(\S+)$/i);
  return m ? m[1] : null;
}

// ---- POST /api/auth/login ----
router.post("/login", async (req, res) => {
  const { username, password } = req.body as { username?: string; password?: string };
  if (!username?.trim() || !password) {
    res.status(400).json({ error: "Username and password are required" });
    return;
  }

  const result = authenticate(username, password);
  if (!result) {
    ConsoleLogger.warn(`[auth] Failed login attempt for user: ${username}`);
    logActivity({ action: "auth_login", username: username.trim(), details: "failed" });
    res.status(401).json({ error: "Invalid username or password" });
    return;
  }

  logActivity({ action: "auth_login", username: result.username, details: `role=${result.role}` });
  res.json({ token: result.token, username: result.username, role: result.role });
});

// ---- POST /api/auth/logout ----
router.post("/logout", (req, res) => {
  const token = extractToken(req.headers.authorization);
  if (token) {
    const session = getSession(token);
    if (session) {
      logActivity({ action: "auth_logout", username: session.username });
    }
    destroySession(token);
  }
  res.json({ ok: true });
});

// ---- GET /api/auth/me ----
router.get("/me", (req, res) => {
  const token = extractToken(req.headers.authorization);
  if (!token) {
    res.status(401).json({ error: "Not authenticated" });
    return;
  }

  const session = getSession(token);
  if (!session) {
    res.status(401).json({ error: "Session expired" });
    return;
  }

  res.json({ username: session.username, role: session.role });
});

export default router;
