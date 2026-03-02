"""
Stage 1e: Match shotlist PDF filenames to film_rolls identifiers.

Scans the shotlist PDF directory and matches each PDF to a film_rolls
identifier using several strategies (exact match, date-suffix stripping,
leading-dash stripping, parenthesized-copy stripping).

Stores results in a new `shotlist_pdfs` column on film_rolls as a
JSON array of filenames, and updates `has_shotlist_pdf` accordingly.

Idempotent — safe to re-run repeatedly as matching logic is refined.

Usage:
    uv run python scripts/1e_match_shotlist_pdfs.py              # full run
    uv run python scripts/1e_match_shotlist_pdfs.py --dry-run    # preview only
    uv run python scripts/1e_match_shotlist_pdfs.py --stats      # show stats only
"""

import argparse
import glob
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict

PDF_DIR = "static_assets/shotlist_pdfs"
DB_PATH = "data/01b_excel.db"


# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------

def extract_identifier(pdf_basename: str, known_ids: set[str]) -> str | None:
    """Given a PDF basename (no .pdf extension), return the matching
    film_rolls identifier or None.

    Strategies applied in order:
      1. Exact match
      2. Strip leading dash  (e.g. "-FR-A013" -> "FR-A013")
      3. Strip date suffix   (e.g. "FR-38592012-07-18" -> "FR-3859")
      4. Strip date+copy     (e.g. "FR-37662012-07-18 (2)" -> "FR-3766")
      5. Strip trailing -A   (e.g. "FR-0319-A" -> "FR-0319")
    """
    name = pdf_basename

    # 1. Exact match
    if name in known_ids:
        return name

    # 2. Strip leading dash(es)
    stripped = name.lstrip("-")
    if stripped in known_ids:
        return stripped

    # 3. Strip YYYY-MM-DD date suffix (no separator between identifier and date)
    # e.g. "FR-38592012-07-18" -> "FR-3859"
    m = re.match(r"^(.+?)\d{4}-\d{2}-\d{2}$", name)
    if m and m.group(1) in known_ids:
        return m.group(1)

    # 4. Strip date suffix + parenthesized copy number
    # e.g. "FR-37662012-07-18 (2)" -> "FR-3766"
    m = re.match(r"^(.+?)\d{4}-\d{2}-\d{2}\s*\(\d+\)$", name)
    if m and m.group(1) in known_ids:
        return m.group(1)

    # 5. Strip leading dash + date suffix combo
    stripped_name = name.lstrip("-")
    m = re.match(r"^(.+?)\d{4}-\d{2}-\d{2}(?:\s*\(\d+\))?$", stripped_name)
    if m and m.group(1) in known_ids:
        return m.group(1)

    # 6. Strip trailing -A (alternate scan suffix)
    # e.g. "FR-0319-A" -> "FR-0319"
    if name.endswith("-A") and name[:-2] in known_ids:
        return name[:-2]

    # Same with date suffix: "FR-0319-A2012-07-17" -> "FR-0319"
    m = re.match(r"^(.+?)-A\d{4}-\d{2}-\d{2}(?:\s*\(\d+\))?$", name)
    if m and m.group(1) in known_ids:
        return m.group(1)

    return None


def match_all_pdfs(
    pdf_dir: str, known_ids: set[str]
) -> tuple[dict[str, list[str]], list[str]]:
    """Match all PDFs in the directory to identifiers.

    Returns:
        matched: dict mapping identifier -> list of PDF filenames
        unmatched: list of PDF filenames that couldn't be matched
    """
    pdfs = glob.glob(os.path.join(pdf_dir, "*.pdf"))

    matched: dict[str, list[str]] = defaultdict(list)
    unmatched: list[str] = []

    for pdf_path in sorted(pdfs):
        filename = os.path.basename(pdf_path)
        basename = os.path.splitext(filename)[0]

        identifier = extract_identifier(basename, known_ids)
        if identifier:
            matched[identifier].append(filename)
        else:
            unmatched.append(filename)

    return dict(matched), unmatched


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

