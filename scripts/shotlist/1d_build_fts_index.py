"""
Stage 1d: Build FTS5 full-text search index.

Primary OCR source is 1c (LLM vision OCR via Qwen3.5), which produces clean
transcription text with form headers, table formatting, and boilerplate
stripped. Marker-pdf OCR (1a) is optionally included as a supplemental source
but can be skipped entirely with --skip-marker.

When marker text is included, it is only used as a supplement: the LLM text
is always the base, and marker text is appended only when it contributes
meaningful unique content (≥10 unique real words not in the LLM output).
Marker-only PDFs (no LLM text) fall back to cleaned marker text.

The merged text is written into the `shotlist_text` column on film_rolls,
and a FTS5 virtual table is built for full-text search.

Also pulls discovery_shotlist.shotlist_raw text for matching reels.

Idempotent — safe to re-run. Drops and recreates the FTS5 table each time.

Pipeline: 1c (LLM OCR) → 1d (FTS5 index). Optionally includes 1a (marker OCR).

Usage:
    uv run python scripts/shotlist/1d_build_fts_index.py                # LLM primary + marker supplement
    uv run python scripts/shotlist/1d_build_fts_index.py --skip-marker  # LLM only, no marker text
    uv run python scripts/shotlist/1d_build_fts_index.py --stats        # show stats only
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHOTLIST_RAW_DIR = ROOT / "data" / "01_shotlist_raw"
LLM_OCR_DIR = ROOT / "static_assets" / "llm_ocr"
DB_PATH = ROOT / "database" / "catalog.db"


# ---------------------------------------------------------------------------
# Markdown → plain text cleaning
# ---------------------------------------------------------------------------

def _rejoin_table_row(row_text: str) -> str:
    """Reconstruct text from a markdown table row, rejoining words split by column boundaries.

    Marker-pdf renders these old typewriter shotlists as multi-column tables
    whose column boundaries often land in the middle of words. For example:
        | Pri | me crev | for A | pollo 1 | 2 mission |
    This function parses cells and uses a heuristic to detect word
    continuations: if a cell starts with a lowercase letter and the previous
    accumulated text ends with a letter, the column boundary split a word
    and the cells are joined without a space.
    """
    cells = [c.strip() for c in row_text.split("|")]
    cells = [c for c in cells if c]
    if not cells:
        return ""

    result = cells[0]
    for i in range(1, len(cells)):
        curr = cells[i]
        if not curr:
            continue
        # If previous text ends with a letter and this cell starts lowercase,
        # the column boundary split a word — join without space.
        if result and result[-1].isalpha() and curr[0].islower():
            result += curr
        else:
            result += " " + curr

    return result


def clean_marker_text(markdown: str) -> str:
    """Strip markdown formatting from marker output to get indexable plain text.

    These PDFs are typewritten microfiche shotlists — marker produces markdown
    with tables, headers, bold/italic, and occasional HTML. We strip all of
    that down to plain words for FTS5 indexing.

    The key challenge is word-splitting: marker's table columns often cut words
    in half (e.g. "Co|mma|nde|r"). We reconstruct these before stripping
    table structure.
    """
    # First pass: remove HTML tags (marker sometimes includes <br>, <b>, etc.)
    text = re.sub(r"<[^>]+>", " ", markdown)

    # Remove bold/italic markers
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)

    # Remove markdown links [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Process line by line — table rows get special reconstruction
    out_lines: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        # Skip table separator rows (all dashes/pipes/colons/spaces)
        if re.match(r"^[\|\-:\s]+$", stripped):
            continue

        # Table row: reconstruct words split across columns
        if "|" in stripped:
            reconstructed = _rejoin_table_row(stripped)
            if reconstructed.strip():
                out_lines.append(reconstructed.strip())
        else:
            # Non-table line: strip heading markers and bullets
            cleaned = re.sub(r"^#{1,6}\s*", "", stripped)
            cleaned = re.sub(r"^[•·▪▸►▶‣⁃※†‡§¶]\s*", "", cleaned)
            if cleaned.strip():
                out_lines.append(cleaned.strip())

    text = "\n".join(out_lines)

    # Collapse OCR artifact sequences (runs of underscores, equals, etc.)
    text = re.sub(r"[_=]{3,}", " ", text)

    # Collapse excessive whitespace
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Drop lines that are too short to be meaningful (OCR noise)
    lines = text.split("\n")
    lines = [ln.strip() for ln in lines if len(ln.strip()) > 3]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dual-source merge logic
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set[str]:
    """Extract lowercase alpha tokens (len ≥ 3) for overlap comparison."""
    return {w.lower() for w in re.findall(r"[a-zA-Z]{3,}", text)}


def _alpha_count(text: str) -> int:
    """Count alphabetic characters in text."""
    return sum(1 for c in text if c.isalpha())


# Words commonly found in form headers / table formatting that the LLM
# correctly strips but marker preserves.  These pollute search results
# (e.g. every reel matching "footage" or "classification").
FORM_BOILERPLATE = frozenset({
    "classification", "footage", "camera", "angle", "unclassified",
    "restricted", "confidential", "secret", "document", "log",
    "evaluation", "motion", "picture", "scene", "documentary",
    "material", "category", "source", "total", "remarks", "nasa",
    "form", "page", "sheet", "number", "date", "title", "subject",
    "type", "description", "location", "film", "roll",
})

MINIMUM_UNIQUE_REAL_WORDS = 10  # marker must contribute this many unique real words to be included


def merge_texts(marker_cleaned: str, llm_text: str) -> tuple[str, str]:
    """Merge marker and LLM transcriptions.  LLM text is always primary.

    Returns (merged_text, strategy_label).

    Strategy:
      - LLM present → use LLM as base.  If marker contributes ≥10 unique
        real words (excluding form boilerplate), append marker as supplement.
      - LLM absent + marker present → use cleaned marker as fallback.
      - Neither → empty.
    """
    has_marker = bool(marker_cleaned and marker_cleaned.strip())
    has_llm = bool(llm_text and llm_text.strip())

    if not has_marker and not has_llm:
        return "", "empty"
    if has_llm and not has_marker:
        return llm_text.strip(), "llm-only"
    if has_marker and not has_llm:
        return marker_cleaned, "marker-fallback"

    # Both sources present — LLM is primary.
    llm_tokens = _tokenize(llm_text)
    marker_tokens = _tokenize(marker_cleaned)
    marker_unique = marker_tokens - llm_tokens - FORM_BOILERPLATE

    if len(marker_unique) >= MINIMUM_UNIQUE_REAL_WORDS:
        # Marker contributes enough unique real words — append as supplement
        return f"{llm_text.strip()}\n\n{marker_cleaned}", f"llm+marker({len(marker_unique)} unique)"
    else:
        # Marker mostly duplicates LLM or adds only boilerplate/noise
        return llm_text.strip(), "llm-primary"


# ---------------------------------------------------------------------------
# Load texts from marker JSON outputs
# ---------------------------------------------------------------------------

def load_all_texts(
    shotlist_raw_dir: Path,
    llm_ocr_dir: Path,
    *,
    skip_marker: bool = False,
) -> dict[str, tuple[str, str]]:
    """Load LLM text from 01c_llm_ocr/ (primary) and optionally marker text.

    Primary source:
      - 01c_llm_ocr/*.json → LLM vision OCR (stage 1c), key: "llm_text"

    Optional supplemental source (skipped when skip_marker=True):
      - 01_shotlist_raw/*.json → marker-pdf OCR (stage 1a), key: "text"

    Returns a dict mapping PDF filename → (cleaned_marker_text, llm_text).
    When skip_marker=True, the marker field is always empty string.
    """
    # ── Step 1: load marker text from 01_shotlist_raw/ (unless skipped) ──
    marker_texts: dict[str, str] = {}  # pdf_name → cleaned marker text
    stats = {"marker": 0, "llm": 0, "both": 0, "legacy_rescue": 0}

    if skip_marker:
        print("  Marker OCR: SKIPPED (--skip-marker)")
    else:
        for jf in sorted(shotlist_raw_dir.glob("*.json")):
            if jf.name == "_manifest.json":
                continue
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"  WARNING: Could not read {jf.name}: {e}")
                continue

            pdf_name = data.get("filename", "")
            if not pdf_name:
                continue

            # Read marker text — handle legacy rescue format
            raw_marker = ""
            if data.get("source") == "llm-rescue" and data.get("marker_text"):
                raw_marker = data["marker_text"]
                stats["legacy_rescue"] += 1
            else:
                raw_marker = data.get("text", "")

            cleaned = clean_marker_text(raw_marker) if raw_marker else ""
            if cleaned:
                marker_texts[pdf_name] = cleaned

        print(f"  Marker OCR (01_shotlist_raw): {len(marker_texts)} PDFs with text")

    # ── Step 2: load LLM text from 01c_llm_ocr/ ──
    llm_texts: dict[str, str] = {}  # pdf_name → llm text

    if llm_ocr_dir.exists():
        for jf in sorted(llm_ocr_dir.glob("*.json")):
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"  WARNING: Could not read {jf.name}: {e}")
                continue

            pdf_name = data.get("filename", "")
            llm_text = data.get("llm_text", "")
            if pdf_name and llm_text and llm_text.strip():
                llm_texts[pdf_name] = llm_text

    # Also pick up LLM text from legacy formats in shotlist_raw
    for jf in sorted(shotlist_raw_dir.glob("*.json")):
        if jf.name == "_manifest.json":
            continue
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        pdf_name = data.get("filename", "")
        if not pdf_name or pdf_name in llm_texts:
            continue
        # Legacy rescue format or embedded llm_text
        llm_text = ""
        if data.get("source") == "llm-rescue" and "text" in data:
            llm_text = data["text"]
        elif data.get("llm_text"):
            llm_text = data["llm_text"]
        if llm_text and llm_text.strip():
            llm_texts[pdf_name] = llm_text

    print(f"  LLM OCR (01c_llm_ocr):       {len(llm_texts)} PDFs with text")

    # ── Step 3: merge into unified dict ──
    all_pdf_names = set(marker_texts.keys()) | set(llm_texts.keys())
    texts: dict[str, tuple[str, str]] = {}

    for pdf_name in all_pdf_names:
        m = marker_texts.get(pdf_name, "")
        l = llm_texts.get(pdf_name, "")
        has_m = bool(m)
        has_l = bool(l)
        if has_m and has_l:
            stats["both"] += 1
        elif has_m:
            stats["marker"] += 1
        elif has_l:
            stats["llm"] += 1
        texts[pdf_name] = (m, l)

    print(f"  Combined: marker-only={stats['marker']}, llm-only={stats['llm']}, "
          f"both={stats['both']}, legacy-rescue={stats['legacy_rescue']}")
    print(f"  Total unique PDFs with text: {len(texts)}")

    return texts


def build_reel_shotlist_texts(
    conn: sqlite3.Connection,
    all_texts: dict[str, tuple[str, str]],
) -> dict[str, str]:
    """Assemble per-reel shotlist text by merging marker + LLM per PDF,
    then combining across PDFs + discovery shotlist per reel.

    Returns dict mapping identifier → combined shotlist text.
    """
    c = conn.cursor()

    # Get all reels with linked PDFs
    c.execute("""
        SELECT identifier, shotlist_pdfs
        FROM film_rolls
        WHERE shotlist_pdfs IS NOT NULL AND shotlist_pdfs != ''
    """)
    reels_with_pdfs = c.fetchall()

    # Get discovery shotlist text keyed by identifier
    discovery_texts: dict[str, list[str]] = {}
    try:
        c.execute("""
            SELECT t.reel_identifier, ds.shotlist_raw
            FROM discovery_shotlist ds
            JOIN transfers t ON CAST(t.tape_number AS INTEGER) = ds.tape_number
            WHERE t.transfer_type = 'discovery_capture'
              AND ds.shotlist_raw IS NOT NULL
              AND ds.shotlist_raw != ''
        """)
        for ident, raw in c.fetchall():
            discovery_texts.setdefault(ident, []).append(raw)
    except sqlite3.OperationalError:
        # discovery_shotlist table may not exist
        pass

    reel_texts: dict[str, str] = {}
    matched_pdfs = 0
    unmatched_pdfs = 0
    merge_stats: dict[str, int] = {}

    for identifier, pdfs_json in reels_with_pdfs:
        try:
            pdf_names = json.loads(pdfs_json)
        except json.JSONDecodeError:
            continue

        parts: list[str] = []

        # Merge marker + LLM text per PDF, then add to reel
        for pdf_name in pdf_names:
            if pdf_name in all_texts:
                marker_cleaned, llm_text = all_texts[pdf_name]
                merged, strategy = merge_texts(marker_cleaned, llm_text)
                # Track strategy counts
                label = strategy.split("(")[0]  # e.g. "union" from "union(45%)"
                merge_stats[label] = merge_stats.get(label, 0) + 1
                if merged:
                    parts.append(merged)
                matched_pdfs += 1
            else:
                unmatched_pdfs += 1

        # Add discovery shotlist text
        if identifier in discovery_texts:
            for dt in discovery_texts[identifier]:
                parts.append(dt)

        if parts:
            reel_texts[identifier] = "\n\n".join(parts)

    print(f"  PDFs matched to reels: {matched_pdfs}")
    print(f"  PDFs not yet processed: {unmatched_pdfs}")
    print(f"  Discovery shotlist entries: {sum(len(v) for v in discovery_texts.values())}")
    print(f"  Reels with shotlist text: {len(reel_texts)}")
    print(f"  Merge strategies: {dict(sorted(merge_stats.items()))}")

    return reel_texts


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

def ensure_shotlist_text_column(conn: sqlite3.Connection) -> None:
    """Add shotlist_text column to film_rolls if it doesn't exist."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(film_rolls)").fetchall()}
    if "shotlist_text" not in cols:
        conn.execute("ALTER TABLE film_rolls ADD COLUMN shotlist_text TEXT")
        conn.commit()
        print("  Added 'shotlist_text' column to film_rolls")
    else:
        print("  'shotlist_text' column already exists")


def write_shotlist_texts(
    conn: sqlite3.Connection,
    reel_texts: dict[str, str],
) -> int:
    """Write shotlist_text values into film_rolls."""
    c = conn.cursor()

    # Clear existing values
    c.execute("UPDATE film_rolls SET shotlist_text = NULL")

    updated = 0
    for identifier, text in reel_texts.items():
        c.execute(
            "UPDATE film_rolls SET shotlist_text = ? WHERE identifier = ?",
            (text, identifier),
        )
        updated += c.rowcount

    conn.commit()
    return updated


def build_fts5_index(conn: sqlite3.Connection) -> None:
    """Build the FTS5 virtual table over film_rolls search fields.

    Uses an external-content FTS5 table (content= pointing to film_rolls)
    for minimal storage overhead — the FTS index only stores tokens and
    positions, not full text copies.
    """
    c = conn.cursor()

    # Drop existing FTS table if present
    c.execute("DROP TABLE IF EXISTS film_rolls_fts")

    # Create FTS5 table as external-content referencing film_rolls.
    # We index: identifier, title, alternate_title, description, mission, shotlist_text
    # Column weights for BM25 ranking are applied at query time.
    c.execute("""
        CREATE VIRTUAL TABLE film_rolls_fts USING fts5(
            identifier,
            title,
            alternate_title,
            description,
            mission,
            shotlist_text,
            content='film_rolls',
            content_rowid='rowid'
        )
    """)

    # Populate the FTS index from film_rolls
    c.execute("""
        INSERT INTO film_rolls_fts(rowid, identifier, title, alternate_title,
                                   description, mission, shotlist_text)
        SELECT rowid, identifier, title, alternate_title,
               description, mission, shotlist_text
        FROM film_rolls
    """)

    conn.commit()

    # Verify
    count = c.execute("SELECT COUNT(*) FROM film_rolls_fts").fetchone()[0]
    print(f"  FTS5 index built: {count} rows indexed")


# ---------------------------------------------------------------------------
# Stats / reporting
# ---------------------------------------------------------------------------

def print_stats(conn: sqlite3.Connection) -> None:
    """Print current state of shotlist text and FTS index."""
    c = conn.cursor()

    total = c.execute("SELECT COUNT(*) FROM film_rolls").fetchone()[0]
    with_text = c.execute(
        "SELECT COUNT(*) FROM film_rolls WHERE shotlist_text IS NOT NULL AND shotlist_text != ''"
    ).fetchone()[0]
    with_pdf = c.execute(
        "SELECT COUNT(*) FROM film_rolls WHERE has_shotlist_pdf = 1"
    ).fetchone()[0]

    # Text length stats
    c.execute("""
        SELECT MIN(LENGTH(shotlist_text)), AVG(LENGTH(shotlist_text)),
               MAX(LENGTH(shotlist_text))
        FROM film_rolls
        WHERE shotlist_text IS NOT NULL AND shotlist_text != ''
    """)
    min_len, avg_len, max_len = c.fetchone()

    # FTS table existence
    fts_exists = c.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='film_rolls_fts'"
    ).fetchone()[0]
    fts_count = 0
    if fts_exists:
        fts_count = c.execute("SELECT COUNT(*) FROM film_rolls_fts").fetchone()[0]

    print(f"\n{'='*60}")
    print("  Shotlist Text & FTS5 Index Status")
    print(f"{'='*60}")
    print(f"  Total film_rolls:           {total:>7}")
    print(f"  With shotlist PDF:          {with_pdf:>7}  ({100*with_pdf/total:.1f}%)")
    print(f"  With shotlist_text:         {with_text:>7}  ({100*with_text/total:.1f}%)")
    if min_len is not None:
        print(f"  Text length (min/avg/max):  {min_len}/{int(avg_len)}/{max_len}")
    print(f"  FTS5 table exists:          {'yes' if fts_exists else 'no'}")
    if fts_exists:
        print(f"  FTS5 rows indexed:          {fts_count:>7}")
    print(f"{'='*60}")

    # Check marker processing progress
    if SHOTLIST_RAW_DIR.exists():
        jsons = [f for f in SHOTLIST_RAW_DIR.iterdir() if f.suffix == ".json" and f.name != "_manifest.json"]
        print(f"\n  Marker OCR outputs in {SHOTLIST_RAW_DIR.name}/: {len(jsons)}")
        total_pdfs = c.execute(
            "SELECT SUM(json_array_length(shotlist_pdfs)) FROM film_rolls WHERE shotlist_pdfs IS NOT NULL"
        ).fetchone()[0] or 0
        print(f"  Total linked PDFs in DB:    {total_pdfs}")
        print(f"  Coverage:                   {100*len(jsons)/max(total_pdfs,1):.1f}%")


# ---------------------------------------------------------------------------
# Test search
# ---------------------------------------------------------------------------

def test_search(conn: sqlite3.Connection, query: str, limit: int = 10) -> None:
    """Run a test FTS5 search and print results."""
    c = conn.cursor()

    # Check FTS table exists
    fts_exists = c.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='film_rolls_fts'"
    ).fetchone()[0]
    if not fts_exists:
        print("  FTS5 table not found — run without --stats first to build it.")
        return

    # Build FTS5 query: quote each token for prefix matching
    tokens = query.strip().split()
    # Use simple token matching — FTS5 handles this well
    fts_query = " AND ".join(f'"{t}"' for t in tokens)

    print(f"\n  Search: {query!r} -> FTS5: {fts_query}")
    print(f"  {'-'*70}")

    try:
        rows = c.execute("""
            SELECT fr.identifier, fr.title,
                   bm25(film_rolls_fts, 5.0, 10.0, 5.0, 3.0, 2.0, 1.0) AS rank,
                   snippet(film_rolls_fts, 5, '<b>', '</b>', '…', 16) AS shotlist_snippet
            FROM film_rolls_fts fts
            JOIN film_rolls fr ON fr.rowid = fts.rowid
            WHERE film_rolls_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (fts_query, limit)).fetchall()
    except sqlite3.OperationalError as e:
        print(f"  ERROR: {e}")
        return

    if not rows:
        print("  No results.")
        return

    for i, (ident, title, rank, snippet) in enumerate(rows, 1):
        snippet_clean = snippet.replace("\n", " ")[:120] if snippet else ""
        print(f"  {i:2d}. [{rank:+8.2f}] {ident:<12s} {(title or '')[:50]}")
        if snippet_clean:
            print(f"      shotlist: {snippet_clean}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build FTS5 search index (LLM OCR primary, marker optional)"
    )
    parser.add_argument("--stats", action="store_true", help="Show stats only")
    parser.add_argument(
        "--skip-marker", action="store_true",
        help="Skip marker-pdf OCR data entirely; use only LLM OCR text"
    )
    parser.add_argument(
        "--test", type=str, default=None,
        help="Run a test search query after building"
    )
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    if args.stats:
        print_stats(conn)
        conn.close()
        return

    mode = "LLM only" if args.skip_marker else "LLM primary + marker supplement"
    print(f"Building FTS5 search index ({mode})...")
    print(f"  DB: {DB_PATH}")
    if not args.skip_marker:
        print(f"  Marker OCR: {SHOTLIST_RAW_DIR}")
    print(f"  LLM OCR:    {LLM_OCR_DIR}")

    # 1. Ensure shotlist_text column exists
    ensure_shotlist_text_column(conn)

    # 2. Load OCR outputs
    t0 = time.time()
    print(f"\nLoading OCR outputs...")
    all_texts = load_all_texts(SHOTLIST_RAW_DIR, LLM_OCR_DIR, skip_marker=args.skip_marker)
    print(f"  Loaded {len(all_texts)} PDFs in {time.time()-t0:.1f}s")

    # 3. Build per-reel shotlist text (merge per PDF, combine per reel)
    print(f"\nAssembling per-reel shotlist text (merging sources)...")
    reel_texts = build_reel_shotlist_texts(conn, all_texts)

    # 4. Write shotlist_text to film_rolls
    print(f"\nWriting shotlist_text to database...")
    updated = write_shotlist_texts(conn, reel_texts)
    print(f"  Updated {updated} rows")

    # 5. Build FTS5 index
    print(f"\nBuilding FTS5 index...")
    t0 = time.time()
    build_fts5_index(conn)
    print(f"  Built in {time.time()-t0:.1f}s")

    # 6. Print stats
    print_stats(conn)

    # 7. Test search if requested
    if args.test:
        test_search(conn, args.test)
    else:
        # Run a few default test searches
        for q in ["Gemini spacecraft", "lunar module", "press conference", "EVA spacewalk"]:
            test_search(conn, q)

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
