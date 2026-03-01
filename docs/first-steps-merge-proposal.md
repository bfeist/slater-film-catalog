# First Steps Scanning List — DB Merge Proposal

## Source File

`input_indexes/First Steps - Master Scanning List.xlsx`

This spreadsheet tracks the physical scanning project (carried out by Final Frame) that brought NARA RG-255 film reels to digital files. It covers three projects across ~337 total rows.

---

## Sheets Overview

| Sheet | Rows | Identifier prefix | Coverage |
|---|---|---|---|
| `Project 1 - NARA Panavision Col` | 210 | `255-PV-*` | 70mm Panavision/Technicolor originals |
| `Project 1 - NARA Special Venue` | 28 | `40-UD-*`, `255-SE-*`, `43-US-*`, `151.1-*`, `255-KSC-*` | Specialty/venue films, mixed gauge |
| `Project 2 - 1635 NARA Selection` | 99 | `255-WS-*`, `255-PV-*`, `255-FR-*`, `255-HQ-*`, `255-S-*`, `255-SE-*` | 16mm/35mm selections; overlaps with Apollo FR reels |
| `Refile Audit`, `Final Frame Film Scanning Data`, `Scanning Progress` | — | — | Scanning logistics only; **not ingested** |

**Focus for ingestion: the three project sheets above.** The remaining three sheets are operational tracking with no catalog value.

---

## Identifier Normalization

NARA RG-255 identifiers always carry a `255-` collection prefix in the spreadsheet. Our existing `film_rolls` DB already uses bare identifiers (e.g. `FR-0001` from ApolloReelsMaster.xlsx, originating from the same `255-FR-*` NARA series). To maintain consistency:

**Rule: always strip the `255-` prefix when storing in `film_rolls.identifier`.**

| Raw NARA identifier | Stored identifier | Notes |
|---|---|---|
| `255-PV-10` | `PV-10` | New prefix — new rows |
| `255-FR-0001` | `FR-0001` | Already in DB from ApolloReelsMaster — enrich existing row |
| `255-WS-5-11` | `WS-5-11` | New prefix — new rows |
| `255-HQ-114` | `HQ-114` | New prefix (note: existing DB has `HQ-` from Master List) |
| `255-SE-1` | `SE-1` | New prefix — new rows |
| `255-S-NNNN` | `S-NNNN` | Already partially in DB from Master List `255-S` entries |
| `40-UD-1` | `40-UD-1` | Non-255 identifier — store as-is (no prefix strip) |

The `extract_id_prefix()` helper in `one_time/1b_ingest_excel.py` needs new cases: `PV`, `WS`, `SE`, `40-UD`, `43-US`, `151.1`.

When matching files on disk (e.g. in `/o/Stephen_2025/`), re-apply the `255-` prefix: `PV-10` → look for `255-pv-10*` or `255-PV-10*`.

---

## Multi-Reel Handling

Several NARA identifiers have multiple physical reels (e.g. `255-PV-10` has Reel 1 and Reel 2). Each reel becomes a separate `digital_file_name` (`255-pv-10-r1`, `255-pv-10-r2`). 

**Approach:** One `film_rolls` row per base identifier. Each physical reel scan → one row in `transfers` (type `digital_file`) with the `digital_file_name` as `filename`. This mirrors how we handle multi-cut HD tapes already.

---

## Column Selection

### Project 1 — Panavision (columns 0–28)

