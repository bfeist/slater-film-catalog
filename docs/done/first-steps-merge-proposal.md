# First Steps Scanning List — DB Merge Proposal

## Source Files

1. `input_indexes/First Steps - Master Scanning List.xlsx` — scanning project tracking spreadsheet
2. `input_indexes/nara_apollo_70mm_metadata.json` — scraped NARA catalog records (182 PV reels)

This spreadsheet tracks the physical scanning project (carried out by Final Frame) that brought NARA RG-255 film reels to digital files. It covers three projects across ~337 total rows.

---

## Sheets Overview

| Sheet                                                                 | Rows | Identifier prefix                                                     | Coverage                                            |
| --------------------------------------------------------------------- | ---- | --------------------------------------------------------------------- | --------------------------------------------------- |
| `Project 1 - NARA Panavision Col`                                     | 210  | `255-PV-*`                                                            | 70mm Panavision/Technicolor originals               |
| `Project 1 - NARA Special Venue`                                      | 28   | `40-UD-*`, `255-SE-*`, `43-US-*`, `151.1-*`, `255-KSC-*`              | Specialty/venue films, mixed gauge                  |
| `Project 2 - 1635 NARA Selection`                                     | 99   | `255-WS-*`, `255-PV-*`, `255-FR-*`, `255-HQ-*`, `255-S-*`, `255-SE-*` | 16mm/35mm selections; overlaps with Apollo FR reels |
| `Refile Audit`, `Final Frame Film Scanning Data`, `Scanning Progress` | —    | —                                                                     | Scanning logistics only; **not ingested**           |

**Focus for ingestion: the three project sheets above.** The remaining three sheets are operational tracking with no catalog value.

---

## Identifier Normalization

NARA RG-255 identifiers always carry a `255-` collection prefix in the spreadsheet. Our existing `film_rolls` DB already uses bare identifiers (e.g. `FR-0001` from ApolloReelsMaster.xlsx, originating from the same `255-FR-*` NARA series). To maintain consistency:

**Rule: always strip the `255-` prefix when storing in `film_rolls.identifier`.**

> **Note:** `255-` is the NARA RG-255 collection prefix used by the National Archives. It is **never stored in the app's DB** — all `film_rolls.identifier` values are bare (e.g. `PV-10`, `FR-0001`). However, physical files on disk (e.g. under `/o/Master 5/70mm Panavision Collection/`) and NARA S3 URLs frequently retain the `255-` prefix in their filenames (e.g. `255-pv-10-r1_4K.mov`). Any file-matching logic must account for this: strip `255-` when looking up the DB, or re-prepend it when constructing expected on-disk filenames.

| Raw NARA identifier | Stored identifier | Notes                                                      |
| ------------------- | ----------------- | ---------------------------------------------------------- |
| `255-PV-10`         | `PV-10`           | New prefix — new rows                                      |
| `255-FR-0001`       | `FR-0001`         | Already in DB from ApolloReelsMaster — enrich existing row |
| `255-WS-5-11`       | `WS-5-11`         | New prefix — new rows                                      |
| `255-HQ-114`        | `HQ-114`          | New prefix (note: existing DB has `HQ-` from Master List)  |
| `255-SE-1`          | `SE-1`            | New prefix — new rows                                      |
| `255-S-NNNN`        | `S-NNNN`          | Already partially in DB from Master List `255-S` entries   |
| `40-UD-1`           | `40-UD-1`         | Non-255 identifier — store as-is (no prefix strip)         |

The `extract_id_prefix()` helper in `one_time/1b_ingest_excel.py` needs new cases: `PV`, `WS`, `SE`, `40-UD`, `43-US`, `151.1`.

When matching files on disk (e.g. in `/o/Stephen_2025/`), re-apply the `255-` prefix: `PV-10` → look for `255-pv-10*` or `255-PV-10*`.

---

## Multi-Reel Handling

