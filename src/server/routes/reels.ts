// ---------------------------------------------------------------------------
// /api/reels — paginated search + detail + shotlist-pdf list
// ---------------------------------------------------------------------------

import { Router } from "express";
import { getDb } from "../db.js";
import { toSlater, resolveIdentifier, isRevealed } from "../slater.js";
import { QUALITY_BUCKETS } from "../../utils/qualityBuckets.js";

const router = Router();

// ---- GET /api/reels?q=&page=&limit=&has_transfer= ----
router.get("/", (req, res) => {
  const d = getDb();
  const q = (req.query.q as string) ?? "";
  const page = Math.max(1, parseInt((req.query.page as string) ?? "1", 10));
  const limit = Math.min(200, Math.max(1, parseInt((req.query.limit as string) ?? "50", 10)));
  const offset = (page - 1) * limit;
  const hasTransfer = req.query.has_transfer as string | undefined;
  const qualityBucket = req.query.quality_bucket as string | undefined;

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
  if (qualityBucket) {
    const bucket = QUALITY_BUCKETS.find((b) => b.key === qualityBucket);
    if (bucket) {
      // sqlWhere contains only literal values — safe to interpolate directly
      conditions.push(
        `EXISTS (
          SELECT 1
          FROM transfer_file_matches tfm
          JOIN files_on_disk fod ON fod.id = tfm.file_id
          JOIN ffprobe_metadata ffp ON ffp.file_id = fod.id
          WHERE tfm.reel_identifier = fr.identifier
            AND (${bucket.sqlWhere}))`
      );
    }
  }

  const where = conditions.length ? "WHERE " + conditions.join(" AND ") : "";

  // Order to pick the "best" available file: ProRes > H.264 > MPEG > other,
  // then widest resolution first.
  const BEST_QUALITY_ORDER = `
    CASE WHEN ffp.video_codec = 'prores' THEN 0
         WHEN ffp.video_codec = 'h264' OR ffp.video_codec = 'hevc' THEN 1
         WHEN ffp.video_codec LIKE 'mpeg%' THEN 2
         ELSE 3 END ASC,
    COALESCE(ffp.video_width, 0) DESC`;

  const bestQualitySubquery = (col: string) =>
    `(SELECT ffp.${col}
      FROM transfer_file_matches tfm
      JOIN files_on_disk fod ON fod.id = tfm.file_id
      JOIN ffprobe_metadata ffp ON ffp.file_id = fod.id
      WHERE tfm.reel_identifier = fr.identifier
        AND ffp.video_codec IS NOT NULL
      ORDER BY ${BEST_QUALITY_ORDER}
      LIMIT 1)`;

  const countRow = d.prepare(`SELECT COUNT(*) as c FROM film_rolls fr ${where}`).get(...params) as {
    c: number;
  };
  const total = countRow.c;

  const rows = d
    .prepare(
      `SELECT fr.identifier, fr.id_prefix, fr.title, fr.alternate_title, fr.date, fr.feet, fr.minutes, fr.audio,
              fr.mission, fr.has_shotlist_pdf, fr.has_transfer_on_disk,
              ${bestQualitySubquery("video_codec")} AS best_quality_codec,
              ${bestQualitySubquery("video_width")} AS best_quality_width,
              ${bestQualitySubquery("video_height")} AS best_quality_height
       FROM film_rolls fr ${where}
       ORDER BY fr.identifier
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

  // For unauthenticated users: hide any file or discovery tape that is shared
  // across multiple reels (e.g. L00x proxy files matched to a whole LTO tape,
  // or Discovery compilation tapes containing several film rolls).
  let visibleFileMatches: unknown[] = fileMatches;
  let visibleFfprobeData: unknown[] = ffprobeData;
  let visibleDiscoveryEntries: unknown[] = discoveryEntries;

  if (!reveal) {
    // File IDs referenced by more than one distinct reel
    const multiReelFileIds = new Set(
      (
        d
          .prepare(
            `SELECT file_id
             FROM transfer_file_matches
             GROUP BY file_id
             HAVING COUNT(DISTINCT reel_identifier) > 1`
          )
          .all() as { file_id: number }[]
      ).map((r) => r.file_id)
    );
    visibleFileMatches = (fileMatches as { file_id: number }[]).filter(
      (fm) => !multiReelFileIds.has(fm.file_id)
    );

    // Keep ffprobe data only for surviving files
    const visibleFileIdSet = new Set(
      (visibleFileMatches as { file_id: number }[]).map((fm) => fm.file_id)
    );
    visibleFfprobeData = (ffprobeData as { file_id: number }[]).filter((p) =>
      visibleFileIdSet.has(p.file_id)
    );

    // Tape numbers linked to more than one distinct reel via discovery_capture
    const multiReelTapeNums = new Set(
      (
        d
          .prepare(
            `SELECT tape_number
             FROM transfers
             WHERE transfer_type = 'discovery_capture'
             GROUP BY tape_number
             HAVING COUNT(DISTINCT reel_identifier) > 1`
          )
          .all() as { tape_number: number }[]
      ).map((r) => r.tape_number)
    );
    visibleDiscoveryEntries = (discoveryEntries as { tape_number: number }[]).filter(
      (e) => !multiReelTapeNums.has(e.tape_number)
    );
  }

  // Obfuscate the reel identifier when not in reveal mode
  const scrubNara = (v: unknown) => (typeof v === "string" ? v.replace(/NARA/gi, "") : v);
  const outReel = reveal
    ? reel
    : { ...reel, identifier: toSlater(identifier), notes: scrubNara(reel.notes) };

  const outDiscoveryEntries = reveal
    ? discoveryEntries
    : (visibleDiscoveryEntries as Record<string, unknown>[]).map((entry) => {
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
    fileMatches: visibleFileMatches,
    ffprobeData: visibleFfprobeData,
    discoveryEntries: outDiscoveryEntries,
    naraCitations,
    externalRefs,
    revealed: reveal,
  });
});

export default router;
