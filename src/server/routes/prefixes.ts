// ---------------------------------------------------------------------------
// /api/prefixes — unique id_prefix list with counts
// ---------------------------------------------------------------------------

import { Router } from "express";
import { getDb } from "../db.js";

const router = Router();

router.get("/", (_req, res) => {
  const d = getDb();
  const rows = d
    .prepare(
      "SELECT id_prefix, COUNT(*) as count FROM film_rolls GROUP BY id_prefix ORDER BY count DESC"
    )
    .all();
  res.json(rows);
});

export default router;
