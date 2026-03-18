"""
Stage 1c: Directory crawl & transfer verification.

Scans /o/ Master folders and proxy directories (READ-ONLY) to build a file
inventory, then matches discovered files against the transfers table in
database/catalog.db.

Currently scans:
    /o/Master 1/        (tapes 501–562)
    /o/Master 2/        (tapes 563–625)
    /o/Master 3/        (tapes 626–712)
    /o/Master 4/        (tapes 713–886)
    /o/Master 5/70mm Panavision Collection/
                        (NARA 70mm: 255-pv-NNN, 255-FR-XXX, 255-se-NN-NNN, …)
    /o/MPEG-Proxies/    (all proxy sub-folders, multiple naming conventions)
      MPEG-2/           L000NNN_FR-NNN.mpg  (LTO-based MPEG-2s)
      MPEG-2_FR/        FR-NNNN.mpg         (bare FR identifiers)
      MPEG-2_Imagery_Online_proxy_files/IO/
                        FR-C176_jsc2014m009788.mp4  (identifier + JSC asset #)
      NARA/             255-fr-1029.mp4, 255-ak-17.mp4, …  (NARA-prefixed)

Reports:
    - Files matched to transfers (and what rule matched them)
    - Unmatched files (no identifier could be resolved)
    - Sets film_rolls.has_transfer_on_disk = 1 for confirmed matches

Matching is handled by two small modules:
    matchers/filename_parser.py  — filename → list of candidate identifiers
    matchers/db_resolve.py       — candidates → transfer rows

Adding support for a new folder/naming convention only requires updating
filename_parser.py, never this file.

Usage:
    uv run python scripts/1c_verify_transfers.py              # full scan
    uv run python scripts/1c_verify_transfers.py --incremental # new files only
    uv run python scripts/1c_verify_transfers.py --dry-run    # report only
    uv run python scripts/1c_verify_transfers.py --stats      # show existing stats

⚠️  /o/ is STRICTLY READ-ONLY — this script only reads directory listings.
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import time

# Allow importing sibling scripts as modules.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_resolve import ResolvedMatch, resolve
from filename_parser import parse_filename

DB_PATH = "../database/catalog.db"

# Folders to scan — /o/ is READ-ONLY, we only list files.
# (path, recursive, is_master_quality)
SCAN_ROOTS = [
    ("O:/Master 1",                   True,  True),   # tapes 501–562
    ("O:/Master 2",                   True,  True),   # tapes 563–625
    ("O:/Master 3",                   True,  True),   # tapes 626–712
    ("O:/Master 4",                   True,  True),   # tapes 713–886
    ("O:/70mm Panavision Collection", True,  True),   # NARA 70mm scans
    ("O:/FR-Masters",                 True,  True),   # NARA FR scans
    ("O:/MPEG-Proxies",               True,  False),  # all proxy subfolders
]

# Tape number → Master folder mapping (for gap detection in the report).
TAPE_FOLDER_RANGES = [
    (501, 562, "Master 1"),
    (563, 625, "Master 2"),
    (626, 712, "Master 3"),
    (713, 886, "Master 4"),
]

# Placeholder/noise files to skip entirely.
# Also skip -SAMPLE files (test/demo clips that are not real transfers).
IGNORE_RE = re.compile(
    r"not missing.*doesn.?t exist|doesn.?t exist.*not missing|MISSING|-SAMPLE",
    re.IGNORECASE,
)

MASTER_ROOTS = {"O:/Master 1", "O:/Master 2", "O:/Master 3", "O:/Master 4"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def tape_master_folder(tape_num: int) -> str | None:
    for start, end, folder in TAPE_FOLDER_RANGES:
        if start <= tape_num <= end:
            return folder
    return None


def tape_expected_path(tape_num: int) -> str | None:
    folder = tape_master_folder(tape_num)
    if folder:
        return f"O:/{folder}/Tape {tape_num} - Self Contained.mov"
    return None


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

STAGE_1C_SCHEMA = """
-- Files discovered on /o/ via directory crawl.
CREATE TABLE IF NOT EXISTS files_on_disk (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_root     TEXT NOT NULL,           -- e.g. 'O:/Master 1'
    rel_path        TEXT NOT NULL,           -- path relative to folder_root
    filename        TEXT NOT NULL,
    extension       TEXT,                    -- lowercase, e.g. '.mov'
    size_bytes      INTEGER,
    UNIQUE(folder_root, rel_path)
);

