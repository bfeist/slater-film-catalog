# Semantic Search Research — NASA Slater Catalog

## Current State

**Search today:** LIKE-based substring matching on `identifier`, `title`, `description`, and `mission` columns in SQLite. The Express API server (`src/server/`) handles all `/api/*` requests, backed by `better-sqlite3`. This is pure keyword matching — searching "lunar landing footage" won't find a reel titled "Apollo 11 descent to surface."

**Data scale:**
| Corpus | Row count | Text quality |
|---|---|---|
| `film_rolls.title` | 43,269 | Every row; avg 56 chars — **primary corpus** |
| `film_rolls.description` | 192 | Effectively empty (Apollo 17 only) |
| `film_rolls.mission` | ~462 | Short mission names |
| `discovery_shotlist.shotlist_raw` | 923 | Rich multi-line timecoded narratives |
| `discovery_timecodes.description` | 4,425 | Short per-shot descriptions |
| OCR'd shotlist PDFs | ~100 processed / 9,579 matched | Structured shot categories & subjects |

**Stack:** React SPA (Vite build) + Express API server + `better-sqlite3`. In dev, Vite proxies `/api/*` to Express on port 3001. In production, Express serves the built SPA and the API from a single process. Designed for Docker deployment.

**Deployment paths (video archive):**
| Environment | Archive path | Config |
|---|---|---|
| Windows dev (GitBash) | `O:\` or `\\192.168.0.6\NASA Archive` | Default on win32 |
| Docker on archive server | `/archive` (bind-mount) | `VIDEO_ARCHIVE_ROOT=/archive` |
| Docker elsewhere | `/archive` (NFS/CIFS mount) | `VIDEO_ARCHIVE_ROOT=/archive` |

---

## The Problem

Keyword search fails on intent. Real user queries hit these walls:

| User types                      | Wants                             | Keyword match finds                    |
| ------------------------------- | --------------------------------- | -------------------------------------- |
| "spacewalk footage"             | EVA reels                         | Nothing (no row says "spacewalk")      |
| "rocket launch pad"             | KSC launch complex footage        | Only if "launch pad" appears literally |
| "astronaut training underwater" | Neutral buoyancy lab footage      | Nothing                                |
| "lunar module assembly"         | Grumman factory / LM construction | Only exact substring hits              |

Semantic search maps both query and document text into a shared vector space where **meaning** is compared, not characters.

---

## Options Evaluated

### Option A: Server-Side Embeddings via sqlite-vec

**How it works:**

1. **Build time (Python):** Encode all titles/descriptions with `all-MiniLM-L6-v2` → store embeddings directly in SQLite via the [sqlite-vec](https://github.com/asg017/sqlite-vec) extension
2. **Query time (Express server):** Embed the user's query server-side using ONNX Runtime (`onnxruntime-node`), then run a single SQL query that combines vector similarity with standard SQL filters

```sql
CREATE VIRTUAL TABLE film_rolls_vec USING vec0(
    embedding float[384]
);
-- Query: vector similarity + SQL filters in one shot
SELECT fr.identifier, fr.title, v.distance
FROM film_rolls_vec v
JOIN film_rolls fr ON fr.rowid = v.rowid
WHERE v.embedding MATCH ?  -- bind the query vector
  AND fr.id_prefix = 'FR'
