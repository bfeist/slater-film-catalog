// ---------------------------------------------------------------------------
// /api/reels — paginated search + detail + shotlist-pdf list
// ---------------------------------------------------------------------------

import { Router } from "express";
import fs from "node:fs";
import path from "node:path";
import { getDb } from "../db.js";
import { config } from "../config.js";
import { toSlater, resolveIdentifier, isRevealed } from "../slater.js";
import { QUALITY_BUCKETS } from "../../utils/qualityBuckets.js";

const router = Router();

// ---------------------------------------------------------------------------
// FTS5 helpers
// ---------------------------------------------------------------------------

/** Cached flag: does the film_rolls_fts table exist? Checked once per process. */
let fts5Available: boolean | null = null;

function hasFts5(): boolean {
  if (fts5Available !== null) return fts5Available;
  try {
    const row = getDb()
      .prepare(
        "SELECT COUNT(*) as c FROM sqlite_master WHERE type='table' AND name='film_rolls_fts'"
      )
      .get() as { c: number };
    fts5Available = row.c > 0;
  } catch {
    fts5Available = false;
  }
  return fts5Available;
}

/**
 * Build an FTS5 MATCH expression from a user query string.
 *
 * Supports:
 *   - Quoted phrases: "lunar module" → matches exact phrase
 *   - OR operator: apollo OR gemini → matches either term
 *   - Prefix matching: astro* → matches astronaut, astronomy, etc.
 *   - Default AND: apollo 11 → both terms must appear
 *
 * Tokens containing only punctuation/dashes are dropped (they're not indexed).
 */
function buildFts5Query(rawQuery: string): string | null {
  const trimmed = rawQuery.trim();
  if (!trimmed) return null;

  const parts: string[] = [];
  const remaining = trimmed;

  // Extract quoted phrases first
  const quoteRe = /"([^"]+)"/g;
  let match: RegExpExecArray | null;
  const quotePositions: Array<[number, number]> = [];

  while ((match = quoteRe.exec(trimmed)) !== null) {
    const inner = match[1].trim();
    if (inner) {
      // Clean each word inside the phrase but preserve the phrase grouping
      const words = inner
        .split(/\s+/)
        .map((w) => w.replace(/[^\w*]/g, ""))
        .filter((w) => w.length > 0);
      if (words.length > 0) {
        parts.push(`"${words.join(" ")}"`);
      }
    }
    quotePositions.push([match.index, match.index + match[0].length]);
  }

  // Remove quoted sections from remainder
  let unquoted = "";
  let pos = 0;
  for (const [start, end] of quotePositions) {
    unquoted += remaining.slice(pos, start) + " ";
    pos = end;
  }
  unquoted += remaining.slice(pos);

  // Process remaining tokens
  const tokens = unquoted.split(/\s+/).filter(Boolean);
  let i = 0;

  while (i < tokens.length) {
    const token = tokens[i];

    // OR operator — connect previous and next parts
    if (token.toUpperCase() === "OR" && parts.length > 0 && i + 1 < tokens.length) {
      const nextToken = tokens[i + 1].replace(/[^\w*]/g, "");
      if (nextToken.length > 0) {
        const prev = parts.pop()!;
        const nextQuoted = nextToken.includes("*") ? nextToken : `"${nextToken}"`;
        parts.push(`(${prev} OR ${nextQuoted})`);
        i += 2;
        continue;
      }
    }

    // Normal token — strip non-word chars (keep * for prefix)
    const cleaned = token.replace(/[^\w*]/g, "");
    if (cleaned.length > 0) {
      // Prefix match: keep trailing * as-is for FTS5
      if (cleaned.endsWith("*")) {
        parts.push(cleaned);
      } else {
        parts.push(`"${cleaned}"`);
      }
    }
    i++;
  }

  if (parts.length === 0) return null;
  return parts.join(" AND ");
}

