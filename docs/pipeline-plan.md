# NASA Slater Catalog — Pipeline Plan

## Overview

This project builds a comprehensive searchable catalog for tens of thousands of hours of archival US space program video. The system runs entirely locally on an RTX 4090 GPU and produces a client-side-searchable JSON catalog — no backend server or database required.

## Current State of Source Material

### Video Files (on `/o/` — STRICTLY READ-ONLY)

All video lives on the `/o/` network share (mapped as `O:\` on Windows). **~68 TB** across multiple folder structures:

#### Master Tape Compilations (Self-Contained .mov)

| Folder         | Tape Range | Files  | Size   | Format                          |
| -------------- | ---------- | ------ | ------ | ------------------------------- |
| `/o/Master 1/` | 501–562    | 61     | 7.4 TB | ProRes .mov, 100–176 GB each    |
| `/o/Master 2/` | 563–625    | 61     | 7.3 TB | ProRes .mov, 100–176 GB each    |
| `/o/Master 3/` | 626–712    | 69     | 7.3 TB | ProRes .mov, 100–176 GB each    |
| `/o/Master 4/` | 713–886    | 97     | 2.6 TB | ProRes .mov, 8–48 GB each       |
| `/o/Master 5/` | (mixed)    | 14,980 | 8.8 TB | Apollo mission-specific content |

**288 tape .mov files spanning Tapes 501–886.** These are high-quality full-tape captures (Masters 1–3 use source timecode; Master 4 uses `Non Source TC`). Some tapes are split into parts (e.g., `Tape 507 - Self Contained - Part 1 Of 2.mov`). A few placeholder `.txt` files mark tapes that don't exist. Master 4 also contains a `BBC/` subfolder (2 MXF files, ~35 GB) and a `LMOTM - ARCHIVE MASTER/` subfolder (excluded from tape counts). Master 5 is a large collection of Apollo mission-specific subdirectories (Apollo 8, 11, 13, 15, 16, 17, plus misc content like 65mm scans, pool feeds, etc.) with 14,980 files across 131 subdirectories.

#### MPEG-2 Proxy Files (Low-Quality Transfers)

- **684 files** in `/o/MPEG-2/`, totaling **1.6 TB**
- Flat directory, no subdirectories
- **676 .mpg files** with two naming patterns (plus 8 non-.mpg files):
  - `L######.mpg` (396 files) — full tape rips, 2.5–3.5 GB each
  - `L######_FR-####.mpg` (280 files) — individual reel clips, ~200 MB–3 GB
- **526 unique L-numbers** (range L000003–L003219)
- These L-numbers correspond to the `VideoFile` column in the Master List spreadsheet:
  - Excel: `VideoFile = L000881/AK-001` → Disk: `O:/MPEG-2/L000881.mpg` (full tape) or `O:/MPEG-2/L000881_FR-AK-1.mpg` (individual reel)
- **11,424 Master List rows** reference L-numbers, meaning many reels share the same tape

#### Other Content

- `/o/Stephen_2025/` — **32.8 TB**, 1,280 files (848 .mov, 401 .mxf, plus misc .mp4/.wav/.ts/.m4v) across 55 subdirectories. Naming pattern: `255-S-NNNN_HD_MASTER.mov` and `255-S-NNNN_HD_UPSCALE_MASTER.mov`
- `/o/Shuttle/` — 1.9 GB, 1 file (`FR-C611 & FR-C615 - Sections synced to 255-pao-416-aad-Up to 4K.mov`)

#### Key Observations

- New material is acquired and added regularly
- Indexing is extremely poor: in many cases only a single descriptor per video file
- Multiple quality tiers exist for the same content (see Source Quality Tracking below)

### Existing Shot List PDFs

- **10,590 PDFs** in `input_indexes/MASTER FR shotlist folder/`
- Some duplicate reel numbers with date suffixes like `FR-00012012-07-17.pdf`)
- PDFs are scanned photographs of typewritten/handwritten documents from the 1960s
- Sizes range from 7.6 KB to 1.2 MB (median ~43 KB)
- Cover an estimated 10% of total video holdings
- Multiple document formats observed:
  - **Typed shot lists** (majority): Tabular format with footage start, camera angle, subject description
  - **Handwritten scene logs**: Lower OCR reliability but still partially extractable
  - **"Documentary Motion Picture Scene Log & Evaluation"** forms: Structured forms with metadata fields

### ApolloReelsMaster.xlsx Spreadsheet

A comprehensive Excel workbook with **5 tabs** containing structured metadata for the collection:

