// ---------------------------------------------------------------------------
// /api/reels — paginated search + detail + shotlist-pdf list
// ---------------------------------------------------------------------------

import { Router } from "express";
import { getDb } from "../db.js";
import { toSlater, resolveIdentifier, isRevealed } from "../slater.js";

const router = Router();

// ---- GET /api/reels?q=&page=&limit=&has_transfer= ----
router.get("/", (req, res) => {
  const d = getDb();
  const q = (req.query.q as string) ?? "";
  const page = Math.max(1, parseInt((req.query.page as string) ?? "1", 10));
  const limit = Math.min(200, Math.max(1, parseInt((req.query.limit as string) ?? "50", 10)));
  const offset = (page - 1) * limit;
  const hasTransfer = req.query.has_transfer as string | undefined;

  const conditions: string[] = [];
  const params: (string | number)[] = [];

  if (q) {
    // If the query is a Slater number, resolve it and search by real identifier
    const resolved = resolveIdentifier(q.trim());
    if (resolved && resolved !== q.trim() && q.trim().startsWith("SFR-")) {
      conditions.push("identifier = ?");
      params.push(resolved);
    } else {
      // Split into tokens and normalise separators (- and _ → space, lowercase).
      const tokens = q
        .trim()
        .split(/\s+/)
        .filter(Boolean)
        .map((t) => t.toLowerCase().replace(/[-_]/g, " "));
      if (tokens.length > 0) {
        // Use SQLite REPLACE() to normalise stored column values the same way.
        const norm = (col: string) =>
          `REPLACE(REPLACE(LOWER(COALESCE(${col},'')), '-', ' '), '_', ' ')`;
        const fields = ["identifier", "title", "description", "mission"];
        // Require ALL tokens to appear in the SAME field (at least one field must
        // satisfy every token). This prevents "gemini" matching via title while
        // "4" sneaks in via an identifier like FR-0046.
        const fieldConditions = fields.map((field) => {
          const allTokensMatch = tokens.map(() => `${norm(field)} LIKE ?`).join(" AND ");
          return `(${allTokensMatch})`;
        });
        conditions.push(`(${fieldConditions.join(" OR ")})`);
        // Params: for each field, push a value per token.
        for (const _field of fields) {
          for (const token of tokens) {
            params.push(`%${token}%`);
          }
        }
      }
    } // close else for non-SFR search
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

  // Obfuscate identifiers unless the request carries a valid reveal key
  const reveal = isRevealed(req);
  const mapped = (rows as { identifier: string }[]).map((r) => {
    const slater_number = toSlater(r.identifier);
    if (reveal) {
      return { ...r, slater_number };
    }
    // Not revealed: replace identifier with slater number so routing still works
    return { ...r, identifier: slater_number, slater_number };
  });

  res.json({ total, page, limit, rows: mapped, revealed: reveal });
});

// ---- GET /api/reels/:identifier/shotlist-pdfs ----
router.get("/:identifier/shotlist-pdfs", (req, res) => {
  const d = getDb();
  const rawParam = req.params.identifier;
  const identifier = resolveIdentifier(rawParam) ?? rawParam;
  const row = d
    .prepare("SELECT shotlist_pdfs FROM film_rolls WHERE identifier = ?")
    .get(identifier) as { shotlist_pdfs: string | null } | undefined;
  const pdfs: string[] = row?.shotlist_pdfs ? JSON.parse(row.shotlist_pdfs) : [];
  // Return the display-facing identifier (slater or real) to the client
  const displayId = isRevealed(req) ? identifier : toSlater(identifier);
  res.json({ identifier: displayId, pdfs });
});

// ---- GET /api/reels/:identifier ----
router.get("/:identifier", (req, res) => {
  const d = getDb();
  const rawParam = req.params.identifier;
  const identifier = resolveIdentifier(rawParam) ?? rawParam;

  const reel = d.prepare("SELECT * FROM film_rolls WHERE identifier = ?").get(identifier) as
    | Record<string, unknown>
    | undefined;
  if (!reel) {
    res.status(404).json({ error: "Reel not found" });
    return;
  }

  const reveal = isRevealed(req);

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

  // Discovery shotlist entries — look up by tape_number via transfers so that
  // all identifiers on a tape get the shotlist, not just the one stored in
  // the identifier column of discovery_shotlist.
  const discoveryEntries = d
    .prepare(
      `SELECT ds.*
       FROM discovery_shotlist ds
       JOIN transfers t ON CAST(t.tape_number AS INTEGER) = ds.tape_number
       WHERE t.reel_identifier = ?
         AND t.transfer_type = 'discovery_capture'`
    )
    .all(identifier);

  // NARA citations (table added by 1b_ingest_first_steps.py migration)
  let naraCitations: unknown[] = [];
  try {
    naraCitations = d
      .prepare("SELECT * FROM nara_citations WHERE reel_identifier = ?")
      .all(identifier);
  } catch {
    /* table not yet created */
  }

  // External file refs: S3 / streaming URLs not stored on local disk
  let externalRefs: unknown[] = [];
  try {
    externalRefs = d
      .prepare("SELECT * FROM external_file_refs WHERE reel_identifier = ?")
      .all(identifier);
  } catch {
    /* table not yet created */
  }

  // Obfuscate the reel identifier when not in reveal mode
  const outReel = reveal ? reel : { ...reel, identifier: toSlater(identifier) };

  const outDiscoveryEntries = reveal
    ? discoveryEntries
    : (discoveryEntries as Record<string, unknown>[]).map((entry) => {
        const entryId =
          typeof entry.identifier === "string" && entry.identifier ? entry.identifier : null;
        if (!entryId) return entry;
        const obfuscated = toSlater(entryId);
        const rawText = typeof entry.shotlist_raw === "string" ? entry.shotlist_raw : null;
        return {
          ...entry,
          identifier: obfuscated,
          ...(rawText ? { shotlist_raw: rawText.split(entryId).join(obfuscated) } : null),
        };
      });

  res.json({
    reel: outReel,
    transfers,
    fileMatches,
    ffprobeData,
    discoveryEntries: outDiscoveryEntries,
    naraCitations,
    externalRefs,
    revealed: reveal,
  });
});

export default router;
