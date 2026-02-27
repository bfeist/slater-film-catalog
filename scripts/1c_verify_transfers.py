"""
Stage 1c: Directory crawl & transfer verification.

Scans /o/ Master folders and MPEG-2 (READ-ONLY) to build a file inventory,
then matches discovered files against the transfers table in 01b_excel.db.

Currently scans:
    /o/Master 1/   (tapes 501–562)
    /o/Master 2/   (tapes 563–625)
    /o/Master 3/   (tapes 626–712)
    /o/Master 4/   (tapes 713–886)
    /o/MPEG-2/     (684 MPEG-2 proxy files, LNNNNNN[_suffix].mpg)

Reports:
    - Files matched to transfers
    - Files that could NOT be resolved to any transfer
    - Transfers that claim a file exists but none was found on disk
    - Sets film_rolls.has_transfer_on_disk = 1 for confirmed matches

Usage:
    uv run python scripts/1c_verify_transfers.py              # full scan
    uv run python scripts/1c_verify_transfers.py --dry-run    # report only, don't update DB
    uv run python scripts/1c_verify_transfers.py --stats      # show existing stats

⚠️  /o/ is STRICTLY READ-ONLY — this script only reads directory listings.
"""

import argparse
import os
import re
import sqlite3
import time
from pathlib import Path

DB_PATH = "data/01b_excel.db"

# Folders to scan — /o/ is READ-ONLY, we only list files.
# On Windows, the network share is mounted as O:\ (accessed as O:/ in GitBash).
# Master 4 has large subdirs (BBC/, LMOTM/) that aren't tape files — scan top-level only.
SCAN_ROOTS = [
    ("O:/Master 1", True),     # (path, recursive)
    ("O:/Master 2", True),
    ("O:/Master 3", True),
    ("O:/Master 4", False),    # top-level only — skip BBC/, LMOTM subdirs
    ("O:/MPEG-2",   False),    # MPEG-2 proxy files
]

# Naming convention: tape number ranges → Master folders.
# Used instead of a DB table to resolve tape numbers to expected paths.
TAPE_FOLDER_RANGES = [
    (501, 562, "Master 1"),
    (563, 625, "Master 2"),
    (626, 712, "Master 3"),
    (713, 886, "Master 4"),
]


def tape_master_folder(tape_num: int) -> str | None:
    """Return the Master folder name for a tape number, or None if out of range."""
    for start, end, folder in TAPE_FOLDER_RANGES:
        if start <= tape_num <= end:
            return folder
    return None


def tape_expected_path(tape_num: int) -> str | None:
    """Return the expected /o/ path for a tape number."""
    folder = tape_master_folder(tape_num)
    if folder:
        return f"/o/{folder}/Tape {tape_num} - Self Contained.mov"
    return None