ORDER BY v.distance
LIMIT 20;
```

**Pros:**

- Everything stays in SQLite — single database file, easy to deploy in Docker
- Can combine vector similarity with SQL filters (prefix, date, has_transfer) in one query
- No browser-side model download (~30 MB ONNX + ~33 MB embeddings saved)
- Server-side ONNX inference is fast (~50ms per query) and works in Docker
- Query results are instant — no cold-start model loading for the user

**Cons:**

- `sqlite-vec` is a native SQLite extension — must be compiled/installed per platform
- Adds `onnxruntime-node` (~40 MB) to the server's `node_modules`
- Embedding model files (~30 MB) live on the server
- Less mature than FTS5

**Verdict:** ✅ **Now the recommended approach.** With a real Express server and Docker deployment, the original objections ("no server") no longer apply. This gives the best UX — instant semantic results with zero client overhead.

### Option B: SQLite FTS5 (Full-Text Search)

**How it works:**
SQLite ships with [FTS5](https://www.sqlite.org/fts5.html), a built-in full-text search engine that supports tokenized matching, BM25 ranking, prefix queries, and phrase matching.

```sql
CREATE VIRTUAL TABLE film_rolls_fts USING fts5(
    identifier, title, description, mission,
    content='film_rolls', content_rowid='rowid'
);
-- Query:
SELECT * FROM film_rolls_fts WHERE film_rolls_fts MATCH 'lunar module' ORDER BY rank;
```

**Pros:**

- Near-zero added dependency (FTS5 is compiled into `better-sqlite3` by default)
- Instant to implement — just create the virtual table and change the query
- BM25 ranking is a massive upgrade over LIKE for relevance
- Supports AND/OR/NOT/phrase/prefix queries
- Works for identifier lookups too ("FR-1005")

**Cons:**

- Still keyword-based — "spacewalk" won't match "EVA"
- No understanding of synonyms or intent
- Requires `better-sqlite3` at runtime (fine for dev server, needs thought for production)

**Verdict:** ✅ **Quick win to implement immediately.** Should be added regardless of whether semantic search is also added — it's the correct baseline for text search in the Express API.

### Option C: Hybrid — FTS5 + Server-Side Vector Search

**How it works:**
Combine Options A and B. The Express API handles both in a single request:

1. **Keyword mode (FTS5):** Fast, exact, great for identifiers and known terms
2. **Semantic mode (sqlite-vec):** Intent-based, great for natural language questions

The API endpoint merges results with reciprocal rank fusion or returns them in separate sections ("Exact matches" / "Related reels"). The frontend just calls one endpoint.

**Verdict:** ✅ **Best of both worlds.** This is the recommended end-state architecture. FTS5 is a quick win; sqlite-vec layers on top — both server-side, zero client impact.

### Option D: Client-Side Embeddings via transformers.js (original plan)

**How it works:**
Pre-compute embeddings at build time, ship ~33 MB of embeddings + ~30 MB ONNX model to the browser, run inference client-side.

**Pros:**

- Zero server load for search queries

**Cons:**

- ~66 MB download before semantic search works
- Bad mobile experience
- Now unnecessary since we have a server

**Verdict:** ❌ **Superseded by Option A.** With a real Express server, there's no reason to push this cost to the client.

### Option E: Pre-computed Synonym/Expansion Table

**How it works:**
At build time, use an LLM or thesaurus to expand each title into additional search terms:

| Original title                 | Expanded terms                                     |
| ------------------------------ | -------------------------------------------------- |
| "Apollo 11 descent to surface" | lunar landing, moon landing, LM descent, touchdown |
| "EVA 1 site preparation"       | spacewalk, extravehicular activity, moonwalk       |

Store expansions in a `search_terms` FTS5 table. Keyword search automatically hits synonyms.

**Pros:**

- No runtime model needed
- Works with FTS5 (no new runtime dependency)
- Can be very targeted for NASA/space domain vocabulary

**Cons:**

- Build-time LLM cost for 43K rows (one-time, ~$2-5 with GPT-4o-mini)
- Expansion quality is uneven — need manual review for key terms
- Doesn't generalize to arbitrary queries the way embeddings do

**Verdict:** ⚠️ **Good complement to FTS5 but not a replacement for real semantic search.** Worth considering as an enhancement if client-side model loading is a concern.

---

## Recommended Implementation Plan

### Phase 1: FTS5 (days, not weeks)

1. Add an FTS5 virtual table to the SQLite ingest script (1b or a new 1f):
   ```sql
   CREATE VIRTUAL TABLE IF NOT EXISTS film_rolls_fts USING fts5(
       identifier, title, description, mission,
       content='film_rolls', content_rowid='rowid'
   );
   INSERT INTO film_rolls_fts(film_rolls_fts) VALUES('rebuild');
   ```
2. Update `src/server/routes/reels.ts` — when `q` is present, use FTS5 MATCH with BM25 ranking instead of LIKE.
3. No frontend changes needed (same API shape, just better results).

**Effort:** ~2 hours. Immediate quality-of-life improvement.

### Phase 2: Server-Side Semantic Search (1-2 weeks)

1. **Adapt `scripts/6_build_search_index.py`** to read from SQLite and write embeddings back into the DB:
   - Extract `title`, `description`, `discovery shotlist_raw`, etc. from the database
   - Concatenate available text per reel into a search document
   - Generate embeddings with `all-MiniLM-L6-v2`
   - Store embeddings in a `film_rolls_vec` table via sqlite-vec

2. **Add ONNX inference to the Express server:**
   - `npm install onnxruntime-node`
   - Download the ONNX model for `all-MiniLM-L6-v2` (~30 MB) into `data/models/`
   - Create `src/server/services/embeddings.ts` — loads model once, provides `embed(text) → Float32Array`

3. **Add `/api/search` endpoint** in `src/server/routes/search.ts`:
   - Accepts `q` (query text), plus optional filters (prefix, has_transfer, etc.)
   - Embeds the query server-side (~50ms)
   - Runs sqlite-vec similarity search combined with FTS5 keyword search
   - Returns merged, ranked results

4. **Update the frontend** to call the new unified search endpoint.

**Docker considerations:**

- sqlite-vec ships as a prebuilt `.so`/`.dll` — install via `npm install sqlite-vec`
- ONNX Runtime has prebuilt binaries for linux-x64 (Docker) and win32-x64 (dev)
- Model files can be baked into the Docker image or volume-mounted

### Phase 3: Enrichment (ongoing)

- Process remaining ~9,479 shotlist PDFs → dramatically richer search corpus
- Concatenate shotlist text into reel descriptions before embedding
- Consider LLM-generated summaries for reels that currently have only a title
- Periodic index rebuilds as new data is added

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    BUILD TIME (Python)                    │
│                                                          │
│  SQLite DB ──▶ Extract text ──▶ sentence-transformers    │
│                 per reel          (all-MiniLM-L6-v2)     │
│                                        │                 │
│                                        ▼                 │
│                              sqlite-vec embeddings       │
│                              stored in catalog.db        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              RUNTIME (Express + React SPA)                │
│                                                          │
│  Browser ──▶ React SPA (.local/vite/dist)                │
│     │                                                    │
│     └──▶ /api/* ──▶ Express (port 3001)                  │
│                        │                                 │
│                        ├── FTS5 keyword search            │
│                        │                                 │
│           query text ──┤                                 │
│                        │  embed via                      │
│                        │  onnxruntime-node               │
│                        │        │                        │
│                        │        ▼                        │
│                        └── sqlite-vec similarity search   │
│                                                          │
│               Merge / rank ──▶ JSON response              │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    DOCKER DEPLOYMENT                      │
│                                                          │
│  express (serves SPA + API on one port)                   │
│  volumes:                                                │
│    /app/database/catalog.db  ← SQLite database            │
│    /archive                  ← NASA video archive share   │
└─────────────────────────────────────────────────────────┘
```

