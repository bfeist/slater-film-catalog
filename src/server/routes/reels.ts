// ---------------------------------------------------------------------------
// /api/reels — paginated search + detail + shotlist-pdf list
// ---------------------------------------------------------------------------

import { Router } from "express";
import { getDb } from "../db.js";

const router = Router();

// ---- GET /api/reels?q=&prefix=&page=&limit=&has_transfer= ----
router.get("/", (req, res) => {
  const d = getDb();
  const q = (req.query.q as string) ?? "";
  const prefix = (req.query.prefix as string) ?? "";
  const page = Math.max(1, parseInt((req.query.page as string) ?? "1", 10));
  const limit = Math.min(200, Math.max(1, parseInt((req.query.limit as string) ?? "50", 10)));
  const offset = (page - 1) * limit;
  const hasTransfer = req.query.has_transfer as string | undefined;

  const conditions: string[] = [];
  const params: (string | number)[] = [];

  if (q) {
    conditions.push("(identifier LIKE ? OR title LIKE ? OR description LIKE ? OR mission LIKE ?)");
    const like = `%${q}%`;
    params.push(like, like, like, like);
  }
  if (prefix) {
    conditions.push("id_prefix = ?");
    params.push(prefix);
  }
  if (hasTransfer === "1") {
    conditions.push("has_transfer_on_disk = 1");
  }

  const where = conditions.length ? "WHERE " + conditions.join(" AND ") : "";

  const countRow = d.prepare(`SELECT COUNT(*) as c FROM film_rolls ${where}`).get(...params) as {
    c: number;
  };
  const total = countRow.c;

  const rows = d
    .prepare(
      `SELECT identifier, id_prefix, title, date, feet, minutes, audio, mission,
              has_shotlist_pdf, has_transfer_on_disk
       FROM film_rolls ${where}
       ORDER BY identifier
       LIMIT ? OFFSET ?`
    )
    .all(...params, limit, offset);

  res.json({ total, page, limit, rows });
});

// ---- GET /api/reels/:identifier/shotlist-pdfs ----
router.get("/:identifier/shotlist-pdfs", (req, res) => {
  const d = getDb();
  const identifier = req.params.identifier;
  const row = d
    .prepare("SELECT shotlist_pdfs FROM film_rolls WHERE identifier = ?")
    .get(identifier) as { shotlist_pdfs: string | null } | undefined;
  const pdfs: string[] = row?.shotlist_pdfs ? JSON.parse(row.shotlist_pdfs) : [];
  res.json({ identifier, pdfs });
});

// ---- GET /api/reels/:identifier ----
router.get("/:identifier", (req, res) => {
  const d = getDb();
  const identifier = req.params.identifier;

  const reel = d.prepare("SELECT * FROM film_rolls WHERE identifier = ?").get(identifier);
  if (!reel) {
    res.status(404).json({ error: "Reel not found" });
    return;
  }

  const transfers = d.prepare("SELECT * FROM transfers WHERE reel_identifier = ?").all(identifier);

  // File matches with joined files_on_disk data
  const fileMatches = d
    .prepare(
      `SELECT tfm.*, fod.folder_root, fod.rel_path, fod.filename, fod.extension, fod.size_bytes
       FROM transfer_file_matches tfm
       JOIN files_on_disk fod ON fod.id = tfm.file_id
       WHERE tfm.reel_identifier = ?`
    )
    .all(identifier);

  // ffprobe data for matched files
  const fileIds = (fileMatches as { file_id: number }[]).map((fm) => fm.file_id);
  let ffprobeData: unknown[] = [];
  if (fileIds.length > 0) {
    const placeholders = fileIds.map(() => "?").join(",");
    ffprobeData = d
      .prepare(
        `SELECT file_id, format_name, format_long_name, duration_secs, bit_rate,
                probe_size_bytes, nb_streams, video_codec, video_codec_long, video_profile,
                video_width, video_height, video_frame_rate, video_display_ar, video_pix_fmt,
                video_color_space, video_field_order, audio_codec, audio_codec_long,
                audio_sample_rate, audio_channels, audio_channel_layout, audio_bit_rate,
                quality_tier, quality_label, probed_at, probe_error
         FROM ffprobe_metadata
         WHERE file_id IN (${placeholders})`
      )
      .all(...fileIds);
  }

  // Discovery shotlist entries
  const discoveryEntries = d
    .prepare(
      `SELECT * FROM discovery_shotlist
       WHERE identifier LIKE ? OR identifier LIKE ?`
    )
    .all(`%${identifier}%`, `%${identifier.replace(/^FR-/, "")}%`);

  res.json({
    reel,
    transfers,
    fileMatches,
    ffprobeData,
    discoveryEntries,
  });
});

export default router;