# Placeholder patterns to completely ignore (these are not real files).
IGNORE_RE = re.compile(
    r"not missing.*doesn.?t exist|doesn.?t exist.*not missing|MISSING",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Schema additions (tables added by this script)
# ---------------------------------------------------------------------------

STAGE_1C_SCHEMA = """
-- Files discovered on /o/ via directory crawl.
CREATE TABLE IF NOT EXISTS files_on_disk (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_root     TEXT NOT NULL,           -- e.g. '/o/Master 1'
    rel_path        TEXT NOT NULL,           -- path relative to folder_root
    filename        TEXT NOT NULL,
    extension       TEXT,                    -- lowercase, e.g. '.mov'
    size_bytes      INTEGER,
    UNIQUE(folder_root, rel_path)
);

CREATE INDEX IF NOT EXISTS idx_fod_filename ON files_on_disk(filename);
CREATE INDEX IF NOT EXISTS idx_fod_ext ON files_on_disk(extension);
CREATE INDEX IF NOT EXISTS idx_fod_root ON files_on_disk(folder_root);

-- Matches between on-disk files and transfers.
CREATE TABLE IF NOT EXISTS transfer_file_matches (
    file_id         INTEGER NOT NULL REFERENCES files_on_disk(id),
    transfer_id     INTEGER REFERENCES transfers(id),          -- NULL if no transfer found
    tape_number     INTEGER,                                   -- populated for tape matches
    match_rule      TEXT NOT NULL,                              -- e.g. 'tape_number', 'filename_exact', 'identifier_in_path'
    reel_identifier TEXT,                                       -- the film_roll identifier this resolves to (if known)
    UNIQUE(file_id, transfer_id)
);

CREATE INDEX IF NOT EXISTS idx_tfm_file ON transfer_file_matches(file_id);
CREATE INDEX IF NOT EXISTS idx_tfm_transfer ON transfer_file_matches(transfer_id);
CREATE INDEX IF NOT EXISTS idx_tfm_reel ON transfer_file_matches(reel_identifier);
"""


# ---------------------------------------------------------------------------
# Directory scanning
# ---------------------------------------------------------------------------

def scan_folder(root: str, db: sqlite3.Connection, recursive: bool = True) -> int:
    """Walk a folder tree and insert files into files_on_disk.

    If recursive=False, only scans the top-level directory (no subdirs).
    Returns count of files inserted.
    """
    count = 0
    root_path = Path(root)

    if recursive:
        walker = os.walk(root)
    else:
        # Top-level only: yield a single (dirpath, dirnames, filenames) tuple
        try:
            entries = list(os.scandir(root))
            files = [e.name for e in entries if e.is_file()]
            walker = [(root, [], files)]
        except OSError:
            return 0

    for dirpath, _dirnames, filenames in walker:
        for fname in filenames:
            # Skip placeholder files ("not missing - doesn't exist", "MISSING")
            if IGNORE_RE.search(fname):
                continue

            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root).replace("\\", "/")
            ext = os.path.splitext(fname)[1].lower() or None

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
    return count


# ---------------------------------------------------------------------------
# Matching rules
# ---------------------------------------------------------------------------

# Regex: "Tape 508 - Self Contained.mov" or "Tape 507 - Self Contained - Part 1 Of 2.mov"
TAPE_RE = re.compile(r"^Tape\s+(\d+)\s*-", re.IGNORECASE)


def match_tape_files(db: sqlite3.Connection) -> tuple[int, int]:
    """Match 'Tape NNN' filenames to discovery_capture transfers.

    Uses the naming convention (TAPE_FOLDER_RANGES) to validate tape numbers
    instead of a separate tape_to_file table.

    Returns (matched_files, matched_transfers).
    """
    matched_files = 0
    matched_xfers = 0

    rows = db.execute(
        "SELECT id, filename FROM files_on_disk "
        "WHERE folder_root IN ('O:/Master 1', 'O:/Master 2', 'O:/Master 3', 'O:/Master 4')"
    ).fetchall()

    for file_id, filename in rows:
        m = TAPE_RE.match(filename)
        if not m:
            continue

        tape_num = int(m.group(1))

        # Find all discovery_capture transfers for this tape
        xfers = db.execute(
            "SELECT id, reel_identifier FROM transfers "
            "WHERE transfer_type = 'discovery_capture' AND tape_number = ?",
            (str(tape_num),),
        ).fetchall()

        if xfers:
            for xfer_id, reel_ident in xfers:
                db.execute(
                    "INSERT OR IGNORE INTO transfer_file_matches "
                    "(file_id, transfer_id, tape_number, match_rule, reel_identifier) "
                    "VALUES (?,?,?,?,?)",
                    (file_id, xfer_id, tape_num, "tape_number", reel_ident),
                )
                matched_xfers += 1
        else:
            # Tape file exists on disk but no discovery_capture transfer references it
            db.execute(
                "INSERT OR IGNORE INTO transfer_file_matches "
                "(file_id, transfer_id, tape_number, match_rule, reel_identifier) "
                "VALUES (?,?,?,?,?)",
                (file_id, None, tape_num, "tape_number_no_transfer", None),
            )

        matched_files += 1

    db.commit()
    return matched_files, matched_xfers


# ---------------------------------------------------------------------------
# MPEG-2 matching
# ---------------------------------------------------------------------------

# MPEG-2 filenames: L000003_FR-27.mpg  or  L000007.mpg
MPEG2_RE = re.compile(r"^(L\d+)(?:_(.+))?\.mpg$", re.IGNORECASE)