#### Master List (43,271 rows)

The primary index of all known reels. 25 columns including:

- **Identifier**: FR-XXXX reel numbers (all rows populated)
- **Concat Title**: Combined title field (all rows populated)
- **Date**: Dating information (42,140 rows)
- **VideoFile**: Video file reference in `L######/AK-###` format (11,424 rows)
- **Discovery Tape #**: Links to Discovery-era tape compilations (428 rows)
- **Filename**: Actual file paths — some point to `Tape NNN - Self Contained.mov`, others to `.mpg` files (75 rows)
- **Description**: Format description e.g. "ProRes 422 HQ 1080p", "MPEG-2 1080p"
- Other columns: MOCR LTO#, MOCR Mission, Orig Title, Source, Total Footage, Film Site, etc.
- **L-number → file mapping**: The `VideoFile` value `L000881/AK-001` maps to files on disk at `O:/MPEG-2/L000881.mpg` (full tape) or `O:/MPEG-2/L000881_FR-AK-1.mpg` (individual clip). The slash-separated second component is the reel identifier within that tape.

#### MOCR (189 rows)

Apollo Mission Operations Control Room footage:

- Columns: Identifier (FR-XXXX), Mission, LTO#, HD Transfer, Title, Feet, Minutes, Audio

#### HD (632 rows)

HD transfer records:

- Columns: Identifier, TAPENO, VERSIONTITLE, CUT, CUTLNGTH, HD Transfer

#### 17 (1,006 rows)

Apollo 17-specific detailed index:

- Columns: Identifier (AK-XXX), HD Transfer, Prime Data Tape, Tape #, Title, Feet, Minutes, Audio, Date, Description, Creator, Filename

#### DiscoveryShotList (965 rows)

Timecoded shot descriptions for Discovery Channel tape compilations:

- **291 unique tape numbers** (range 501–886)
- Each row: Identifier (FR numbers, sometimes comma-separated), Tape Number, Description, Shotlist
- Shotlist field contains detailed timecoded descriptions, e.g.: `"01:00:00 Story 1: Apollo 9 Onboards..."`
- **Tape number → file mapping**: Tape numbers correspond to files on `/o/` at paths like:
  `/o/master 1/Tape 508 - Self Contained.mov`

### Spot Check Results (marker-pdf v1.10.1, RTX 4090)

| PDF     | Type            | Size    | Processing Time | Quality                                                                                                                                 |
| ------- | --------------- | ------- | --------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| FR-0001 | Typed shot list | 46 KB   | 22.6s           | **Excellent** — camera angles (MS, LS, MCU), footage numbers, descriptions ("Mercury Capsule", "Technicians guiding") clearly extracted |
| FR-2041 | Typed shot list | 43.5 KB | 9.2s            | **Good** — reads Saturn model descriptions, footage start/end, classifications correctly                                                |
| FR-1902 | Handwritten log | 1.2 MB  | 99.8s           | **Fair** — handwritten content partially readable, form structure detected, 4 pages with images                                         |

**Conclusion**: marker-pdf with `force_ocr` mode handles the typed shot lists well. Handwritten documents will need post-processing or LLM assistance for accuracy improvement.

### Alternative Approach Evaluation (Feb 2025)

**Script**: `scripts/0b_compare_ocr_approaches.py`

Tested four approaches on the same 3 PDFs:

| Approach                       | Method                                   | FR-0001 Time | Text Accuracy                                                       | Notes                                                                                                                                                                                                           |
| ------------------------------ | ---------------------------------------- | ------------ | ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A. marker baseline**         | marker `force_ocr`                       | 22.6s        | **Accurate** — real text captured, noisy table formatting           | Current approach. All footage numbers, camera angles, descriptions present (correctly reads "Mercury Capsule", "Hanger S")                                                                                      |
| **B. marker + LLM**            | marker `force_ocr` + Ollama `gemma3:12b` | 40.9s        | **Mixed** — cleaner formatting but DROPPED shot entries (data loss) | 2× slower; LLM "cleaned" the table by removing rows it deemed noisy. Unreliable for production.                                                                                                                 |
| **C. Direct VLM (gemma3:12b)** | Page images → Ollama gemma3:12b → JSON   | 22.9s        | **HALLUCINATED** — fabricated content entirely                      | FR-0001 described as "Apollo 11 Lunar Module" (actual: Mercury Capsule). FR-2041 described as "Apollo 11 Lunar Surface Ops" (actual: Saturn table models). Completely wrong FR numbers, subjects, descriptions. |
| **C. Direct VLM (llava:7b)**   | Page images → Ollama llava:7b → JSON     | 33.2s        | **Failed** — echoed field names from prompt as template             | Too small a model; no actual content extraction                                                                                                                                                                 |

