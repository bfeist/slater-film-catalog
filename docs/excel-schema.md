# ApolloReelsMaster.xlsx — Schema Reference

Source file: `input_indexes/ApolloReelsMaster.xlsx` (24 MB)
Ingested into: `data/01b_excel.db` (12 MB SQLite)

---

## Data Model

"FR" stands for **Film Roll** in NASA archive terminology. Not all film rolls
have an `FR-` prefix, but the term applies to the entire collection.

The database separates **content** (what was filmed) from **transfers**
(known physical/digital copies of that content):

```
┌──────────────────────┐       ┌──────────────────────────────┐
│   film_rolls         │ 1───* │        transfers             │
│   (content def)      │       │  (instances on disk/tape)    │
│                      │       │                              │
│  identifier (PK)     │       │  reel_identifier (FK)        │
│  title               │       │  transfer_type               │
│  orig_title          │       │  lto_number, tape_number     │
│  date, feet, mins    │       │  filename, file_path         │
│  audio, mission      │       │  file_description, etc.      │
│  description         │       │  transfer_status             │
│  has_shotlist_pdf    │       │  creator, prime_data_tape    │
│  has_transfer_on_disk│       │  (A17 transfer props)        │
│  (enriched by MOCR   │       │  (A17 transfer props)        │
│   and Apollo 17)     │       │                              │
└──────────────────────┘       └──────────────────────────────┘
```

A **film roll** is the definition of the original content — what was shot, when,
by whom. Content metadata from the MOCR and Apollo 17 tabs is merged directly
into the film_rolls row (cleaner titles, feet, minutes, audio, description).

Properties like transfer quality, HD format, file location, creator, or
prime data tape are **not** on the film roll — they belong to a **transfer** row.

A single film roll may have zero or many transfers (LTO copy, HD dub, VRDS
reference, Discovery tape capture, digital file on disk).

---

## Source Workbook: 5 Sheets

| Sheet             | Rows   | Purpose                                                          |
| ----------------- | ------ | ---------------------------------------------------------------- |
| Master List       | 43,271 | Backbone index — every known film roll (+ merged transfer flags) |
| MOCR              | 188    | Mission Operations Control Room content detail                   |
| HD                | 631    | HD transfer records (purely transfer metadata)                   |
| 17                | 192    | Apollo 17 detailed content + file references                     |
| DiscoveryShotList | 964    | Timecoded shot descriptions for 291 compilation tapes            |

---

## Master List (43,271 rows, 25 columns)

The primary index. Every film roll in the collection has one row here. The
spreadsheet flattens content and transfer data into a single row; the
ingestion script separates them.

### Content columns → `film_rolls` table

| #   | Column           | Population     | Maps to                  |
| --- | ---------------- | -------------- | ------------------------ |
| 0   | **Identifier**   | 100% (43,271)  | `film_rolls.identifier`  |
| 3   | **Concat Title** | 100%           | `film_rolls.title`       |
| 4   | Orig Title       | 100%           | `film_rolls.orig_title`  |
| 8   | **Date**         | 97.4% (42,140) | `film_rolls.date`        |
| 11  | Description      | 0.4% (192)     | `film_rolls.description` |
| 15  | Feet             | 0.9% (378)     | `film_rolls.feet`        |
| 16  | Minutes          | 0.9% (378)     | `film_rolls.minutes`     |
| 17  | Audio            | 0.9% (378)     | `film_rolls.audio`       |
| 2   | MOCR Mission     | 1.1% (462)     | `film_rolls.mission`     |

### Derived columns (not from Excel)

| Column                 | Source                           | Description                                                                      |
| ---------------------- | -------------------------------- | -------------------------------------------------------------------------------- |
| `has_shotlist_pdf`     | PDF folder scan during 1b ingest | `1` if a matching PDF exists in `input_indexes/MASTER FR shotlist folder/`       |
| `has_transfer_on_disk` | Stage 1c directory crawl         | `1` if a verified file exists on `/o/` (set by `scripts/1c_verify_transfers.py`) |

### Transfer columns → `transfers` table

