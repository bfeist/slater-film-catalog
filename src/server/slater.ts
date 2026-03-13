// ---------------------------------------------------------------------------
// Slater Number facility — reversible identifier obfuscation
// ---------------------------------------------------------------------------
//
// Generates deterministic "Slater numbers" (SFR-XXXXXX) from film roll
// identifiers using HMAC-SHA256.  The mapping is purely a function of the
// identifier string + a secret key, so it survives DB recreation.
//
// Reverse lookup (slater → identifier) requires the in-memory map built at
// startup by `initSlaterMap()`.
// ---------------------------------------------------------------------------

import crypto from "node:crypto";
import type { Request } from "express";
import { getDb } from "./db.js";
import { config } from "./config.js";

// ---- Bidirectional maps (populated at startup) ----------------------------

const identToSlater = new Map<string, string>();
const slaterToIdent = new Map<string, string>();
let initialized = false;

/**
 * Build the bidirectional identifier ↔ slater-number maps from all rows in
 * film_rolls.  Call once at server startup (after the DB is available).
 */
export function initSlaterMap(): void {
  const db = getDb();
  const rows = db.prepare("SELECT identifier FROM film_rolls").all() as {
    identifier: string;
  }[];

  identToSlater.clear();
  slaterToIdent.clear();

  for (const row of rows) {
    const slater = computeSlater(row.identifier);
    identToSlater.set(row.identifier, slater);
    slaterToIdent.set(slater, row.identifier);
  }

  initialized = true;
  console.log(`[slater] Mapped ${identToSlater.size} identifiers → slater numbers`);
}

// ---- Core computation -----------------------------------------------------

/**
 * Deterministically derive a Slater number from an identifier.
 * Uses HMAC-SHA256 with a configurable secret.  Collision resolution:
 * on the (rare) event two identifiers hash to the same 6-digit number,
 * we re-hash with an incrementing suffix until the collision is resolved.
 */
function computeSlater(identifier: string): string {
  for (let attempt = 0; attempt < 100; attempt++) {
    const input = attempt === 0 ? identifier : `${identifier}\x00${attempt}`;
    const hmac = crypto.createHmac("sha256", config.slaterSecret).update(input).digest();
    const num = (hmac.readUInt32BE(0) % 999999) + 1; // 1 – 999 999
    const slater = `SFR-${String(num).padStart(6, "0")}`;

    const existing = slaterToIdent.get(slater);
    if (!existing || existing === identifier) {
      return slater;
    }
    // collision — try next attempt
  }
  // Extremely unlikely — but fail loudly rather than silently collide
  throw new Error(`[slater] Exhausted 100 attempts for "${identifier}"`);
}

// ---- Public helpers -------------------------------------------------------

/** Map an identifier → its Slater number.  Falls back to computing on-the-fly. */
export function toSlater(identifier: string): string {
  if (!initialized) initSlaterMap();
  return identToSlater.get(identifier) ?? computeSlater(identifier);
}

/**
 * Resolve a URL parameter that may be either a Slater number or a real
 * identifier.  Returns the real identifier, or `null` if the slater number
 * is unknown.
 */
export function resolveIdentifier(slaterOrIdent: string): string | null {
  if (!initialized) initSlaterMap();

  if (slaterOrIdent.startsWith("SFR-")) {
    return slaterToIdent.get(slaterOrIdent) ?? null;
  }
  return slaterOrIdent;
}

/**
 * Does the current request carry a valid reveal key?
 * Checked via `X-Reveal-Key` header or `?reveal=` query param.
 */
export function isRevealed(req: Request): boolean {
  if (!config.revealSecret) return true; // no secret configured → always reveal
  const key =
    (req.headers["x-reveal-key"] as string | undefined) ?? (req.query.reveal as string | undefined);
  return !!key && key === config.revealSecret;
}