#### Key Findings

1. **marker baseline wins on accuracy**: Despite noisy markdown table output, marker correctly captures the actual text from the scanned documents. The OCR (Surya) reads "Mercury Capsule", "Technicians guiding", footage numbers (13, 21, 32, 47...) etc. faithfully from the typed originals.

2. **Local VLMs hallucinate badly on these documents**: Both gemma3:12b and llava:7b fabricate plausible-sounding but completely wrong content when given page images. This is a known problem with smaller VLMs on degraded/historical documents — they "fill in" what they expect rather than reading what's actually there. These models are **not reliable for extraction** from 1960s typewritten scans.

3. **marker + LLM mode is counterproductive for this use case**: The LLM "improves" formatting by removing rows it considers noisy, causing data loss. The 2× slowdown (40.9s vs 22.6s per PDF, → ~88 hours total) makes this impractical at scale.

4. **Handwritten documents remain unsolved locally**: Neither marker nor any tested local VLM produces usable output for FR-1902 (handwritten scene log). A capable cloud VLM (Gemini, Claude) or a larger local model (Qwen2.5-VL-72B via vLLM with quantization) would be needed.

#### Other Tools Evaluated (Not Tested)

| Tool                     | Stars | Relevance                                     | Why Not Selected                                                                                                   |
| ------------------------ | ----- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **Docling** (IBM)        | 54k   | PDF→markdown, VLM support, MIT license        | Good alternative but no evidence of better OCR on degraded historical docs; GraniteDocling VLM is only 258M params |
| **MinerU** (OpenDataLab) | 55k   | PDF→markdown/JSON, hybrid VLM+pipeline        | Requires 10GB+ VRAM for VLM mode; uses PaddleOCR under the hood; AGPL license                                      |
| **PaddleOCR**            | 71k   | Industry OCR toolkit, 111 languages, VL model | PaddleOCR-VL (0.9B) is promising but requires PaddlePaddle framework (separate from PyTorch ecosystem)             |
| **docTR** (Mindee)       | 5.9k  | PyTorch OCR with detection+recognition        | Scene text focused; no table structure understanding                                                               |
| **Tesseract**            | —     | Classic OCR engine                            | Fast but no layout/table understanding; same accuracy tier as Surya for typed content                              |

#### Decision: Keep marker-pdf for Stage 1

**marker-pdf with `force_ocr` is the right choice for Stage 1.** Rationale:

- **Accurate raw OCR** on typed documents (the vast majority of the 10,590 PDFs)
- **Already installed and tested** — no new dependencies or framework conflicts
- **15s/PDF average** is acceptable (44 hrs single-worker, reducible with `--workers`)
- The noisy table formatting is a Stage 2 problem (LLM-based parsing), not a Stage 1 problem
- Surya OCR supports finetuning if accuracy needs improvement on specific document types (see `surya/scripts/finetune_ocr.py`)

**For handwritten documents**: defer to Stage 2 — flag PDFs where marker output is low-confidence or low-character-count, then re-process those through a cloud VLM API (Gemini Flash is fast/cheap) or a better local model if one becomes available. Do NOT use local VLMs (gemma3, llava) for this — they hallucinate.

#### Chunked LLM Post-Processing (Tested Feb 2025)

**Script**: `scripts/0b_compare_ocr_approaches.py`

The original marker + LLM test (approach B) dropped whole shot entries because the LLM processed the full page at once and "cleaned" away rows. We tested sending the raw marker OCR output to an LLM in **small chunks** (3, 5, or 10 table rows at a time) to prevent this.

**Models tested**: gemma3:12b (8.1 GB), qwen3:14b (9.3 GB), gemma3:27b (17 GB)