def ensure_column(conn: sqlite3.Connection) -> None:
    """Add shotlist_pdfs column to film_rolls if it doesn't exist."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(film_rolls)").fetchall()}
    if "shotlist_pdfs" not in cols:
        conn.execute("ALTER TABLE film_rolls ADD COLUMN shotlist_pdfs TEXT")
        conn.commit()
        print("  Added 'shotlist_pdfs' column to film_rolls")
    else:
        print("  'shotlist_pdfs' column already exists")


def apply_matches(
    conn: sqlite3.Connection,
    matched: dict[str, list[str]],
) -> None:
    """Write matched PDF filenames into the database."""
    # First clear all existing values
    conn.execute("UPDATE film_rolls SET shotlist_pdfs = NULL")
    conn.execute("UPDATE film_rolls SET has_shotlist_pdf = 0")

    # Apply matches
    update_stmt = conn.cursor()
    count = 0
    for identifier, filenames in matched.items():
        pdf_json = json.dumps(sorted(filenames))
        update_stmt.execute(
            "UPDATE film_rolls SET shotlist_pdfs = ?, has_shotlist_pdf = 1 WHERE identifier = ?",
            (pdf_json, identifier),
        )
        count += update_stmt.rowcount

    conn.commit()
    print(f"  Updated {count} film_rolls with shotlist PDF info")


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_stats(
    matched: dict[str, list[str]],
    unmatched: list[str],
    total_pdfs: int,
    total_reels: int,
) -> None:
    """Print match statistics."""
    matched_pdfs = sum(len(v) for v in matched.values())
    multi_pdf = {k: v for k, v in matched.items() if len(v) > 1}

    print(f"\n{'='*60}")
    print(f"  Shotlist PDF Matching Report")
    print(f"{'='*60}")
    print(f"  Total PDFs on disk:         {total_pdfs:>6}")
    print(f"  Total film_rolls in DB:     {total_reels:>6}")
    print(f"  PDFs matched:               {matched_pdfs:>6}  ({matched_pdfs*100/total_pdfs:.1f}%)")
    print(f"  PDFs unmatched:             {len(unmatched):>6}  ({len(unmatched)*100/total_pdfs:.1f}%)")
    print(f"  Unique reels with PDFs:     {len(matched):>6}  ({len(matched)*100/total_reels:.1f}%)")
    print(f"  Reels with multiple PDFs:   {len(multi_pdf):>6}")
    print(f"{'='*60}")

    if unmatched:
        print(f"\n  Unmatched PDFs ({len(unmatched)}):")
        for f in sorted(unmatched):
            print(f"    {f}")

    if multi_pdf:
        print(f"\n  Reels with multiple PDFs (showing first 20):")
        for ident, files in sorted(multi_pdf.items())[:20]:
            print(f"    {ident}: {', '.join(files)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Match shotlist PDFs to film_rolls")
    parser.add_argument("--dry-run", action="store_true", help="Preview matches without writing to DB")
    parser.add_argument("--stats", action="store_true", help="Show current DB stats only")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    if args.stats:
        # Just show current state
        cols = {r[1] for r in conn.execute("PRAGMA table_info(film_rolls)").fetchall()}
        if "shotlist_pdfs" not in cols:
            print("No shotlist_pdfs column yet. Run without --stats first.")
        else:
            has = conn.execute("SELECT COUNT(*) FROM film_rolls WHERE shotlist_pdfs IS NOT NULL").fetchone()[0]
            total = conn.execute("SELECT COUNT(*) FROM film_rolls").fetchone()[0]
            print(f"film_rolls with shotlist_pdfs: {has} / {total}")

            # Show a few examples
            rows = conn.execute(
                "SELECT identifier, shotlist_pdfs FROM film_rolls WHERE shotlist_pdfs IS NOT NULL LIMIT 10"
            ).fetchall()
            for r in rows:
                print(f"  {r[0]}: {r[1]}")
        conn.close()
        return

    # Load all known identifiers
    known_ids = set(
        r[0] for r in conn.execute("SELECT identifier FROM film_rolls").fetchall()
    )
    total_reels = len(known_ids)

    # Count PDFs
    all_pdfs = glob.glob(os.path.join(PDF_DIR, "*.pdf"))
    total_pdfs = len(all_pdfs)

    print(f"Scanning {total_pdfs} PDFs in {PDF_DIR}...")
    matched, unmatched = match_all_pdfs(PDF_DIR, known_ids)

    print_stats(matched, unmatched, total_pdfs, total_reels)

    if args.dry_run:
        print("\n  [DRY RUN] No database changes made.")
    else:
        print("\nWriting to database...")
        ensure_column(conn)
        apply_matches(conn, matched)
        print("Done.")

    conn.close()


if __name__ == "__main__":
    main()