---

## Files to Change

| Phase | File                                                          | Change                                                    |
| ----- | ------------------------------------------------------------- | --------------------------------------------------------- |
| 1     | `scripts/1b_ingest_excel.py` or new `scripts/1f_build_fts.py` | Add FTS5 virtual table                                    |
| 1     | `src/server/routes/reels.ts`                                  | Use FTS5 MATCH when `q` is present                        |
| 2     | `scripts/6_build_search_index.py`                             | Refactor to read from SQLite, write sqlite-vec embeddings |
| 2     | `package.json`                                                | Add `onnxruntime-node`, `sqlite-vec`                      |
| 2     | `src/server/services/embeddings.ts` (new)                     | Server-side ONNX embedding inference                      |
| 2     | `src/server/routes/search.ts` (new)                           | Unified search endpoint (FTS5 + vector)                   |
| 2     | `data/models/`                                                | ONNX model files for all-MiniLM-L6-v2                     |

---

## Key Decisions Needed

1. **Phase 1 vs Phase 2 priority?** FTS5 is quick and improves keyword search immediately. Semantic search is higher impact but more work.
2. **sqlite-vec installation strategy?** The npm package `sqlite-vec` provides prebuilt binaries. Need to verify it works in the target Docker base image (e.g., `node:20-slim`).
3. **Shotlist PDF processing priority?** Currently only 100/9,579 are processed. Expanding this would dramatically improve semantic search quality since titles alone are terse.
4. **Embedding model size?** `all-MiniLM-L6-v2` (384 dims, ~30 MB ONNX) is the sweet spot. Smaller `L3` variant saves ~13 MB at some quality cost. Larger models (768 dims) double storage with marginal gains for short titles.