| PDF         | Approach               | Time   | Recall  | Notes                                                                  |
| ----------- | ---------------------- | ------ | ------- | ---------------------------------------------------------------------- |
| FR-0001     | baseline marker        | 29s    | 93.8%   | Missed footage 70 (OCR noise)                                         |
| FR-0001     | gemma3:12b chunk3      | 21s    | **100%**| Recovered all 16 shots — best result                                   |
| FR-0001     | gemma3:12b chunk10     | 10s    | **100%**| Same recall, faster                                                    |
| FR-0001     | gemma3:27b chunk10     | 99s    | **100%**| Too slow — spills to CPU on Windows (24GB VRAM needed)                 |
| FR-0001     | qwen3:14b             | >4min  | —       | Chain-of-thought overhead made it impractically slow                    |
| FR-2041     | baseline marker        | 53s    | 80.0%   | Missed 4 footages: OCR read `5t)` as 5, `1.64` as 1, `T80` as 1      |
| FR-2041     | gemma3:12b chunk10     | 37s    | 85.0%   | Only +1 recovered; OCR *number* errors can't be fixed from text alone  |
| FR-2041     | gemma3:12b chunk3      | 45s    | 70.0%   | Worse — smaller chunks lost context, introduced false positives        |

**Conclusions**:

1. **Chunked LLM helps on clean typed documents** (FR-0001: 93.8% → 100%) where the text is correct but formatting is messy. The LLM successfully merges split columns and removes noise without dropping rows.

2. **Chunked LLM does NOT fix OCR number errors** (FR-2041: 80% → 85%). When Surya misreads `50` as `5t)` or `180` as `T80`, the LLM has no way to know the correct number from a 10-row text chunk alone. These errors are better handled in Stage 2 where the LLM can use sequential footage patterns and document structure as context.

3. **gemma3:12b is the only viable local model**: gemma3:27b spills to CPU on Windows (RTX 4090 has 24GB but Windows reserves ~6GB). qwen3:14b uses chain-of-thought reasoning that adds massive latency for a simple text-cleanup task.

4. **Not worth adding to Stage 1**: The marginal accuracy gain (+5% on average) doesn't justify doubling the processing time (10,590 PDFs × ~30s extra ≈ 88 additional hours). The baseline marker output is faithful to the source — the noisy formatting and OCR number errors are better resolved in Stage 2 LLM parsing where the full document context is available.

---

## Pipeline Architecture

All scripts live in `/scripts/` and are numbered to reflect pipeline stages. All intermediate and output data goes in `/data/` (gitignored). The catalog is built as JSON files that can be served statically to a React front-end with client-side search.

### Stage 0: Spot Check & Validation (DONE)

**Script**: `scripts/0_spot_check_marker.py`

Validates marker-pdf OCR quality on representative PDFs.

### Stage 1: Ingest Existing Shot List PDFs

**Script**: `scripts/1_ingest_shotlist_pdfs.py`

Batch-process all 10,590 FR shot list PDFs through marker-pdf:

- Use `force_ocr` mode (these are scanned images, not digital text)
- Output: one JSON file per PDF in `data/01_shotlist_raw/`
- Track processing status in `data/01_shotlist_raw/_manifest.json`
- Deduplicate: when multiple date-variant PDFs exist for the same FR number, keep the best quality (most text extracted)
- Incremental: skip already-processed PDFs on re-run
- Estimated time: ~15s/PDF average × 10,590 PDFs ≈ **44 hours** (single worker on RTX 4090)

### Stage 1b: Ingest Excel Spreadsheet Data

**Script**: `scripts/1b_ingest_excel.py`

Parse all 5 tabs of `input_indexes/ApolloReelsMaster.xlsx` into a **SQLite database**. The source Excel is 24 MB and has 43,271+ rows — JSON would inflate this significantly due to repeated key names on every row. SQLite keeps the interim data compact (~5–10 MB expected), queryable, and zero-infrastructure:

- **master_list** table (43,271 rows): FR identifiers, titles, dates, video file references, descriptions. This is the backbone index — every FR number in the catalog should appear here.
- **mocr** table (189 rows): Apollo MOCR activity records. Cross-reference by FR identifier.
- **hd_transfers** table (632 rows): HD transfer records with tape numbers and cuts. Cross-reference by identifier.
- **apollo17** table (1,006 rows): Apollo 17 detailed index with AK-XXX identifiers and filenames.
- **discovery_shotlist** table (965 rows): Timecoded shot descriptions for 291 Discovery tapes. Parse the Shotlist text field to extract individual timecoded entries. Map tape numbers to video files on `/o/` (e.g., Tape 508 → `/o/master 1/Tape 508 - Self Contained.mov`).
- **tape_to_file_map** table: Discovery tape number → file path mapping (derived).
- **\_manifest** table: processing metadata and timestamp.

- Output: `data/01b_excel.db` (single SQLite file)

Why SQLite over JSON for this stage:

