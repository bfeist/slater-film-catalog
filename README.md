# NASA Slater Catalog

AI-powered cataloging pipeline for archival US space program video footage using local GPU inference (RTX 4090).

## Goals

- Ingest and OCR existing shot list PDFs (scanned typewritten documents from the 1960s)
- Analyze video files with scene detection, visual descriptions, face detection, and OCR
- Produce a fully client-side searchable JSON catalog (no backend/database needed)
- Support incremental updates as new material is acquired

## Setup

```bash
# Install uv if not already available
# https://docs.astral.sh/uv/getting-started/installation/

# Install dependencies (includes CUDA PyTorch)
uv sync
```

## Pipeline Stages

See [docs/pipeline-plan.md](docs/pipeline-plan.md) for the full plan.

| Stage | Script                              | Status  |
| ----- | ----------------------------------- | ------- |
| 0     | `scripts/0_spot_check_marker.py`    | Done    |
| 1     | `scripts/1_ingest_shotlist_pdfs.py` | Planned |
| 1b    | `scripts/1b_ingest_excel.py`        | Planned |
| 2     | `scripts/2_parse_shotlists.py`      | Planned |
| 3     | `scripts/3_discover_videos.py`      | Planned |
| 4     | `scripts/4_analyze_video.py`        | Planned |
| 5     | `scripts/5_merge_catalog.py`        | Planned |
| 6     | `scripts/6_identify_faces.py`       | Planned |
| 7     | `scripts/7_build_search_index.py`   | Planned |
| 8     | `scripts/8_incremental_update.py`   | Planned |

## Project Structure

```
scripts/     # Numbered pipeline scripts
docs/        # Pipeline plan and documentation
data/        # All output data (gitignored)
input_indexes/  # Source shotlist PDFs
```