def match_mpeg2_files(db: sqlite3.Connection) -> tuple[int, int, int]:
    """Match MPEG-2 proxy files to transfers via video_file_ref and lto_number.

    Filename patterns:
        L000003_FR-27.mpg       → video_file_ref = 'L000003/FR-0027'  (/ → _ on disk)
        L000007.mpg             → lto_number = 'L000007'  (all transfers on that LTO)
        L000803_FR-AK-3.mpg     → video_file_ref = 'L000803/FR-AK-3'

    Returns (matched_files, matched_transfers, unmatched_files).
    """
    matched_files = 0
    matched_xfers = 0
    unmatched_files = 0

    rows = db.execute(
        "SELECT id, filename FROM files_on_disk WHERE folder_root = 'O:/MPEG-2'"
    ).fetchall()

    for file_id, filename in rows:
        m = MPEG2_RE.match(filename)
        if not m:
            unmatched_files += 1
            continue

        lto = m.group(1)       # e.g. 'L000003'
        suffix = m.group(2)    # e.g. 'FR-27' or None

        xfers = []

        if suffix:
            # Build video_file_ref: L000003_FR-27 → L000003/FR-27
            vfr_raw = f"{lto}/{suffix}"
            # Try exact match first
            xfers = db.execute(
                "SELECT id, reel_identifier FROM transfers WHERE video_file_ref = ?",
                (vfr_raw,),
            ).fetchall()

            # If no match, try zero-padding the numeric part of FR-NNN
            if not xfers and suffix.startswith("FR-"):
                fr_rest = suffix[3:]  # e.g. '27'
                # Pad purely numeric FR numbers to 4 digits
                if fr_rest.isdigit() and len(fr_rest) < 4:
                    vfr_padded = f"{lto}/FR-{fr_rest.zfill(4)}"
                    xfers = db.execute(
                        "SELECT id, reel_identifier FROM transfers WHERE video_file_ref = ?",
                        (vfr_padded,),
                    ).fetchall()

            # Fallback: try LIKE match for edge cases (e.g. AK15 vs AK-15)
            if not xfers:
                xfers = db.execute(
                    "SELECT id, reel_identifier FROM transfers "
                    "WHERE video_file_ref LIKE ? AND lto_number = ?",
                    (f"{lto}/%", lto),
                ).fetchall()
                # Filter to only those whose vfr suffix matches closely
                if len(xfers) > 1:
                    # Don't do a broad match — leave as unresolved
                    xfers = []
        else:
            # Bare L-number file: match by lto_number (all transfers on this LTO),
            # falling back to video_file_ref prefix if lto_number field is missing.
            xfers = db.execute(
                "SELECT id, reel_identifier FROM transfers WHERE lto_number = ?",
                (lto,),
            ).fetchall()
            if not xfers:
                xfers = db.execute(
                    "SELECT id, reel_identifier FROM transfers "
                    "WHERE video_file_ref LIKE ? || '/%'",
                    (lto,),
                ).fetchall()

        if xfers:
            rule = "mpeg2_vfr" if suffix else "mpeg2_lto"
            for xfer_id, reel_ident in xfers:
                db.execute(
                    "INSERT OR IGNORE INTO transfer_file_matches "
                    "(file_id, transfer_id, tape_number, match_rule, reel_identifier) "
                    "VALUES (?,?,?,?,?)",
                    (file_id, xfer_id, None, rule, reel_ident),
                )
                matched_xfers += 1
            matched_files += 1
        elif suffix:
            # Suffixed file couldn't exact-match via video_file_ref.
            # Fall back to matching by LTO number (left of '/') — links to ALL
            # transfers on that LTO tape, same as a bare L-number file would.
            lto_xfers = db.execute(
                "SELECT id, reel_identifier FROM transfers WHERE lto_number = ?",
                (lto,),
            ).fetchall()
            if not lto_xfers:
                # Also try matching against the prefix of video_file_ref
                lto_xfers = db.execute(
                    "SELECT id, reel_identifier FROM transfers "
                    "WHERE video_file_ref LIKE ? || '/%'",
                    (lto,),
                ).fetchall()
            if lto_xfers:
                for xfer_id, reel_ident in lto_xfers:
                    db.execute(
                        "INSERT OR IGNORE INTO transfer_file_matches "
                        "(file_id, transfer_id, tape_number, match_rule, reel_identifier) "
                        "VALUES (?,?,?,?,?)",
                        (file_id, xfer_id, None, "mpeg2_lto_fallback", reel_ident),
                    )
                    matched_xfers += 1
                matched_files += 1
            else:
                unmatched_files += 1
        else:
            unmatched_files += 1

    db.commit()
    return matched_files, matched_xfers, unmatched_files


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
    to the actual on-disk file. Prefers the most specific match rule:
        mpeg2_vfr > mpeg2_lto_fallback > mpeg2_lto > tape_number

    Returns count of transfers updated.
    """
    # Rank match rules — lower number = more specific = preferred.
    RULE_RANK = {
        "mpeg2_vfr": 1,
        "mpeg2_lto_fallback": 2,
        "mpeg2_lto": 3,
        "tape_number": 4,
        "tape_number_no_transfer": 5,
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
          AND (m.file_id IS NULL OR m.match_rule = 'tape_number_no_transfer')
        ORDER BY f.folder_root, f.filename
    """).fetchall()

    if tape_unmatched:
        for root, fname, size in tape_unmatched:
            folder = root.split("/")[-1]
            size_str = f"{size/1024/1024/1024:.1f} GB" if size and size > 0 else "??"
            print(f"    [{folder}] {fname}  ({size_str})")
    else:
        print("    (none — all tape files resolved to transfers)")

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

    # Drop previous 1c tables and rebuild
    print("Preparing Stage 1c tables...")
    db.execute("DROP TABLE IF EXISTS transfer_file_matches")
    db.execute("DROP TABLE IF EXISTS files_on_disk")
    db.execute("UPDATE film_rolls SET has_transfer_on_disk = 0")
    # Clear file paths that were backfilled by a previous 1c run (lto_copy + tape matches),
    # but leave discovery_capture file_path (set by 1b from naming convention) intact.
    db.execute("""
        UPDATE transfers SET filename = NULL, file_path = NULL
        WHERE transfer_type NOT IN ('discovery_capture', 'digital_file')
    """)
    db.commit()
    db.executescript(STAGE_1C_SCHEMA)

    # Scan directories
    t0 = time.time()
    total_scanned = 0
    for root, recursive in SCAN_ROOTS:
        if not os.path.isdir(root):
            print(f"  WARNING: {root} not accessible, skipping")
            continue
        t1 = time.time()
        mode = "" if recursive else " (top-level only)"
        print(f"Scanning {root}{mode}...", end=" ", flush=True)
        n = scan_folder(root, db, recursive=recursive)
        print(f"{n:,d} files ({time.time()-t1:.1f}s)")
        total_scanned += n

    print(f"\nTotal files scanned: {total_scanned:,d} ({time.time()-t0:.1f}s)")

    # Match tape files (Masters 1-4)
    t1 = time.time()
    print("\nMatching tape files (Masters 1-4)...", end=" ", flush=True)
    mf, mx = match_tape_files(db)
    print(f"{mf:,d} files → {mx:,d} transfer links ({time.time()-t1:.1f}s)")

    # Match MPEG-2 files
    t1 = time.time()
    print("Matching MPEG-2 files...", end=" ", flush=True)
    m2f, m2x, m2u = match_mpeg2_files(db)
    print(f"{m2f:,d} files → {m2x:,d} transfer links, {m2u:,d} unmatched ({time.time()-t1:.1f}s)")

    # Set has_transfer_on_disk
    if not args.dry_run:
        n_updated = set_has_transfer_on_disk(db)
        print(f"\nUpdated has_transfer_on_disk = 1 for {n_updated:,d} film_rolls")

        # Backfill filename/file_path on transfers from matched files
        t1 = time.time()
        print("Backfilling transfers.filename/file_path...", end=" ", flush=True)
        n_backfill = backfill_transfer_file_paths(db)
        print(f"{n_backfill:,d} transfers updated ({time.time()-t1:.1f}s)")
    else:
        print("\n(dry-run — has_transfer_on_disk not updated)")

    # Report
    print_report(db)
    db.close()


if __name__ == "__main__":
    main()