- **Size**: ~5–10 MB vs. ~50–80 MB as JSON (key names repeated 43K times)
- **Queryable**: downstream stages can `SELECT` only the columns/rows they need instead of loading everything into memory
- **Atomic writes**: no partial-write corruption risk across multiple files
- **Still portable**: single file, no server, `sqlite3` available everywhere
- JSON remains the output format for the final catalog (Stage 5+) where per-reel files are small and browser-loadable

### Stage 2: Parse & Normalize Shot List Data

**Script**: `scripts/2_parse_shotlists.py`

Convert raw marker-pdf markdown/JSON output into structured shot list records:

- Extract structured fields: FR number, footage start, camera angle, subject description, source, film site, date, classification, material type, total footage
- Handle the two main document formats (typed shot list vs. scene log form)
- Output: `data/02_shotlists_parsed/{FR-XXXX}.json` — one normalized JSON per reel
- Schema per shot entry:
  ```json
  {
    "fr_number": "FR-0001",
    "footage_start": 13,
    "footage_end": 21,
    "camera_angle": "MS",
    "description": "Technician guiding Mercury Capsule over to mount dolly.",
    "category": "Facilities & Support Activities, Spacecraft - Mercury",
    "source": "Unknown",
    "film_site": null,
    "classification": "UN",
    "material": "ECN",
    "total_footage": 207
  }
  ```

### Stage 3: Video File Discovery & Registration

**Script**: `scripts/3_discover_videos.py`

Scan the network share to build a registry of all video files:

> **⚠️ CRITICAL: The `/o/` network share is STRICTLY READ-ONLY.**
> Scripts must NEVER write, delete, or modify any files on `/o/`. Only read operations (listing, stat, ffprobe, frame extraction to local `data/` directory) are permitted.

- Walk directory tree on `/o/`, collect: path, filename, size, modification date
- **Run `ffprobe -v quiet -print_format json -show_format -show_streams`** on every video file and store the full JSON output — this preserves all technical metadata (codec, bitrate, resolution, frame rate, color space, audio channels, etc.) per file
- Derive a human-readable **quality tier** label from the ffprobe data for general searching (see Source Quality Tracking below)
- Extract FR number from filename where possible
- Map DiscoveryShotList tape numbers to actual files (e.g., `Tape 508` → `/o/Master 1/Tape 508 - Self Contained.mov`)
- Map L-numbers from Master List `VideoFile` column to files in `/o/MPEG-2/` (e.g., `L000881/AK-001` → `/o/MPEG-2/L000881.mpg`)
- Link to existing shot list data from Stage 2 and Excel data from Stage 1b
- Output: `data/03_video_registry.json`
- Incremental: detect new/changed files since last scan

### Stage 4: Video Scene Analysis (GPU-Intensive)

**Script**: `scripts/4_analyze_video.py`

The core GPU pipeline — analyze each video file to extract scene metadata. This is the "scan once, extract everything" pass:

#### 4a. Shot Boundary Detection

- Use scene change detection (e.g., PySceneDetect or custom threshold-based approach)
- Detect cuts, dissolves, fades
- Establishes the temporal structure of the video
- Output: list of shot boundaries with timestamps

#### 4b. Keyframe Extraction

- Extract 1-3 representative keyframes per detected shot
- Save as JPEG thumbnails in `data/04_keyframes/{FR-XXXX}/`
- These serve double duty: visual browsing and input for further analysis

#### 4c. Visual Content Description

- Process keyframes through a vision-language model (e.g., LLaVA, CogVLM, or similar that runs on RTX 4090)
- Generate natural language descriptions of each shot
- Prompt tuned for space program content: "Describe what you see in this frame from NASA archival footage..."
- **Sampling interval**: Every detected shot (not fixed time interval) — this naturally adapts to content density

#### 4d. Face Detection & Embedding

- Run face detection on keyframes (e.g., RetinaFace, MTCNN)
- Extract face embedding vectors (e.g., ArcFace/InsightFace)
- Save face crops and embeddings — **do NOT attempt identification yet**
- Store as: `data/04_faces/{FR-XXXX}/{shot_id}_{face_idx}.jpg` + embedding vectors
- Face ID assignment happens later in Stage 6 when reference photos are available

#### 4e. OCR on Frames

- Run OCR on keyframes to capture any on-screen text (slates, title cards, captions, signage)
- This is separate from the PDF OCR — this captures in-video text

**Output per video**: `data/04_analysis/{FR-XXXX}.json`

