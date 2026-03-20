# NASA Slater Film Catalog

Read-only catalog of ~12,000 NASA 16mm/35mm archival film reels. Users browse, search, and view metadata. Authenticated users (via `?key=SECRET` URL param → `sessionStorage.revealKey`) see real identifiers/filenames/paths; unauthenticated users see obfuscated data.

## /o/ Drive — CRITICAL SAFETY RULE

The `/o/` path (network share with archival video) is **STRICTLY READ-ONLY**.

- **NEVER** write files to `/o/`
- **NEVER** delete files from `/o/`
- **NEVER** modify files on `/o/`
- **NEVER** run any command that could alter `/o/` contents (no `mv`, `rm`, `cp ... /o/`, `rsync --delete`, etc.)
- Only use `/o/` as a **read source** for video discovery, metadata extraction, and analysis

## Stack

- **Frontend**: React 19, React Router 7, TypeScript 5 (strict), Vite 7
- **Backend**: Express 5 API, Better-SQLite3 (read-only DB), bundled with esbuild
- **UI**: Radix UI primitives + CSS Modules (camelCase enforced) + `clsx`
- **Python**: `uv` for package management. Python ≥3.11. Dependencies in `pyproject.toml`.
- **Testing**: Vitest + jsdom. Lint: ESLint + Stylelint.

## Commands

```bash
# Frontend/API
npm run dev           # Vite :9300, API :9301 (proxied via /api/*)
npm run test:all      # lint → tsc → tsc:server → build → vitest
npm run test          # vitest only
npm run lint          # eslint + stylelint

# Python scripts (always use uv)
uv run python scripts/shotlist/1a_marker_ocr.py
uv run python scripts/shotlist/1c_llm_ocr.py
uv run python scripts/shotlist/1d_build_fts_index.py
```

## Project Layout

```
src/                  # React frontend + Express server
  api/                #   API route handlers
  components/         #   React components
  pages/              #   Page-level components
  server/             #   Express server entry
  styles/             #   theme.css, global.css, CSS Modules
  lib/, utils/        #   Shared helpers
  __tests__/          #   Vitest tests

scripts/              # Python data-processing pipeline (run with uv)
  shotlist/           #   OCR pipeline: 1a → 1b → 1c → 1d
    1a_marker_ocr.py        # Marker-PDF OCR of shotlist PDFs
    1b_match_shotlist_pdfs.py  # Match PDFs to film reels
    1c_llm_ocr.py           # LLM vision OCR via Ollama (Qwen)
    1d_build_fts_index.py   # Merge OCR sources + build FTS5 index
  title_gen/          #   LLM title generation
  nara_scraper/       #   NARA metadata scraping
  files_audit/        #   File integrity auditing
  filename_parser.py  #   Reel filename parsing
  db_resolve.py       #   DB identifier resolution

docs/                 # Architecture docs, plans, schema notes
  architecture.md
  pipeline-plan.md
  excel-schema.md

database/             # SQLite DB (catalog.db) — read-only in production
data/                 # Pipeline intermediate outputs
  01_shotlist_raw/    #   Marker-PDF OCR JSON outputs
  01c_llm_ocr/       #   LLM vision OCR JSON outputs
static_assets/        # Source PDFs, etc.
  shotlist_pdfs/      #   Shotlist PDF scans
```

## /o/ Drive — CRITICAL SAFETY RULE

`/o/` is a network share with archival video. **STRICTLY READ-ONLY.** Never write, delete, or modify anything on `/o/`. No exceptions.

## Key Conventions

- CSS Module classes must be camelCase
- The `revealed` boolean gates all sensitive data — thread it through to children; never assume `true`
- Dev servers on `:9300` (Vite) and `:9301` (API) — assume already running
- Default shell: GitBash (Windows)