| #   | Column           | Population     | Transfer type                                                  |
| --- | ---------------- | -------------- | -------------------------------------------------------------- |
| 1   | MOCR LTO#        | 1.3% (567)     | `lto_copy` — L-number on LTO tape                              |
| 9   | VideoFile        | 26.4% (11,424) | `lto_copy` (if L-number) or `vrds_ref` (if VRDS ITEMID)        |
| 10  | Discovery Tape # | 1.0% (428)     | `discovery_capture` — film roll captured onto compilation tape |
| 14  | HD Transfer      | 1.3% (567)     | Status flag for `hd_dub`                                       |
| 18  | HD TAPENO        | 1.5% (631)     | `hd_dub` — tape number                                         |
| 19  | HD CUT           | 1.5% (631)     | `hd_dub` — cut number                                          |
| 20  | HD CUTLNGTH      | 1.5% (631)     | `hd_dub` — cut length                                          |
| 21  | Filename         | 0.4% (192)     | `digital_file` — actual video file                             |
| 22  | File Description | 0.4% (192)     | `digital_file` — format info                                   |
| 23  | File Audio       | 0.4% (192)     | `digital_file` — audio info                                    |
| 24  | Audio File       | 0.3% (147)     | `digital_file` — separate audio                                |

### Echo columns (lookup from other tabs, not separately ingested)

| #   | Column             | Population | Source        |
| --- | ------------------ | ---------- | ------------- |
| 5   | MOCR Title         | 1.1% (469) | MOCR tab      |
| 6   | HD Title           | 1.5% (631) | HD tab        |
| 7   | 17 Title           | 0.4% (192) | Apollo 17 tab |
| 12  | Concat HD Transfer | 1.3% (567) | Derived       |
| 13  | MOCR HD Trans      | 0.3% (147) | MOCR tab      |

---

## Transfer Types (12,687 total)

| Type                | Count | Source                                 | Description                                                                     |
| ------------------- | ----- | -------------------------------------- | ------------------------------------------------------------------------------- |
| `vrds_ref`          | 8,424 | VideoFile = `VRDS ITEMID: ####`        | Reference in the VRDS database                                                  |
| `lto_copy`          | 3,008 | VideoFile = `L######/...` or MOCR LTO# | Copy on an LTO tape, located by L-number                                        |
| `hd_dub`            | 635   | HD TAPENO/CUT/CUTLNGTH cols + HD tab   | HD transfer onto numbered HD tape                                               |
| `discovery_capture` | 428   | Discovery Tape # column                | Film Roll captured onto a compilation Discovery tape (many film_rolls per tape) |
| `digital_file`      | 192   | Filename column + Apollo 17 tab        | Standalone digital file (ProRes .mov / .mpg)                                    |

### Film Roll coverage

- **27.7%** of film_rolls (11,988) have at least one known transfer
- **72.3%** (31,281) have no transfer record — not yet digitised or location unknown
- **498 film_rolls** have multiple transfers (e.g. both an LTO copy and an HD dub)

---

## Identifier Patterns

| Prefix    | Count  | Example              | Origin                                  |
| --------- | ------ | -------------------- | --------------------------------------- |
| `FR-`     | 16,419 | `FR-0001`, `FR-5678` | Film Report — the core JSC film catalog |
| `JSCmSTS` | 13,109 | `JSCmSTS-006-00001`  | JSC media, Space Shuttle missions       |
| `JSCm`    | 9,448  | `JSCm-798`           | JSC media, general collection           |
| `JSC`     | 1,330  | `JSC-528`            | Johnson Space Center catalog            |
| `BRF`     | 788    | `BRF-1087`           | Briefing films                          |
| `S`       | 351    | `S847-07`            | S-series designations                   |
| `VJSC`    | 292    | `VJSC-0001`          | Video JSC collection                    |
| `CL`      | 279    | `CL-0085`            | Classification series                   |
| `CMP`     | 265    | `CMP-0001`           | Composite/compilation film_rolls        |
| `AK`      | 198    | `AK-001`             | Access copy identifiers                 |
| `JSCmND`  | 157    | `JSCmND-0001`        | JSC media, no date                      |
| `CS`      | 104    | `CS-0001`            | CS-series                               |
| `ASR`     | 97     | `ASR-0001`           | Archival storage reference              |
| `SL`      | 74     | `SL-0001`            | Skylab footage                          |
| `KSC`     | 73     | `KSC-1`              | Kennedy Space Center                    |
| `VCL`     | 60     | `VCL-0001`           | Video classification                    |
| `EC`      | 59     | `EC-0001`            | EC-series                               |
| `HQ`      | 45     | `HQ-001`             | NASA Headquarters                       |
| `LRL`     | 45     | `LRL-001`            | Lunar Receiving Laboratory              |
| numeric   | 28     | `1-8304-03`          | Legacy numeric catalog numbers          |
| other     | 48     | various              | Miscellaneous one-offs                  |