```json
{
  "fr_number": "FR-0001",
  "video_path": "//server/share/path/to/FR-0001.mp4",
  "duration_seconds": 420,
  "shots": [
    {
      "shot_id": 0,
      "start_time": 0.0,
      "end_time": 12.5,
      "keyframe_paths": ["04_keyframes/FR-0001/shot_000_kf0.jpg"],
      "description": "Wide shot of Mercury capsule being lowered by crane in hangar...",
      "on_screen_text": ["HANGER S", "NASA"],
      "faces": [
        {
          "bbox": [120, 80, 200, 190],
          "embedding_path": "04_faces/FR-0001/shot_000_face_0.npy",
          "confidence": 0.97,
          "identity": null
        }
      ]
    }
  ]
}
```

### Stage 5: Merge & Reconcile

**Script**: `scripts/5_merge_catalog.py`

Combine all data sources into a unified catalog:

- Merge Stage 1b (Excel metadata), Stage 2 (parsed shot lists), and Stage 4 (video analysis)
- Incorporate DiscoveryShotList timecoded descriptions as an additional layer
- Align shot list footage numbers with detected shot boundaries
- Resolve conflicts (shot list description vs. AI description vs. Excel metadata — keep all, flag discrepancies)
- Flag gaps: videos with no shot list, shot lists with no matching video
- Output: `data/05_catalog/{FR-XXXX}.json` — one comprehensive record per reel

### Stage 6: Face Identification (Deferred/Incremental)

**Script**: `scripts/6_identify_faces.py`

When reference photos become available:

- Ingest reference photos of astronauts and historical figures
- Extract embeddings from reference photos (same model as Stage 4d)
- Compare stored face embeddings against reference set
- Assign tentative identities above a confidence threshold
- Store reference embeddings in `data/06_face_references/`
- This step can be re-run as new reference photos are added — it only updates identity labels, never re-scans video

### Stage 7: Build Search Index

**Script**: `scripts/7_build_search_index.py`

Generate multiple search indices for the client-side catalog. The search needs to support use cases we can't fully anticipate — users may search by concept, person, reel number, shot description, mission, date range, camera angle, or free-form natural language.

#### 7a. Semantic Search Index (all-MiniLM-L6-v2)

Embed all textual content using **all-MiniLM-L6-v2** (384-dim vectors, fast, good quality):

- Embed every unique text field that a user might search against:
  - Shot descriptions (from PDFs)
  - AI-generated scene descriptions (from Stage 4c)
  - Concat titles (from Master List)
  - DiscoveryShotList timecoded descriptions
  - On-screen text (OCR from video frames)
  - Face identity labels (when available)
- Store as: `data/07_search_index/embeddings_{field}.bin` + ID mapping
- At query time, embed the user's query with the same model and find nearest neighbors
- **This is the primary search mechanism** — handles concept search ("astronaut training"), person search ("Cernan"), equipment search ("lunar rover"), etc.

#### 7b. Keyword / Faceted Index

Structured indices for exact-match and faceted filtering:

- **Inverted text index**: tokenized keyword search across all text fields
- **FR number index**: direct lookup by reel identifier
- **Date index**: range queries on dates
- **Mission index**: faceted filter by Apollo mission, Gemini, Shuttle, ISS, etc.
- **Quality tier index**: filter by available source quality
- **Tape number index**: lookup by Discovery/Master tape number
- **L-number index**: lookup by MPEG-2 L-number

#### 7c. Output Structure

- Output: `data/07_search_index/`
  - `catalog.json` — full catalog data
  - `embeddings_descriptions.bin` — MiniLM-L6-v2 vectors for descriptions
  - `embeddings_titles.bin` — vectors for titles
  - `keyword_index.json` — inverted keyword index
  - `facets.json` — faceted filter metadata (missions, dates, quality tiers)
  - `id_map.json` — maps vector indices to catalog entry IDs
- These files are designed to be loaded by a React app for fully client-side search (no backend needed)

#### Search Strategy Notes

> **Iterative approach**: The exact set of indices and their structure will be refined once we generate real data from the pipeline and can test actual search queries. The initial implementation should prioritize:
>
> 1. all-MiniLM-L6-v2 semantic search over concatenated description text (covers the broadest range of queries)
> 2. Exact FR-number / tape-number lookup (for known-item search)
> 3. Date range filtering
>
> Additional specialized indices (per-field embeddings, cross-references, etc.) will be added based on real usage patterns. The architecture supports multiple index files loaded independently, so we can add new search dimensions without rebuilding everything.

### Stage 8: Incremental Update

**Script**: `scripts/8_incremental_update.py`

Orchestrator for processing new material:

