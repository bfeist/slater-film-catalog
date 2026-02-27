// ---------------------------------------------------------------------------
// /api/stats — aggregate counts from every table
// ---------------------------------------------------------------------------

import { Router } from "express";
import { getDb } from "../db.js";

const router = Router();

router.get("/", (_req, res) => {
  const d = getDb();
  const count = (sql: string): number => (d.prepare(sql).get() as { c: number }).c;

  const stats = {
    film_rolls: count("SELECT COUNT(*) as c FROM film_rolls"),
    transfers: count("SELECT COUNT(*) as c FROM transfers"),
    files_on_disk: count("SELECT COUNT(*) as c FROM files_on_disk"),
    ffprobe_metadata: count("SELECT COUNT(*) as c FROM ffprobe_metadata"),
    discovery_shotlist: count("SELECT COUNT(*) as c FROM discovery_shotlist"),
    transfer_file_matches: count("SELECT COUNT(*) as c FROM transfer_file_matches"),
    total_video_size_bytes: count(
      "SELECT COALESCE(SUM(f.size_bytes), 0) as c FROM files_on_disk f JOIN ffprobe_metadata m ON m.file_id = f.id WHERE m.probe_error IS NULL"
    ),
  };
  res.json(stats);
});

export default router;
