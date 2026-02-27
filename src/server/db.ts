// ---------------------------------------------------------------------------
// Database singleton — lazy-loaded, read-only better-sqlite3 connection
// ---------------------------------------------------------------------------

import Database from "better-sqlite3";
import { config } from "./config.js";

let db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (db) return db;
  db = new Database(config.dbPath, { readonly: true });
  db.pragma("journal_mode = WAL");
  return db;
}

export function closeDb(): void {
  if (db) {
    db.close();
    db = null;
  }
}