// ---- GET /api/reels?q=&page=&limit=&has_transfer= ----
router.get("/", (req, res) => {
  const d = getDb();
  const q = (req.query.q as string) ?? "";
  const page = Math.max(1, parseInt((req.query.page as string) ?? "1", 10));
  const limit = Math.min(200, Math.max(1, parseInt((req.query.limit as string) ?? "50", 10)));
  const offset = (page - 1) * limit;
  const hasTransfer = req.query.has_transfer as string | undefined;
  const qualityBucket = req.query.quality_bucket as string | undefined;
  const reveal = isRevealed(req);

  // For guests, precompute which reels have at least one file that is NOT
  // shared across multiple reels (e.g. L00x proxy files on an LTO tape).
  // Reels whose only files are shared will show has_transfer_on_disk = 0.
  let guestTransferReels: Set<string> | null = null;
  if (!reveal) {
    const visibleRows = d
      .prepare(
        `SELECT DISTINCT tfm.reel_identifier
         FROM transfer_file_matches tfm
         WHERE tfm.file_id NOT IN (
           SELECT file_id FROM transfer_file_matches
           GROUP BY file_id
           HAVING COUNT(DISTINCT reel_identifier) > 1
         )`
      )
      .all() as { reel_identifier: string }[];
    guestTransferReels = new Set(visibleRows.map((r) => r.reel_identifier));
  }

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

  // ---------------------------------------------------------------------------
  // Determine search strategy: FTS5 (ranked) vs LIKE (fallback)
  // ---------------------------------------------------------------------------
  const useFts5 = q && hasFts5();
  const isSfrLookup =
    q &&
    resolveIdentifier(q.trim()) !== null &&
    resolveIdentifier(q.trim()) !== q.trim() &&
    q.trim().startsWith("SFR-");

  // For SFR lookups we always do an exact identifier match regardless of FTS5
  if (isSfrLookup) {
    const resolved = resolveIdentifier(q.trim())!;
    const filterConditions: string[] = ["identifier = ?"];
    const filterParams: (string | number)[] = [resolved];

    if (hasTransfer === "1") filterConditions.push("has_transfer_on_disk = 1");
    if (qualityBucket) {
      const bucket = QUALITY_BUCKETS.find((b) => b.key === qualityBucket);
      if (bucket) {
        filterConditions.push(
          `EXISTS (
            SELECT 1 FROM transfer_file_matches tfm
            JOIN files_on_disk fod ON fod.id = tfm.file_id
            JOIN ffprobe_metadata ffp ON ffp.file_id = fod.id
            WHERE tfm.reel_identifier = fr.identifier AND (${bucket.sqlWhere}))`
        );
      }
    }

    const where = "WHERE " + filterConditions.join(" AND ");
    const countRow = d
      .prepare(`SELECT COUNT(*) as c FROM film_rolls fr ${where}`)
      .get(...filterParams) as { c: number };
    const rows = d
      .prepare(
        `SELECT fr.identifier, fr.id_prefix, fr.title, fr.alternate_title, fr.date, fr.feet, fr.minutes, fr.audio,
              fr.mission, fr.has_shotlist_pdf, fr.has_transfer_on_disk,
              ${bestQualitySubquery("video_codec")} AS best_quality_codec,
              ${bestQualitySubquery("video_width")} AS best_quality_width,
              ${bestQualitySubquery("video_height")} AS best_quality_height
       FROM film_rolls fr ${where}
       ORDER BY fr.identifier LIMIT ? OFFSET ?`
      )
      .all(...filterParams, limit, offset);

    const mapped = (rows as { identifier: string }[]).map((r) => {
      const slater_number = toSlater(r.identifier);
      const guestDisk =
        guestTransferReels !== null
          ? { has_transfer_on_disk: guestTransferReels.has(r.identifier) ? 1 : 0 }
          : {};
      return reveal
        ? { ...r, slater_number }
        : { ...r, identifier: slater_number, slater_number, ...guestDisk };
    });
    res.json({ total: countRow.c, page, limit, rows: mapped, revealed: reveal });
    return;
  }

  // ---------------------------------------------------------------------------
  // FTS5 ranked search path
  // ---------------------------------------------------------------------------
  if (useFts5) {
    const ftsQuery = buildFts5Query(q);
    if (ftsQuery) {
      // BM25 column weights: identifier(5), title(10), alternate_title(5),
      // description(3), mission(2), shotlist_text(1)
      const filterConditions: string[] = [];
      const filterParams: (string | number)[] = [];

      if (hasTransfer === "1") filterConditions.push("fr.has_transfer_on_disk = 1");
      if (qualityBucket) {
        const bucket = QUALITY_BUCKETS.find((b) => b.key === qualityBucket);
        if (bucket) {
          filterConditions.push(
            `EXISTS (
              SELECT 1 FROM transfer_file_matches tfm
              JOIN files_on_disk fod ON fod.id = tfm.file_id
              JOIN ffprobe_metadata ffp ON ffp.file_id = fod.id
              WHERE tfm.reel_identifier = fr.identifier AND (${bucket.sqlWhere}))`
          );
        }
      }

      const extraWhere = filterConditions.length ? "AND " + filterConditions.join(" AND ") : "";

      // Count matching rows
      const countRow = d
        .prepare(
          `SELECT COUNT(*) as c
         FROM film_rolls_fts fts
         JOIN film_rolls fr ON fr.rowid = fts.rowid
         WHERE film_rolls_fts MATCH ? ${extraWhere}`
        )
        .get(ftsQuery, ...filterParams) as { c: number };

      // Fetch page of results ranked by BM25
      const rows = d
        .prepare(
          `SELECT fr.identifier, fr.id_prefix, fr.title, fr.alternate_title, fr.date,
                fr.feet, fr.minutes, fr.audio, fr.mission,
                fr.has_shotlist_pdf, fr.has_transfer_on_disk,
                ${bestQualitySubquery("video_codec")} AS best_quality_codec,
                ${bestQualitySubquery("video_width")} AS best_quality_width,
                ${bestQualitySubquery("video_height")} AS best_quality_height,
                bm25(film_rolls_fts, 5.0, 10.0, 5.0, 3.0, 2.0, 1.0) AS search_rank,
                snippet(film_rolls_fts, 5, '<mark>', '</mark>', '…', 12) AS shotlist_snippet
         FROM film_rolls_fts fts
         JOIN film_rolls fr ON fr.rowid = fts.rowid
         WHERE film_rolls_fts MATCH ? ${extraWhere}
         ORDER BY search_rank
         LIMIT ? OFFSET ?`
        )
        .all(ftsQuery, ...filterParams, limit, offset);

      const mapped = (rows as { identifier: string }[]).map((r) => {
        const slater_number = toSlater(r.identifier);
        const guestDisk =
          guestTransferReels !== null
            ? { has_transfer_on_disk: guestTransferReels.has(r.identifier) ? 1 : 0 }
            : {};
        return reveal
          ? { ...r, slater_number }
          : { ...r, identifier: slater_number, slater_number, ...guestDisk };
      });
      res.json({ total: countRow.c, page, limit, rows: mapped, revealed: reveal, search: "fts5" });
      return;
    }
    // ftsQuery was null (all-punctuation query) — fall through to LIKE
  }

  // ---------------------------------------------------------------------------
  // LIKE fallback (no FTS5 table, or no search query)
  // ---------------------------------------------------------------------------
  const conditions: string[] = [];
  const params: (string | number)[] = [];

  if (q) {
    const tokens = q
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .map((t) => t.toLowerCase().replace(/[-_]/g, " "));
    if (tokens.length > 0) {
      const norm = (col: string) =>
        `REPLACE(REPLACE(LOWER(COALESCE(${col},'')), '-', ' '), '_', ' ')`;
      const fields = ["identifier", "title", "description", "mission"];
      const fieldConditions = fields.map((field) => {
        const allTokensMatch = tokens.map(() => `${norm(field)} LIKE ?`).join(" AND ");
        return `(${allTokensMatch})`;
      });
      conditions.push(`(${fieldConditions.join(" OR ")})`);
      for (const _field of fields) {
        for (const token of tokens) {
          params.push(`%${token}%`);
        }
      }
    }
  }
  if (hasTransfer === "1") {
    conditions.push("has_transfer_on_disk = 1");
  }
  if (qualityBucket) {
    const bucket = QUALITY_BUCKETS.find((b) => b.key === qualityBucket);
    if (bucket) {
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

  const mapped = (rows as { identifier: string }[]).map((r) => {
    const slater_number = toSlater(r.identifier);
    const guestDisk =
      guestTransferReels !== null
        ? { has_transfer_on_disk: guestTransferReels.has(r.identifier) ? 1 : 0 }
        : {};
    if (reveal) {
      return { ...r, slater_number };
    }
    return { ...r, identifier: slater_number, slater_number, ...guestDisk };
  });

  res.json({ total, page, limit, rows: mapped, revealed: reveal, search: q ? "like" : "none" });
});

// Regex ported from scripts/title_gen/generate_alt_titles.py (_REEL_ID_RE).
// Matches parenthesised annotations first, then bare reel identifiers.
const REEL_ID_RE =
  /\(\s*(?:FR-[A-G]?\d+(?:-\d+)?|AK-\d+|BRF\d+[A-Z]?)(?:\s+[A-Z0-9][A-Z0-9\s./]*?)?\s*\)|FR-[A-G]?\d+(?:-\d+)?|AK-\d+|BRF\d+[A-Z]?/gi;

function redactShotlistText(text: string, pdfStems: string[]): string {
  // 1. Strip standard reel-identifier patterns (FR-XXXX, AK-NNN, BRFnnnX)
  let out = text.replace(REEL_ID_RE, "[redacted]");

  // 2. Strip the specific PDF stem names verbatim (covers non-standard identifiers
  //    like 255-PV-10 that aren't captured by REEL_ID_RE)
  for (const stem of pdfStems) {
    if (stem.length < 3) continue; // skip trivially short strings
    const escaped = stem.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    out = out.replace(new RegExp(escaped, "gi"), "[redacted]");
  }

  return out;
}

// ---- GET /api/reels/:identifier/shotlist-text ----
// Serves LLM OCR text for guest users (and revealed users too).
router.get("/:identifier/shotlist-text", (req, res) => {
  const d = getDb();
  const rawParam = req.params.identifier;
  const identifier = resolveIdentifier(rawParam) ?? rawParam;
  const row = d
    .prepare("SELECT shotlist_pdfs FROM film_rolls WHERE identifier = ?")
    .get(identifier) as { shotlist_pdfs: string | null } | undefined;
  if (!row) {
    res.status(404).json({ error: "Reel not found" });
    return;
  }
  const pdfs: string[] = row.shotlist_pdfs ? JSON.parse(row.shotlist_pdfs) : [];
  if (pdfs.length === 0) {
    res.json({ identifier: rawParam, text: null });
    return;
  }

  // Collect OCR text from all matching JSON files
  const pdfStems: string[] = [];
  const texts: string[] = [];
  for (const pdfName of pdfs) {
    const stem = pdfName.replace(/\.pdf$/i, "");
    pdfStems.push(stem);
    const jsonPath = path.join(config.llmOcrDir, `${stem}.json`);
    if (!fs.existsSync(jsonPath)) continue;
    try {
      const data = JSON.parse(fs.readFileSync(jsonPath, "utf-8"));
      if (typeof data.llm_text === "string" && data.llm_text.trim()) {
        texts.push(data.llm_text);
      }
    } catch {
      /* skip malformed JSON */
    }
  }

  const combined = texts.join("\n\n") || null;

  const reveal = isRevealed(req);
  const displayId = reveal ? identifier : toSlater(identifier);
  let outText = combined;
  if (!reveal && combined) {
    outText = redactShotlistText(combined, pdfStems);
  }

  res.json({ identifier: displayId, text: outText });
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