CREATE INDEX IF NOT EXISTS idx_fod_filename ON files_on_disk(filename);
CREATE INDEX IF NOT EXISTS idx_fod_ext      ON files_on_disk(extension);
CREATE INDEX IF NOT EXISTS idx_fod_root     ON files_on_disk(folder_root);

-- Matches between on-disk files and transfers.
CREATE TABLE IF NOT EXISTS transfer_file_matches (
    file_id         INTEGER NOT NULL REFERENCES files_on_disk(id),
    transfer_id     INTEGER REFERENCES transfers(id),     -- NULL if roll found but no transfer
    tape_number     INTEGER,                              -- populated for tape_number matches
    match_rule      TEXT NOT NULL,                        -- e.g. 'tape_number', 'lto_vfr', 'identifier'
    reel_identifier TEXT,                                 -- film_roll identifier resolved to
    UNIQUE(file_id, transfer_id)
);

CREATE INDEX IF NOT EXISTS idx_tfm_file     ON transfer_file_matches(file_id);
CREATE INDEX IF NOT EXISTS idx_tfm_transfer ON transfer_file_matches(transfer_id);
CREATE INDEX IF NOT EXISTS idx_tfm_reel     ON transfer_file_matches(reel_identifier);
"""


# ---------------------------------------------------------------------------
# Directory scanning
# ---------------------------------------------------------------------------

def scan_folder(
    root: str,
    db: sqlite3.Connection,
    recursive: bool = True,
) -> tuple[int, set[str]]:
    """Walk *root* and upsert files into ``files_on_disk``.

    Existing rows (keyed on folder_root + rel_path UNIQUE) are left untouched
    so primary-key IDs — and ffprobe_metadata rows referencing them — remain
    stable across re-runs.

    Returns ``(count_touched, set_of_rel_paths_seen)``.
    """
    count = 0
    seen: set[str] = set()

    if recursive:
        walker = os.walk(root)
    else:
        try:
            entries = list(os.scandir(root))
            files = [e.name for e in entries if e.is_file()]
            walker = [(root, [], files)]
        except OSError:
            return 0, seen

    for dirpath, _dirnames, filenames in walker:
        for fname in filenames:
            if IGNORE_RE.search(fname):
                continue

            full = os.path.join(dirpath, fname)
            rel  = os.path.relpath(full, root).replace("\\", "/")
            ext  = os.path.splitext(fname)[1].lower() or None
            seen.add(rel)

            try:
                size = os.path.getsize(full)
            except OSError:
                size = None

            db.execute(
                "INSERT OR IGNORE INTO files_on_disk "
                "(folder_root, rel_path, filename, extension, size_bytes) "
                "VALUES (?,?,?,?,?)",
                (root, rel, fname, ext, size),
            )
            count += 1

    db.commit()
    return count, seen


# ---------------------------------------------------------------------------
# Matching — single unified pass
# ---------------------------------------------------------------------------

def match_all_files(db: sqlite3.Connection, unmatched_only: bool = False) -> dict[str, int]:
    """Match files in ``files_on_disk`` to transfers using the filename parser.

    If *unmatched_only* is True, skip files that already have at least one row
    in ``transfer_file_matches`` — used in incremental mode to avoid
    re-processing files that were matched in a previous full or incremental run.

    Delegates all filename interpretation to ``matchers.filename_parser`` and
    all DB lookups to ``matchers.db_resolve``.  No per-folder special-casing
    lives here — adding a new folder/naming convention only requires touching
    the parser.

    Returns a dict of match_rule → row count for progress display.
    """
    if unmatched_only:
        rows = db.execute(
            "SELECT f.id, f.folder_root, f.filename FROM files_on_disk f "
            "WHERE NOT EXISTS ("
            "    SELECT 1 FROM transfer_file_matches WHERE file_id = f.id"
            ")"
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT id, folder_root, filename FROM files_on_disk"
        ).fetchall()

    counts: dict[str, int] = {}

    for file_id, _folder_root, filename in rows:
        parsed  = parse_filename(filename)
        matches = resolve(db, parsed)

        if not matches:
            continue

        for match in matches:
            db.execute(
                "INSERT OR IGNORE INTO transfer_file_matches "
                "(file_id, transfer_id, tape_number, match_rule, reel_identifier) "
                "VALUES (?,?,?,?,?)",
                (
                    file_id,
                    match.transfer_id,
                    match.tape_number,
                    match.match_rule,
                    match.reel_identifier,
                ),
            )
            counts[match.match_rule] = counts.get(match.match_rule, 0) + 1

    db.commit()
    return counts


def dedup_transfer_file_matches(db: sqlite3.Connection) -> int:
    """Remove duplicate transfer_file_matches rows keeping one per (file_id, reel_identifier).

    Fan-out matching (one file → many transfers for the same reel) can leave
    multiple rows with the same file_id + reel_identifier.  Only one row per
    physical file per reel is meaningful for downstream queries.

    Keeps the row with the lowest rowid (first inserted = most specific).

    Returns number of duplicate rows deleted.
    """
    result = db.execute("""
        DELETE FROM transfer_file_matches
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM transfer_file_matches
            GROUP BY file_id, COALESCE(reel_identifier, '__null__')
        )
    """)
    db.commit()
    return result.rowcount


def set_has_transfer_on_disk(db: sqlite3.Connection) -> int:
    """Set film_rolls.has_transfer_on_disk = 1 for all rolls with confirmed file matches.

    Returns count updated.
    """
    result = db.execute("""
        UPDATE film_rolls SET has_transfer_on_disk = 1
        WHERE identifier IN (
            SELECT DISTINCT reel_identifier
            FROM transfer_file_matches
            WHERE reel_identifier IS NOT NULL
        )
    """)
    db.commit()
    return result.rowcount


def backfill_transfer_file_paths(db: sqlite3.Connection) -> int:
    """Populate transfers.filename and transfers.file_path from matched on-disk files.

    For each transfer linked via transfer_file_matches, sets filename and file_path
    to the actual on-disk file.  The most specific match rule wins:
        identifier > lto_vfr > lto_fallback > tape_number

    Returns count of transfers updated.
    """
    # Rank match rules — lower number = more specific = preferred.
    RULE_RANK = {
        "identifier":              1,
        "lto_vfr":                 2,
        "lto_fallback":            3,
        "tape_number":             4,
        "tape_shotlist_only":      5,
        "identifier_no_transfer":  6,
        "tape_known_no_rolls":     7,
        "tape_number_no_transfer": 8,
    }

    rows = db.execute("""
        SELECT m.transfer_id, m.match_rule,
               f.folder_root, f.rel_path, f.filename
        FROM transfer_file_matches m
        JOIN files_on_disk f ON f.id = m.file_id
        WHERE m.transfer_id IS NOT NULL
        ORDER BY m.transfer_id
    """).fetchall()

    # For each transfer, pick the best (most specific) file match.
    best: dict[int, tuple[str, str, str]] = {}   # transfer_id → (rule, folder_root, rel_path, filename)
    for xfer_id, rule, folder_root, rel_path, fname in rows:
        rank = RULE_RANK.get(rule, 99)
        existing = best.get(xfer_id)
        if existing is None or rank < RULE_RANK.get(existing[0], 99):
            best[xfer_id] = (rule, folder_root, rel_path, fname)

    updated = 0
    for xfer_id, (rule, folder_root, rel_path, fname) in best.items():
        file_path = f"{folder_root}/{rel_path}"
        db.execute(
            "UPDATE transfers SET filename = ?, file_path = ? WHERE id = ?",
            (fname, file_path, xfer_id),
        )
        updated += 1

    db.commit()
    return updated


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(db: sqlite3.Connection):
    """Print a comprehensive matching report."""
    print("\n" + "=" * 70)
    print("STAGE 1c: TRANSFER VERIFICATION REPORT")
    print("=" * 70)

    # Files by folder
    print(f"\n  {'--- Files on disk by folder ---':^50}")
    for row in db.execute(
        "SELECT folder_root, COUNT(*), "
        "SUM(CASE WHEN extension IN ('.mov', '.mp4', '.mxf', '.mpg', '.m4v', '.ts') THEN 1 ELSE 0 END) "
        "FROM files_on_disk GROUP BY folder_root ORDER BY folder_root"
    ):
        print(f"    {row[0]:30s}: {row[1]:>8,d} files ({row[2]:,d} video)")

    total_files = db.execute("SELECT COUNT(*) FROM files_on_disk").fetchone()[0]
    print(f"    {'TOTAL':30s}: {total_files:>8,d}")

    # Match summary
    print(f"\n  {'--- Match results ---':^50}")
    for row in db.execute(
        "SELECT match_rule, COUNT(*), COUNT(DISTINCT file_id), COUNT(DISTINCT reel_identifier) "
        "FROM transfer_file_matches GROUP BY match_rule"
    ):
        print(f"    {row[0]:30s}: {row[1]:>6,d} matches, {row[2]:>6,d} files, {row[3]:>6,d} reels")

    total_matches = db.execute("SELECT COUNT(DISTINCT file_id) FROM transfer_file_matches").fetchone()[0]
    total_reels = db.execute(
        "SELECT COUNT(DISTINCT reel_identifier) FROM transfer_file_matches WHERE reel_identifier IS NOT NULL"
    ).fetchone()[0]
    print(f"    {'TOTAL':30s}: {' ':>6s}        {total_matches:>6,d} files, {total_reels:>6,d} reels")

    # Unmatched files
    unmatched = db.execute(
        "SELECT COUNT(*) FROM files_on_disk "
        "WHERE id NOT IN (SELECT file_id FROM transfer_file_matches)"
    ).fetchone()[0]
    video_unmatched = db.execute(
        "SELECT COUNT(*) FROM files_on_disk "
        "WHERE id NOT IN (SELECT file_id FROM transfer_file_matches) "
        "AND extension IN ('.mov', '.mp4', '.mxf', '.mpg', '.m4v', '.ts')"
    ).fetchone()[0]
    print(f"\n  Unmatched files:       {unmatched:>8,d} ({video_unmatched:,d} video)")

    # Tape files that couldn't be resolved
    print(f"\n  {'--- Unresolved tape files (Masters 1-4) ---':^50}")
    tape_unmatched = db.execute("""
        SELECT f.folder_root, f.filename, f.size_bytes
        FROM files_on_disk f
        LEFT JOIN transfer_file_matches m ON f.id = m.file_id
        WHERE f.folder_root IN ('O:/Master 1', 'O:/Master 2', 'O:/Master 3', 'O:/Master 4')
          AND (m.file_id IS NULL OR m.match_rule IN ('tape_number_no_transfer'))
        ORDER BY f.folder_root, f.filename
    """).fetchall()

    if tape_unmatched:
        for root, fname, size in tape_unmatched:
            folder = root.split("/")[-1]
            size_str = f"{size/1024/1024/1024:.1f} GB" if size and size > 0 else "??"
            print(f"    [{folder}] {fname}  ({size_str})")
    else:
        print("    (none — all tape files resolved to transfers)")

    # Tapes that exist in the discovery shotlist but whose individual rolls were
    # never linked in the spreadsheet — known content, but no roll-level mapping.
    known_no_rolls = db.execute("""
        SELECT f.folder_root, f.filename, f.size_bytes, m.tape_number
        FROM files_on_disk f
        JOIN transfer_file_matches m ON f.id = m.file_id
        WHERE m.match_rule = 'tape_known_no_rolls'
        ORDER BY m.tape_number, f.filename
    """).fetchall()
    if known_no_rolls:
        print(f"\n  {'--- Tapes known but rolls not linked in spreadsheet ---':^50}")
        for root, fname, size, tapeno in known_no_rolls:
            folder = root.split("/")[-1]
            size_str = f"{size/1024/1024/1024:.1f} GB" if size and size > 0 else "??"
            print(f"    [{folder}] {fname}  ({size_str})  [tape {tapeno} — content not roll-mapped]")

    # Tapes expected by naming convention but not found on disk
    print(f"\n  {'--- Tapes expected but not on disk ---':^50}")
    found_tapes = set()
    for row in db.execute(
        "SELECT tape_number FROM transfer_file_matches WHERE tape_number IS NOT NULL"
    ):
        found_tapes.add(row[0])

    phantom = []
    for start, end, folder in TAPE_FOLDER_RANGES:
        for tape in range(start, end + 1):
            if tape not in found_tapes:
                path = tape_expected_path(tape)
                phantom.append((tape, path, folder))

    if phantom:
        for tape, path, folder in phantom[:30]:
            print(f"    Tape {tape:>4d}  ({folder}) — expected: {path}")
        if len(phantom) > 30:
            print(f"    ... and {len(phantom) - 30} more")
        print(f"    Total phantom tapes: {len(phantom)}")
    else:
        print("    (none — all expected tapes found on disk)")

    # PV rolls in DB not found on disk
    print(f"\n  {'--- PV rolls in DB but no file on disk ---':^50}")
    pv_unmatched = db.execute("""
        SELECT fr.identifier, fr.title
        FROM film_rolls fr
        WHERE fr.id_prefix = 'PV'
          AND fr.identifier NOT IN (
              SELECT DISTINCT reel_identifier
              FROM transfer_file_matches
              WHERE reel_identifier IS NOT NULL
          )
        ORDER BY fr.identifier
    """).fetchall()
    if pv_unmatched:
        for ident, title in pv_unmatched:
            print(f"    {ident:15s}  {title or '(no title)'}")
        print(f"    Total: {len(pv_unmatched)}")
    else:
        print("    (none — all DB PV rolls have a file on disk)")

    # Non-tape-master and proxy folders — files not matched to any DB record
    print(f"\n  {'--- Unrecognised files (not in DB) ---':^50}")
    non_tape_roots = [root for root, _, _ in SCAN_ROOTS if root not in MASTER_ROOTS]
    placeholders = ",".join("?" * len(non_tape_roots))
    unmatched_vid = db.execute(f"""
        SELECT f.folder_root, f.rel_path
        FROM files_on_disk f
        WHERE f.folder_root IN ({placeholders})
          AND f.id NOT IN (SELECT file_id FROM transfer_file_matches)
          AND f.extension IN ('.mov', '.mp4', '.mxf', '.mpg', '.m4v', '.ts')
        ORDER BY f.folder_root, f.rel_path
    """, non_tape_roots).fetchall()
    if unmatched_vid:
        for root, rel in unmatched_vid[:40]:
            short = root.replace("O:/", "")
            print(f"    [{short}]  {rel}")
        if len(unmatched_vid) > 40:
            print(f"    ... and {len(unmatched_vid) - 40} more")
        print(f"    Total: {len(unmatched_vid)}")
    else:
        print("    (none)")

    # has_transfer_on_disk summary
    total_rolls = db.execute("SELECT COUNT(*) FROM film_rolls").fetchone()[0]
    has_xfer = db.execute(
        "SELECT COUNT(*) FROM film_rolls WHERE has_transfer_on_disk = 1"
    ).fetchone()[0]
    print(f"\n  {'--- film_rolls.has_transfer_on_disk ---':^50}")
    print(f"    Set to 1:    {has_xfer:>8,d} / {total_rolls:,d} ({100*has_xfer/total_rolls:.1f}%)")

    print("=" * 70)


def print_stats_only(db: sqlite3.Connection):
    """Show stats from a previous run without re-scanning."""
    try:
        count = db.execute("SELECT COUNT(*) FROM files_on_disk").fetchone()[0]
    except sqlite3.OperationalError:
        print("No Stage 1c data found. Run without --stats first.")
        return

    if count == 0:
        print("No files in files_on_disk table. Run without --stats first.")
        return

    print_report(db)


def _run_incremental(db: sqlite3.Connection, dry_run: bool = False) -> None:
    """Incremental scan: discover new files and match only those.

    Unlike the full run this mode:
    - Does NOT drop transfer_file_matches (existing matches are preserved)
    - Does NOT reset has_transfer_on_disk or transfers.filename/file_path
    - Only scans the filesystem for files not already in files_on_disk
    - Only runs the matcher for files with no entry in transfer_file_matches
    - Still prunes records for files that have disappeared from disk

    Use this after new tapes/proxies are added to /o/ so you don't have to
    wait for a full overnight re-scan.  Run 1d_ffprobe_metadata.py afterward
    to probe the newly discovered files.
    """
    print("Incremental mode — preserving existing matches.")
    db.executescript(STAGE_1C_SCHEMA)  # ensure tables exist on first-ever run

    n_before = db.execute("SELECT COUNT(*) FROM files_on_disk").fetchone()[0]

    # Scan all roots; INSERT OR IGNORE means existing rows are untouched.
    t0 = time.time()
    total_scanned = 0
    seen_by_root: dict[str, set[str]] = {}
    for root, recursive, _is_master in SCAN_ROOTS:
        if not os.path.isdir(root):
            print(f"  WARNING: {root} not accessible, skipping")
            continue
        t1 = time.time()
        mode = "" if recursive else " (top-level only)"
        print(f"Scanning {root}{mode}...", end=" ", flush=True)
        n, seen = scan_folder(root, db, recursive=recursive)
        seen_by_root[root] = seen
        print(f"{n:,d} files ({time.time()-t1:.1f}s)")
        total_scanned += n

    n_after = db.execute("SELECT COUNT(*) FROM files_on_disk").fetchone()[0]

    # Prune stale file records (same logic as full run).
    n_pruned = 0
    for root, seen_rels in seen_by_root.items():
        existing = db.execute(
            "SELECT id, rel_path FROM files_on_disk WHERE folder_root = ?", (root,)
        ).fetchall()
        stale_ids = [row[0] for row in existing if row[1] not in seen_rels]
        if stale_ids:
            db.execute(
                f"DELETE FROM files_on_disk WHERE id IN ({','.join('?' * len(stale_ids))})",
                stale_ids,
            )
            n_pruned += len(stale_ids)
    db.commit()

    n_new = n_after - n_before
    print(f"\nTotal scanned: {total_scanned:,d} files ({time.time()-t0:.1f}s)")
    print(f"New files added: {n_new:,d}  |  Pruned (no longer on disk): {n_pruned:,d}")

    # Match only files not yet in transfer_file_matches.
    unmatched_count = db.execute(
        "SELECT COUNT(*) FROM files_on_disk f "
        "WHERE NOT EXISTS (SELECT 1 FROM transfer_file_matches WHERE file_id = f.id)"
    ).fetchone()[0]

    if unmatched_count == 0:
        print("All files already matched — nothing to do.")
        print_report(db)
        return

    print(f"\nMatching {unmatched_count:,d} unmatched file(s)...", end=" ", flush=True)
    t1 = time.time()
    rule_counts = match_all_files(db, unmatched_only=True)
    total_rows = sum(rule_counts.values())
    print(f"{total_rows:,d} new match rows in {time.time() - t1:.1f}s")
    for rule, cnt in sorted(rule_counts.items()):
        print(f"    {rule:35s}: {cnt:,d}")

    n_dedup = dedup_transfer_file_matches(db)
    if n_dedup:
        print(f"Removed {n_dedup:,d} duplicate match row(s).")

    if not dry_run:
        n_updated = set_has_transfer_on_disk(db)
        print(f"\nUpdated has_transfer_on_disk = 1 for {n_updated:,d} film_rolls (cumulative)")
        t1 = time.time()
        print("Backfilling transfers.filename/file_path ...", end=" ", flush=True)
        n_backfill = backfill_transfer_file_paths(db)
        print(f"{n_backfill:,d} transfers updated ({time.time() - t1:.1f}s)")
    else:
        print("\n(dry-run — DB flags and file paths not updated)")

    print_report(db)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 1c: Directory crawl & transfer verification"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Report only — don't update has_transfer_on_disk")
    parser.add_argument("--stats", action="store_true",
                        help="Show stats from previous run (no scan)")
    parser.add_argument("--incremental", action="store_true",
                        help="Only discover and match new files; preserves existing matches")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"Database not found: {DB_PATH}")
        print("Run scripts/1b_ingest_excel.py first.")
        return

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")

    if args.stats:
        print_stats_only(db)
        db.close()
        return

    if args.incremental:
        _run_incremental(db, dry_run=args.dry_run)
        db.close()
        return

    # --- Full rebuild ---
    # files_on_disk is kept across runs (stable IDs preserve ffprobe_metadata links).
    # transfer_file_matches is always rebuilt from scratch (pure derived data).
    print("Preparing Stage 1c tables...")

    # Remove any stale SAMPLE records inserted before this filter was added.
    sample_deleted = db.execute(
        "DELETE FROM files_on_disk WHERE filename LIKE '%-SAMPLE%'"
    ).rowcount
    if sample_deleted:
        print(f"  Purged {sample_deleted:,d} existing -SAMPLE record(s) from files_on_disk")
        db.commit()
    db.execute("DROP TABLE IF EXISTS transfer_file_matches")
    db.execute("UPDATE film_rolls SET has_transfer_on_disk = 0")
    # Clear file paths backfilled by a previous 1c run so they are re-verified.
    db.execute("""
        UPDATE transfers SET filename = NULL, file_path = NULL
        WHERE transfer_type NOT IN ('discovery_capture', 'digital_file')
    """)
    db.commit()
    db.executescript(STAGE_1C_SCHEMA)  # CREATE TABLE IF NOT EXISTS — safe on re-run

    # Scan directories
    t0 = time.time()
    total_scanned = 0
    seen_by_root: dict[str, set[str]] = {}   # root → rel_paths found this run
    for root, recursive, _is_master in SCAN_ROOTS:
        if not os.path.isdir(root):
            print(f"  WARNING: {root} not accessible, skipping")
            continue
        t1 = time.time()
        mode = "" if recursive else " (top-level only)"
        print(f"Scanning {root}{mode}...", end=" ", flush=True)
        n, seen = scan_folder(root, db, recursive=recursive)
        seen_by_root[root] = seen
        print(f"{n:,d} files ({time.time()-t1:.1f}s)")
        total_scanned += n

    print(f"\nTotal files scanned: {total_scanned:,d} ({time.time()-t0:.1f}s)")

    # Prune files_on_disk rows for files that have disappeared from disk.
    # Only prune roots that were accessible this run — if a root was skipped
    # (WARNING above) its existing records are left untouched.
    n_pruned = 0
    for root, seen_rels in seen_by_root.items():
        existing = db.execute(
            "SELECT id, rel_path FROM files_on_disk WHERE folder_root = ?", (root,)
        ).fetchall()
        stale_ids = [row[0] for row in existing if row[1] not in seen_rels]
        if stale_ids:
            db.execute(
                f"DELETE FROM files_on_disk WHERE id IN ({','.join('?' * len(stale_ids))})",
                stale_ids,
            )
            n_pruned += len(stale_ids)
    db.commit()
    if n_pruned:
        print(f"Pruned {n_pruned:,d} file record(s) no longer on disk.")

    # Prune records for roots that are no longer in SCAN_ROOTS at all.
    # This catches stale entries from previously-configured paths (e.g. O:/MPEG-2)
    # that have since been removed from or reorganised out of the scan list.
    configured_roots = {root for root, _, _ in SCAN_ROOTS}
    db_roots = [row[0] for row in db.execute(
        "SELECT DISTINCT folder_root FROM files_on_disk"
    ).fetchall()]
    n_root_pruned = 0
    for old_root in db_roots:
        if old_root not in configured_roots:
            result = db.execute(
                "DELETE FROM files_on_disk WHERE folder_root = ?", (old_root,)
            )
            n_root_pruned += result.rowcount
            print(f"  Removed {result.rowcount:,d} stale record(s) for defunct root: {old_root}")
    db.commit()
    if n_root_pruned:
        print(f"Pruned {n_root_pruned:,d} file record(s) from defunct scan root(s).")

    # Match all files in a single pass
    t1 = time.time()
    print("\nMatching files to transfers ...", end=" ", flush=True)
    rule_counts = match_all_files(db)
    total_rows = sum(rule_counts.values())
    print(f"{total_rows:,d} match rows in {time.time() - t1:.1f}s")
    for rule, cnt in sorted(rule_counts.items()):
        print(f"    {rule:35s}: {cnt:,d}")

    # Deduplicate: keep one row per (file_id, reel_identifier)
    n_dedup = dedup_transfer_file_matches(db)
    if n_dedup:
        print(f"Removed {n_dedup:,d} duplicate match row(s).")

    # Post-match DB updates
    if not args.dry_run:
        n_updated = set_has_transfer_on_disk(db)
        print(f"\nUpdated has_transfer_on_disk = 1 for {n_updated:,d} film_rolls")

        t1 = time.time()
        print("Backfilling transfers.filename/file_path ...", end=" ", flush=True)
        n_backfill = backfill_transfer_file_paths(db)
        print(f"{n_backfill:,d} transfers updated ({time.time() - t1:.1f}s)")
    else:
        print("\n(dry-run — DB flags and file paths not updated)")

    # Report
    print_report(db)
    db.close()


if __name__ == "__main__":
    main()