- Re-run Stage 3 to discover new videos
- Process only new/changed videos through Stage 4
- Re-run Stage 5 merge
- Re-run Stage 7 search index build
- Manual trigger (not automated/scheduled)

---

## Key Design Decisions

### Why JSON Files Instead of a Database

- **No backend required**: The React front-end loads JSON directly
- **Git-friendly**: Easy to version, diff, and inspect (though large files go in .gitignore)
- **Portable**: Just files on disk, no database server to maintain
- **Incremental**: Each reel is its own JSON file — easy to update one without touching others
- **Searchable client-side**: Pre-built search indices load into browser memory

### Video Sampling Strategy

Rather than sampling at fixed time intervals (e.g., every 5 seconds), the pipeline uses **shot boundary detection** to naturally segment video:

- Avoids redundant analysis of static shots
- Captures every meaningful visual change
- Adapts to content density (a 30-second static shot gets 1 keyframe; a 5-second montage gets multiple)
- Typical archival footage: ~2-10 shots per minute → ~3-15 keyframes per minute

### Face Detection vs. Identification Separation

Face detection/embedding (Stage 4d) is separated from identification (Stage 6) because:

- Video only needs to be scanned once
- Reference photo collection can grow over time
- Re-identification is cheap (just vector comparisons)
- Avoids having to re-scan video when new reference faces are added

### Source Quality Tracking

The same reel content may exist at multiple quality levels, and the catalog must track what's available:

| Quality Tier     | Source                     | Typical Format      | Size/hr  | Notes                                   |
| ---------------- | -------------------------- | ------------------- | -------- | --------------------------------------- |
| **Master**       | `/o/Master 1-4/` Tape .mov | ProRes 422 HQ 1080p | ~100+ GB | Best available. Full-tape captures.     |
| **HD Transfer**  | Listed in HD/MOCR tabs     | ProRes/DNxHD        | varies   | Subset of reels with HD transfers       |
| **MPEG-2 Proxy** | `/o/MPEG-2/` L-number .mpg | MPEG-2 1080p        | ~2-3 GB  | Lower quality but individual reel clips |
| **Stephen HD**   | `/o/Stephen_2025/`         | HD Master .mov/.mxf | varies   | 32.8 TB total, 848 .mov + 401 .mxf      |

Each catalog entry carries a `sources` array with both the **human-readable quality tier** (for general searching) and the **raw ffprobe output** (for exact technical queries):

```json
{
  "fr_number": "FR-0001",
  "sources": [
    {
      "quality_tier": "master",
      "quality_label": "ProRes 422 HQ 1080p",
      "path": "/o/Master 1/Tape 508 - Self Contained.mov",
      "tape_number": 508,
      "timecode_in": "01:23:45:00",
      "timecode_out": "01:30:12:15",
      "file_size_bytes": 178487713792,
      "ffprobe": {
        "format": {
          "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
          "duration": "3612.480000",
          "bit_rate": "395182891"
        },
        "streams": [
          {
            "codec_type": "video",
            "codec_name": "prores",
            "profile": "HQ",
            "width": 1920,
            "height": 1080,
            "r_frame_rate": "30000/1001",
            "pix_fmt": "yuv422p10le",
            "bits_per_raw_sample": "10",
            "color_space": "bt709"
          },
          {
            "codec_type": "audio",
            "codec_name": "pcm_s24le",
            "sample_rate": "48000",
            "channels": 2
          }
        ]
      }
    },
    {
      "quality_tier": "mpeg2_proxy",
      "quality_label": "MPEG-2 1080p",
      "path": "/o/MPEG-2/L000881_FR-0001.mpg",
      "l_number": "L000881",
      "file_size_bytes": 367884288,
      "ffprobe": {
        "format": {
          "format_name": "mpeg",
          "duration": "245.600000",
          "bit_rate": "11984000"
        },
        "streams": [
          {
            "codec_type": "video",
            "codec_name": "mpeg2video",
            "width": 1920,
            "height": 1080,
            "r_frame_rate": "30000/1001"
          }
        ]
      }
    }
  ],
  "best_available_quality": "master"
}
```

The `quality_tier` and `quality_label` fields enable common-language searching ("show me everything in HD", "which reels only have MPEG-2 proxies"). The raw `ffprobe` object preserves exact technical detail per file (codec profile, bitrate, color space, audio channels, etc.) for specialized queries.

The pipeline should prefer the highest quality source for analysis (Stage 4) but track all available sources so the front-end can display what's available and what quality level was analyzed.