| Col | Header | Keep? | Maps to |
|---|---|---|---|
| 0 | NARA Local Identifier | ✅ | `film_rolls.identifier` (strip `255-`) |
| 1 | Reel Number | ✅ | `transfers.reel_part` (new column, nullable int) |
| 2 | Digital File Name | ✅ | `transfers.filename` (type `digital_file`) |
| 3 | *(blank)* | ❌ | — |
| 4 | Technicolor/Panavision Roll Number | ✅ | `film_rolls.nara_roll_number` (new column, TEXT) |
| 5 | Reel Title / Content | ✅ | `film_rolls.title` (enriches/fills NULL) |
| 6 | Additional Citations / Source Reels | ✅ | `nara_citations` table (see below) |
| 7 | Content | ✅ | `film_rolls.description` (enriches/fills NULL) |
| 8 | Date Filmed (If Known) | ✅ | `film_rolls.date_raw` / `film_rolls.date` |
| 9 | Shot List | ✅ | `film_rolls.has_shotlist_pdf` flag heuristic; store raw text in `nara_shot_list_ref` |
| 10 | Sync Sound Reference | ✅ | `transfers.audio_file` (links sync sound reel) |
| 11 | 65mm Reel in NARA Holdings | ✅ | `film_rolls.gauge_65mm` (new boolean column) |
| 12 | 35mm Reel in NARA Holdings | ✅ | `film_rolls.gauge_35mm` (new boolean column) |
| 13 | Footage | ✅ | `film_rolls.feet` (enriches/fills NULL) |
| 14 | Notes | ✅ | `film_rolls.notes` (new TEXT column) |
| 15 | Shipment Number | ❌ | Scanning logistics |
| 16 | Box Number | ❌ | Scanning logistics |
| 17–24 | Depart/Arrive dates (outward/return/follow-up) | ❌ | Scanning logistics |
| 25 | Scanning Completed — Final Frame Verification | ❌ | Scanning logistics |
| 26 | Running Time | ❌ | Derived from digital file; unreliable pre-ingest |
| 27 | NARA Refile Audit Complete | ❌ | Scanning logistics |
| 28 | NARA Preservation Lab Inspection Complete | ❌ | Scanning logistics |

### Project 1 — Special Venue (additional columns)

| Col | Header | Keep? | Maps to |
|---|---|---|---|
| — | Gauge | ✅ | `film_rolls.gauge_35mm` / `film_rolls.gauge_65mm` derived |
| — | Format | ✅ | `transfers.file_description` |
| — | Comments | ✅ | `film_rolls.notes` |

### Project 2 — 1635 NARA Selection (additional columns)

| Col | Header | Keep? | Maps to |
|---|---|---|---|
| — | Format | ✅ | `transfers.file_description` |
| — | Comments | ✅ | `film_rolls.notes` |
| — | Best Available NARA Source | ✅ | `film_rolls.notes` or a new `nara_best_source` column |
| — | NARA JSC File Roll Collection Reel # | ✅ | `nara_citations` table |
| — | NARA HQ Stock Footage Collection Reel # | ✅ | `nara_citations` table |
| — | NARA JSC Engineering Footage Collection Reel # | ✅ | `nara_citations` table |
| — | Stephen Slater Notes on Duplication | ✅ | `film_rolls.notes` |
| — | LTO / Tape No | ✅ | `transfers` row (type `lto_copy`) |
| — | Best Statement Pictures Reference Source | ✅ | `film_rolls.notes` |
| — | Confirmation of NARA Source Reels | ✅ | `nara_citations` table |
| — | Final Project Plan # 2 Scanning List | ❌ | Scanning logistics |
| — | Shipment/Box/Date columns | ❌ | Scanning logistics |
| — | Scanning Completed / Refile / Inspection | ❌ | Scanning logistics |
| — | Running Time of Digital Files | ❌ | Derived |

---

## Proposed Schema Changes

### 1. New columns on `film_rolls`

```sql
ALTER TABLE film_rolls ADD COLUMN nara_roll_number  TEXT;   -- Technicolor/Panavision roll #
ALTER TABLE film_rolls ADD COLUMN gauge_65mm         INTEGER DEFAULT 0;  -- 65mm original exists at NARA
ALTER TABLE film_rolls ADD COLUMN gauge_35mm         INTEGER DEFAULT 0;  -- 35mm original exists at NARA
ALTER TABLE film_rolls ADD COLUMN nara_shot_list_ref TEXT;   -- raw "Shot List" field value
ALTER TABLE film_rolls ADD COLUMN notes              TEXT;   -- merged Notes/Comments/Slater notes
```

`has_shotlist_pdf` already exists — the ingestion script should set it to 1 when the Shot List column contains a non-null, non-`"-"` value that references a shot list document.

### 2. New column on `transfers`

```sql
ALTER TABLE transfers ADD COLUMN reel_part INTEGER;  -- reel number within a multi-reel item (nullable)
```

### 3. New `nara_citations` table