Several NARA identifiers have multiple physical reels (e.g. `255-PV-10` has Reel 1 and Reel 2,
confirmed in both the spreadsheet `Reel Number` column and the NARA JSON `object_designator`
field which reads "Reel 1 of 2"). Each reel scan → one row in `transfers` (type `digital_file`)
with `reel_part` set. One `film_rolls` row per base identifier.

---

## Film Gauge — Unified Text Field

**Replace the originally proposed `gauge_65mm INTEGER` + `gauge_35mm INTEGER` pair with a
single `film_gauge TEXT` column on `film_rolls`.**

Rationale: gauge is inconsistent across source docs. The existing `film_rolls` rows from
ApolloReelsMaster have no gauge recorded at all (FR reels are presumed 16mm/35mm but it isn't
stated anywhere in the spreadsheet). Two boolean columns for two specific sizes would produce
a sea of NULLs for the majority of the catalog and can't represent gauges like 16mm, 70mm,
8mm, etc.

Mapping:

- **Project 1 Panavision**: All are 65mm Panavision originals → `film_gauge = '65mm'`
  - The "65mm Reel in NARA Holdings" / "35mm Reel in NARA Holdings" columns describe what
    physical print formats NARA retains (not the original camera negative gauge).
    This is noted in `film_rolls.notes` as free text when relevant (e.g. "NARA also holds
    35mm print") but does not need dedicated boolean columns.
- **Project 1 Special Venue**: Has an explicit `Gauge` text column → stored directly into
  `film_gauge` (e.g. `"35mm"`, `"16mm"`, `"70mm"`).
- **Project 2**: The `Format` column sometimes contains gauge context (e.g. `"16mm color"`,
  `"35mm B&W"`) → parse out gauge token and store in `film_gauge`.
- **Existing FR reels**: `film_gauge` left NULL. These can be back-filled if the information
  becomes available.

## NARA Catalog JSON (`nara_apollo_70mm_metadata.json`)

The JSON contains 182 records scraped from the NARA online catalog (all `255-PV-*` reels).
Fields and disposition:

| Field                         | Coverage | Disposition                                                              |
| ----------------------------- | -------- | ------------------------------------------------------------------------ |
| `naid`                        | 182/182  | Store in `film_rolls.nara_id` — unique NARA archival identifier          |
| `url`                         | 182/182  | Store in `film_rolls.nara_catalog_url` — NARA catalog page               |
| `title`                       | 182/182  | Enrich `film_rolls.title` (fill NULL / prefer over scanning list)        |
| `description`                 | 105/182  | Enrich `film_rolls.description` (fill NULL)                              |
| `dates`                       | 182/182  | Parse item-level date where present; enrich `film_rolls.date_raw`        |
| `agency_assigned_identifiers` | 170/182  | PV roll number + KSC roll number → `nara_citations`                      |
| `object_designator`           | 182/182  | "Reel N of M" — confirms reel count; useful for data completeness checks |
| `digital_objects`             | 182/182  | Video download URLs and shotlist PDFs — see below                        |
| `access`                      | 182/182  | All "Unrestricted" — skip                                                |
| `use_restriction`             | 182/182  | All "Possibly Restricted / Copyright" boilerplate — skip                 |
| `creator`                     | 182/182  | Always NASA — skip                                                       |
| `part_of`                     | 182/182  | Always same record group/series — skip                                   |
| `archived_copy_location`      | 182/182  | Boilerplate NARA address — skip                                          |
| `tag_count`, `comment_count`  | 182/182  | Always 0 — skip                                                          |

### NARA digital video URLs → `transfers`

Each `digital_objects` entry with a `download_url` is a publicly accessible MP4 on NARA's
S3 bucket (e.g. `https://s3.amazonaws.com/NARAprodstorage/lz/mopix/255/PV/255-pv-7.mp4`).
All 182 records have one. Store as a `transfers` row:

- `transfer_type = 'nara_streaming'`
- `filename` = URL filename stem (e.g. `255-pv-7`)
- `file_path` = full download URL
- `reel_part` = parsed from stem's `-rN` suffix where present

### NARA shotlist PDFs

110 of 182 records have a `digital_objects` entry with `type: "document"` pointing to a PDF
on NARA S3, e.g.:

```
https://s3.amazonaws.com/NARAprodstorage/lz/mopix/255/PV/Shotlist/255-PV-7.pdf
```

These are accessible and should be downloaded. **The spreadsheet "Shot List" column links to
a locked Google Drive folder and is not usable.**

Download destination: `data/nara_shotlists/{filename}` (e.g. `data/nara_shotlists/255-PV-7.pdf`).

Tracking in DB:

- `film_rolls.has_shotlist_pdf = 1` when a NARA shotlist PDF exists
- `film_rolls.nara_shot_list_ref` = the PDF filename

A one-time script `scripts/one_time/1b_download_nara_shotlists.py` handles the actual download,
using `data/nara_shotlists/` for already-downloaded file detection (incremental).

### `agency_assigned_identifiers` → `nara_citations`

The NARA JSON `agency_assigned_identifiers` array contains structured entries like:

```json
[
  { "value": "1871", "note": "This is the Technicolor/Panavision Roll Number" },
  { "value": "KSC-67-08-001", "note": "This is the roll number." }
]
```

These map to `nara_citations` with `source_sheet = 'nara_json'` and types `pv_roll_number`
or `ksc_number`. This cross-references the scanning spreadsheet's PV roll column; conflicts
flag data quality issues.

---

## Column Selection

### Project 1 — Panavision (columns 0–28)

| Col   | Header                                           | Keep? | Maps to                                                                      |
| ----- | ------------------------------------------------ | ----- | ---------------------------------------------------------------------------- |
| 0     | NARA Local Identifier                            | ✅    | `film_rolls.identifier` (strip `255-`)                                       |
| 1     | Reel Number                                      | ✅    | `transfers.reel_part`                                                        |
| 2     | Digital File Name                                | ✅    | `transfers.filename` (type `digital_file`)                                   |
| 3     | _(blank)_                                        | ❌    | —                                                                            |
| 4     | Technicolor/Panavision Roll Number               | ✅    | `nara_citations` (type `pv_roll_number`)                                     |
| 5     | Reel Title / Content                             | ✅    | `film_rolls.title` (enriches/fills NULL)                                     |
| 6     | Additional Citations / Source Reels              | ✅    | `nara_citations`                                                             |
| 7     | Content                                          | ✅    | `film_rolls.description` (enriches/fills NULL)                               |
| 8     | Date Filmed (If Known)                           | ✅    | `film_rolls.date_raw`                                                        |
| 9     | Shot List                                        | ❌    | Google Drive links — not accessible. Shotlist presence tracked via NARA JSON |
| 10    | Sync Sound Reference                             | ✅    | `transfers.audio_file`                                                       |
| 11    | 65mm Reel in NARA Holdings                       | ✅    | Append "NARA holds 65mm print" to `film_rolls.notes` when present            |
| 12    | 35mm Reel in NARA Holdings                       | ✅    | Append "NARA holds 35mm print" to `film_rolls.notes` when present            |
| 13    | Footage                                          | ✅    | `film_rolls.feet` (enriches/fills NULL)                                      |
| 14    | Notes                                            | ✅    | `film_rolls.notes`                                                           |
| 15–28 | Shipment/Box/Dates/Audit/Inspection/Running Time | ❌    | Scanning logistics                                                           |

→ `film_rolls.film_gauge = '65mm'` hardcoded for all PV rows.

### Project 1 — Special Venue

| Col  | Header                | Keep? | Maps to                                                     |
| ---- | --------------------- | ----- | ----------------------------------------------------------- |
| 0    | NARA Local Identifier | ✅    | `film_rolls.identifier`                                     |
| 1    | Digital File Name     | ✅    | `transfers.filename`                                        |
| 2    | Title                 | ✅    | `film_rolls.title`                                          |
| 3    | Shot List             | ❌    | Google Drive links                                          |
| 4    | Gauge                 | ✅    | `film_rolls.film_gauge` (e.g. `"35mm"`, `"16mm"`, `"70mm"`) |
| 5    | Format                | ✅    | `transfers.file_description`                                |
| 6    | Footage               | ✅    | `film_rolls.feet`                                           |
| 7    | Comments              | ✅    | `film_rolls.notes`                                          |
| 8–17 | Shipment/Dates/Audit  | ❌    | Scanning logistics                                          |

### Project 2 — 1635 NARA Selection

| Col   | Header                                          | Keep? | Maps to                                                                   |
| ----- | ----------------------------------------------- | ----- | ------------------------------------------------------------------------- |
| 0     | NARA Local Identifier                           | ✅    | `film_rolls.identifier`                                                   |
| 1     | Reel Number                                     | ✅    | `transfers.reel_part`                                                     |
| 2     | Digital File Name                               | ✅    | `transfers.filename`                                                      |
| 3     | Reel Title                                      | ✅    | `film_rolls.title`                                                        |
| 4     | Date                                            | ✅    | `film_rolls.date_raw`                                                     |
| 5     | Additional Citations / Source Reels             | ✅    | `nara_citations`                                                          |
| 6     | Footage                                         | ✅    | `film_rolls.feet`                                                         |
| 7     | Format                                          | ✅    | `transfers.file_description`; parse gauge token → `film_rolls.film_gauge` |
| 8     | Shot List                                       | ❌    | Google Drive links                                                        |
| 9     | Sync Sound Reference                            | ✅    | `transfers.audio_file`                                                    |
| 10    | Comments                                        | ✅    | `film_rolls.notes`                                                        |
| 11–20 | Shipment/Box/Dates/Scanning/Running Time/Refile | ❌    | Scanning logistics                                                        |
| 21    | Final Project Plan # 2 Scanning List            | ❌    | Scanning logistics                                                        |
| 22    | Best Available NARA Source                      | ❌    | Superseded by NARA JSON                                                   |
| 23    | NARA JSC File Roll Collection Reel #            | ✅    | `nara_citations` (type `jsc_collection`)                                  |
| 24    | NARA HQ Stock Footage Collection Reel #         | ✅    | `nara_citations` (type `hq_collection`)                                   |
| 25    | NARA JSC Engineering Footage Collection Reel #  | ✅    | `nara_citations` (type `engineering_collection`)                          |
| 26    | Stephen Slater Notes on Duplication             | ✅    | `film_rolls.notes`                                                        |
| 27    | LTO / Tape No                                   | ❌    | No usable FR cross-ref available                                          |
| 28    | Best Statement Pictures Reference Source        | ❌    | Not needed                                                                |
| 29    | Confirmation of NARA Source Reels               | ❌    | Not needed                                                                |

---

## Proposed Schema Changes

### 1. New columns on `film_rolls`

```sql
ALTER TABLE film_rolls ADD COLUMN nara_id           TEXT;   -- NARA archival ID (naid)
ALTER TABLE film_rolls ADD COLUMN nara_catalog_url  TEXT;   -- https://catalog.archives.gov/id/...
ALTER TABLE film_rolls ADD COLUMN nara_roll_number  TEXT;   -- Technicolor/Panavision roll # (from scanning list)
ALTER TABLE film_rolls ADD COLUMN film_gauge        TEXT;   -- original film gauge: "65mm", "35mm", "16mm", etc.
ALTER TABLE film_rolls ADD COLUMN nara_shot_list_ref TEXT;  -- downloaded NARA shotlist PDF filename
ALTER TABLE film_rolls ADD COLUMN notes             TEXT;   -- free text: Notes/Comments/Slater notes/NARA holdings info
```

No `gauge_65mm`/`gauge_35mm` boolean columns. The "65mm/35mm in NARA Holdings" spreadsheet
columns go into `notes` as human-readable text.

### 2. New column on `transfers`

```sql
ALTER TABLE transfers ADD COLUMN reel_part INTEGER;  -- reel number within a multi-reel item (nullable)
```

New `transfer_type` value: `'nara_streaming'` (NARA S3 MP4 download URL stored in `file_path`).

### 3. New `nara_citations` table

```sql
CREATE TABLE IF NOT EXISTS nara_citations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    reel_identifier TEXT NOT NULL,
    citation        TEXT NOT NULL,
    citation_type   TEXT,            -- ksc_number | pv_roll_number | as_magazine |
                                     -- jsc_collection | hq_collection |
                                     -- engineering_collection | other
    source_column   TEXT,            -- which spreadsheet/JSON field this came from
    source_sheet    TEXT             -- sheet name or 'nara_json'
);

CREATE INDEX IF NOT EXISTS idx_nc_reel ON nara_citations(reel_identifier);
CREATE INDEX IF NOT EXISTS idx_nc_cit  ON nara_citations(citation);
```

Citation type heuristics:

- `KSC-\d{2}-` → `ksc_number`
- `AS-\d+` → `as_magazine`
- Technicolor/PV roll (numeric) from NARA JSON → `pv_roll_number`
- NARA JSC File Roll / HQ Stock / Engineering collection values → respective type
- Otherwise → `other`

Citation values in `Additional Citations / Source Reels` are often the identifier stems that
`/o/Stephen_2025/` filenames were derived from, making them critical for Stage 1c matching.

---

## Shotlist Scraping (one-time)

Script: `scripts/one_time/1b_download_nara_shotlists.py`

1. Reads `input_indexes/nara_apollo_70mm_metadata.json`
2. For each record with a `type: "document"` entry in `digital_objects`, downloads the PDF to
   `data/nara_shotlists/` (skipping already-downloaded files — incremental)
3. Updates `film_rolls.has_shotlist_pdf = 1` and `film_rolls.nara_shot_list_ref = '{filename}'`
   in the DB after successful download

Known count: 110 of 182 PV reels have an accessible NARA shotlist PDF.

---

## Ingestion Script Outline

`scripts/1b_ingest_first_steps.py` — ingests the spreadsheet (all three project sheets).
Additional `--source nara-json` mode ingests `nara_apollo_70mm_metadata.json`:

- Enriches `film_rolls` (title, description, date, nara_id, nara_catalog_url,
  nara_shot_list_ref, has_shotlist_pdf)
- Inserts `nara_streaming` transfers from `download_url` entries
- Inserts `nara_citations` from `agency_assigned_identifiers`

`scripts/one_time/1b_download_nara_shotlists.py` — downloads NARA shotlist PDFs.

---

## `extract_id_prefix()` Updates

New prefix cases needed in the helper function:

```python
NEW_PREFIXES = ["PV-", "WS-", "SE-", "255-KSC", "40-UD", "43-US"]
```

---

## `transfers.filename` and File Matching

The `Digital File Name` column gives the lowercase-hyphenated stem of the scanned output file (e.g. `255-pv-10-r1`). On disk these appear in `/o/Stephen_2025/` with naming patterns like:

- `255-S-NNNN_HD_MASTER.mov`
- `255-S-NNNN_HD_UPSCALE_MASTER.mov`

The `255-pv-*` and `255-ws-*` Panavision/WIDESCREEN scans likely follow a similar pattern. Stage 1c (`1c_verify_transfers.py`) should use these `digital_file_name` values as match candidates when walking `/o/Stephen_2025/`, applying case-insensitive prefix matching.

The `Digital File Name` column gives the lowercase-hyphenated stem of the scanned output file
(e.g. `255-pv-10-r1`). Stage 1c (`1c_verify_transfers.py`) should use these values as match
candidates when walking `/o/Stephen_2025/`, applying case-insensitive prefix matching.

The ingestion script stores:

- `transfers.filename` = the `Digital File Name` cell value
- `transfers.transfer_type` = `'digital_file'`
- `transfers.file_description` = Format column where present
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