### FR- identifiers and PDF shotlists

The `FR-` prefix is the primary focus (16,419 film_rolls). These have
corresponding typewritten shotlist PDFs in `input_indexes/MASTER FR shotlist folder/`.

- 9,578 FR-numbers match a PDF on disk
- ~6,841 FR-numbers in the spreadsheet have no corresponding PDF

---

## MOCR (188 rows)

Extended **content** metadata for Mission Operations Control Room footage.
These are all FR-numbered film_rolls with detailed mission/activity information.

| #   | Column          | Population  | Description                                   |
| --- | --------------- | ----------- | --------------------------------------------- |
| 0   | **Identifier**  | 100%        | FR-number                                     |
| 1   | **Mission**     | 100%        | Apollo mission (e.g. `Apollo 7`, `Apollo 13`) |
| 2   | LTO#            | 78.2% (147) | LTO tape number → `transfers.lto_copy`        |
| 3   | **HD Transfer** | 100%        | HD transfer status → `transfers.hd_dub`       |
| 4   | **Title**       | 100%        | Activity title                                |
| 5   | **Feet**        | 100%        | Film length in feet                           |
| 6   | **Minutes**     | 100%        | Duration in minutes                           |
| 7   | **Audio**       | 100%        | Audio type (SOF/SIL/MOS)                      |

Columns 2-3 are **transfer metadata** (ingested into `transfers` table).
Columns 0-1, 4-7 are **content metadata** — merged directly into `film_rolls`
(MOCR title overwrites the Master List's concatenated title; feet/minutes/audio
fill NULLs). No separate `mocr` table.

---

## HD (631 rows)

**Purely transfer metadata.** Records which film_rolls have been dubbed to HD
and where they sit on HD tapes. All columns go to `transfers` as `hd_dub` type.

| #   | Column           | Population | Description                  |
| --- | ---------------- | ---------- | ---------------------------- |
| 0   | **Identifier**   | 100%       | FR-number                    |
| 1   | **TAPENO**       | 100%       | HD tape number               |
| 2   | **VERSIONTITLE** | 100%       | Version/title on the HD tape |
| 3   | **CUT**          | 100%       | Cut number on the tape       |
| 4   | **CUTLNGTH**     | 100%       | Cut length (timecode)        |
| 5   | **HD Transfer**  | 100%       | Transfer status              |

---

## Apollo 17 (192 rows)

Detailed index for Apollo 17 footage with both content metadata (title,
creator, date) and transfer info (filenames, file format descriptions).

| #   | Column           | Population | Maps to                                             |
| --- | ---------------- | ---------- | --------------------------------------------------- |
| 0   | **Identifier**   | 100%       | `film_rolls.identifier`                             |
| 4   | **Title**        | 100%       | → `film_rolls.title` (overwrites concatenated)      |
| 8   | **Date**         | 100%       | → `film_rolls.date`                                 |
| 9   | Description      | 100%       | → `film_rolls.description` (fills NULLs)            |
| 5   | **Feet**         | 100%       | → `film_rolls.feet` (fills NULLs)                   |
| 6   | **Minutes**      | 100%       | → `film_rolls.minutes` (fills NULLs)                |
| 7   | **Audio**        | 100%       | → `film_rolls.audio` (fills NULLs)                  |
| 10  | Creator          | 18.8%      | → `transfers.creator` (on digital_file row)         |
| 2   | Prime Data Tape  | 16.7%      | → `transfers.prime_data_tape` (on digital_file row) |
| 1   | HD Transfer      | 76.6%      | `transfers.transfer_status`                         |
| 11  | Filename         | 100%       | `transfers.filename` (digital_file)                 |
| 12  | File Description | 100%       | `transfers.file_description`                        |
| 13  | File Audio       | 100%       | `transfers.file_audio`                              |
| 14  | Audio File       | 76.6%      | `transfers.audio_file`                              |