The `Additional Citations / Source Reels` column often contains references that are the *actual filename stems* on disk (e.g. `KSC-67-08-0001`) or references to other archive collections. These can be multi-valued (some cells contain comma-separated lists or newline-separated values). A separate table is cleaner than a delimited text column:

```sql
CREATE TABLE IF NOT EXISTS nara_citations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    reel_identifier     TEXT NOT NULL REFERENCES film_rolls(identifier),
    citation            TEXT NOT NULL,       -- raw citation value, trimmed
    citation_type       TEXT,                -- 'ksc_number', 'as_magazine', 'jsc_collection',
                                             -- 'hq_collection', 'engineering_collection',
                                             -- 'source_reel', 'other'
    source_column       TEXT,                -- which spreadsheet column this came from
    source_sheet        TEXT                 -- which sheet
);

CREATE INDEX IF NOT EXISTS idx_nc_reel  ON nara_citations(reel_identifier);
CREATE INDEX IF NOT EXISTS idx_nc_cit   ON nara_citations(citation);
```

**Citation type heuristics** (to be applied at ingest):
- Matches `KSC-\d{2}-\d{2}` → `ksc_number`
- Matches `AS-\d+` → `as_magazine` (Apollo onboard camera magazine)
- Matches `NARA JSC File Roll`, `NARA HQ Stock`, etc. → respective collection type
- Otherwise → `other`

These citation values are often the identifiers that `/o/Stephen_2025/` filenames were derived from, making them critical for Stage 1c file matching.

---

## `extract_id_prefix()` Updates

The utility function in `one_time/1b_ingest_excel.py` needs new prefix cases. The new ingestion script should include an updated version:

```python
NEW_PREFIXES = ["PV-", "WS-", "SE-", "255-KSC", "40-UD", "43-US"]
```

And the `255-` stripping logic:

```python
def normalize_nara_identifier(raw: str) -> str:
    """Strip '255-' prefix from NARA RG-255 identifiers."""
    s = raw.strip()
    if s.startswith("255-"):
        return s[4:]
    return s
```

---

## `transfers.filename` and File Matching

The `Digital File Name` column gives the lowercase-hyphenated stem of the scanned output file (e.g. `255-pv-10-r1`). On disk these appear in `/o/Stephen_2025/` with naming patterns like:

- `255-S-NNNN_HD_MASTER.mov`
- `255-S-NNNN_HD_UPSCALE_MASTER.mov`

The `255-pv-*` and `255-ws-*` Panavision/WIDESCREEN scans likely follow a similar pattern. Stage 1c (`1c_verify_transfers.py`) should use these `digital_file_name` values as match candidates when walking `/o/Stephen_2025/`, applying case-insensitive prefix matching.

The ingestion script should store:
- `transfers.filename` = the `Digital File Name` cell value (e.g. `255-pv-10-r1`)
- `transfers.transfer_type` = `'digital_file'`
- `transfers.file_description` = Format column where present (e.g. `16mm color`)
- `transfers.reel_part` = `Reel Number` column where present

---

## Cross-Sheet Deduplication

Project 2 contains identifiers that overlap with Project 1 (`255-PV-*`) and with ApolloReelsMaster.xlsx (`255-FR-*`). Strategy:

1. **`255-FR-*` identifiers**: After stripping prefix → `FR-*` → `INSERT OR IGNORE` into `film_rolls` (row likely already exists); upsert enrichment columns; add new `nara_citations` and `transfers` rows.
2. **`255-PV-*` appearing in both Project 1 and Project 2**: Deduplicate by identifier + reel_part. Process Project 1 first (more complete data), then skip rows from Project 2 already covered.
3. **Non-255 identifiers** (`40-UD-*`, `43-US-*`, `151.1-*`): Store as-is; new rows.

---

## Recommended Ingestion Script Location

`scripts/1b_ingest_first_steps.py`

This becomes the new Stage 1b (the original `1b_ingest_excel.py` has moved to `scripts/one_time/`). It should:

1. Accept `--sheet` to target individual sheets or `--all` for all three
2. Accept `--force` to drop and recreate NARA-derived rows
3. Run `ALTER TABLE … ADD COLUMN IF NOT EXISTS` for new columns before inserting
4. Print the same style stats as `1b_ingest_excel.py`
5. Be incremental: skip rows where `(identifier, reel_part)` already exists in `transfers`