### Incremental Processing

Every stage is designed to be re-runnable and incremental:

- Manifest files track what's been processed
- New material is detected by comparing against the manifest
- Only new/changed items are processed
- The merge and search index stages are fast enough to rebuild entirely

---

## Technology Stack

| Component             | Library                                      | Purpose                                     |
| --------------------- | -------------------------------------------- | ------------------------------------------- |
| Package management    | **uv**                                       | Fast Python dependency management           |
| PDF OCR               | **marker-pdf** (v1.10.2)                     | OCR scanned shotlist PDFs → structured text |
| PDF backup (LLM)      | **Qwen2-VL** / **InternVL** (TBD)            | Multimodal LLM fallback for difficult PDFs  |
| Excel ingestion       | **openpyxl**                                 | Parse ApolloReelsMaster.xlsx spreadsheet    |
| Interim data store    | **sqlite3** (stdlib)                         | Compact queryable storage for parsed Excel  |
| Deep learning         | **PyTorch** (cu126)                          | GPU inference backbone                      |
| Scene detection       | **PySceneDetect** / custom                   | Shot boundary detection in video            |
| Video processing      | **ffmpeg** / **ffprobe**                     | Video metadata, keyframe extraction         |
| Vision-language model | **LLaVA** / **CogVLM** (TBD)                 | Scene description from keyframes            |
| Face detection        | **InsightFace** / **RetinaFace**             | Face detection and embedding                |
| OCR (video frames)    | **surya** (via marker) or **EasyOCR**        | In-video text extraction                    |
| Text embeddings       | **all-MiniLM-L6-v2** (sentence-transformers) | Semantic search vectors (384-dim)           |
| Front-end (future)    | **React**                                    | Client-side search UI                       |

---

## Data Directory Structure

```
data/
├── 01_shotlist_raw/          # Raw marker-pdf output per PDF
│   ├── FR-0001.json
│   ├── FR-0001.md
│   └── _manifest.json
├── 01b_excel.db                # Parsed Excel data (SQLite)
├── 02_shotlists_parsed/      # Normalized shot list records
│   ├── FR-0001.json
│   └── _manifest.json
├── 03_video_registry.json    # All discovered video files
├── 04_analysis/              # Per-video AI analysis results
│   └── FR-0001.json
├── 04_keyframes/             # Extracted keyframe images
│   └── FR-0001/
│       └── shot_000_kf0.jpg
├── 04_faces/                 # Detected face crops + embeddings
│   └── FR-0001/
│       └── shot_000_face_0.npy
├── 05_catalog/               # Merged comprehensive catalog
│   └── FR-0001.json
├── 06_face_references/       # Reference photos + embeddings
│   ├── astronauts/
│   └── _reference_index.json
├── 07_search_index/          # Client-side search files
│   ├── catalog.json
│   ├── embeddings_descriptions.bin
│   ├── embeddings_titles.bin
│   ├── keyword_index.json
│   ├── facets.json
│   └── id_map.json
└── marker_spot_checks/       # Stage 0 spot check outputs
```

---

## Estimated Processing Times (RTX 4090)

| Stage              | Items       | Est. Per Item           | Total     |
| ------------------ | ----------- | ----------------------- | --------- |
| 1. PDF OCR         | 10,590 PDFs | ~15s                    | ~44 hours |
| 1b. Excel ingest   | 5 tabs      | seconds                 | < 1 min   |
| 3. Video discovery | All files   | seconds                 | minutes   |
| 4. Video analysis  | TBD videos  | ~5-15 min/hour of video | TBD       |
| 5. Merge           | All reels   | ms                      | seconds   |
| 7. Search index    | All reels   | ms                      | seconds   |

The bottleneck is Stage 4 (video analysis). For tens of thousands of hours, this will take **weeks to months** of continuous GPU time. This is expected and the pipeline is designed for it — progress is saved per-video, and the process can be stopped and resumed at any time.

---

## Next Steps

1. **Stage 1b**: Ingest ApolloReelsMaster.xlsx (quick win — structured data, minutes of work)
2. **Stage 1**: Batch-process all shotlist PDFs through marker-pdf (~22 hours GPU time)
3. **Stage 2**: Build the shot list parser (will need user input on document format nuances)
4. Discuss existing catalog information in detail (user mentioned "a lot of nuance")
5. **Stage 3**: Set up video discovery on `/o/` (READ-ONLY scan of network share)
6. Evaluate vision-language models for Stage 4c and multimodal LLM backup for Stage 1