Content columns (title, description, feet, minutes, audio) merge into `film_rolls`.
Transfer columns (creator, prime_data_tape, filename, etc.) go into `transfers`.
No separate `apollo17` table.

---

## DiscoveryShotList (964 rows, 291 tapes)

Timecoded shot descriptions for **compilation Discovery tapes**. Each tape
contains **multiple FR-numbered film_rolls**. The identifier column often lists
comma-separated FR numbers.

| #   | Column          | Population  | Description                                        |
| --- | --------------- | ----------- | -------------------------------------------------- |
| 0   | Identifier      | 84.1% (811) | FR-number(s) on this tape — may be comma-separated |
| 1   | **Tape Number** | 100%        | Discovery tape number (501–886)                    |
| 2   | **Description** | 100%        | Tape-level description                             |
| 3   | **Shotlist**    | 95.7% (923) | Multi-line timecoded shot list                     |

### Shotlist text format

```
01:00:00 Story 1: Apollo 9 Onboards, Day 5 Interiors
01:03:00 Interiors, games with weightless objects
01:05:15 EVA preparation
01:12:30 Schweickart EVA, helmet camera
```

Parsed into 4,425 individual `(timecode, description)` entries in the
`discovery_timecodes` table.

---

## Cross-Reference Map

```
film_rolls  (enriched by MOCR + Apollo 17 content metadata)
  │
  └── identifier ──────────► transfers.reel_identifier (1:many)
                                 │
                                 ├── lto_copy ──────► LTO tape by L-number
                                 ├── vrds_ref ──────► VRDS database item
                                 ├── hd_dub ────────► HD tape + cut
                                 ├── discovery_capture ──► Discovery tape (compilation)
                                 │                           │
                                 │                           └── discovery_shotlist.tape_number
                                 └── digital_file ──► file on disk

discovery_shotlist
  └── tape_number ──────────► /o/{Master N}/Tape {NNN} - Self Contained.mov
                                 (naming convention: 501–562=M1, 563–625=M2, 626–712=M3, 713–886=M4)
```

### Discovery tapes are compilation tapes

A Discovery tape (e.g. Tape 505) is a **compilation** containing multiple
original film_rolls. For example, Tape 505 contains JSC-0091, JSC-0094, JSC-0119,
and JSC-0124. The `discovery_capture` transfer links each film roll to the tape
it was captured onto. Multiple film_rolls share the same tape number and map to
the same physical `.mov` file.

- Unique compilation tapes: **291** (numbers 501–886)
- Total film roll captures on tapes: **428**
- Average film_rolls per tape: **~1.5**

### Tape-to-file mapping

Discovery tapes map to `.mov` files in four Master folders:

| Folder   | Tape Range |
| -------- | ---------- |
| Master 1 | 501–562    |
| Master 2 | 563–625    |
| Master 3 | 626–712    |
| Master 4 | 713–886    |

Expected path: `/o/{Master N}/Tape {NNN} - Self Contained.mov`

### VideoFile column formats

| Format              | Example             | Count  | Transfer type |
| ------------------- | ------------------- | ------ | ------------- |
| `L######/ID`        | `L000881/AK-001`    | ~3,000 | `lto_copy`    |
| `VRDS ITEMID: ####` | `VRDS ITEMID: 1234` | ~8,400 | `vrds_ref`    |

---

## Coverage Summary

| Metric                                | Value                  |
| ------------------------------------- | ---------------------- |
| Total film_rolls                      | 43,269                 |
| Film Rolls with at least one transfer | 11,988 (27.7%)         |
| Film Rolls with no known transfer     | 31,281 (72.3%)         |
| Film Rolls with multiple transfers    | 498                    |
| Total transfer records                | 12,687                 |
| FR-numbers with matching shotlist PDF | 9,578 / 16,419 (58.3%) |
| Discovery compilation tapes           | 291                    |
| Parsed timecoded shot entries         | 4,425                  |
