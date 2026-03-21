"""
One-time catalog analysis reports.

Each report is a self-contained function that reads from catalog.db and
prints findings to stdout.  Run one report by name or all at once.

Usage:
    uv run python scripts/one_time/analyze_catalog.py                 # all reports
    uv run python scripts/one_time/analyze_catalog.py --list          # list available reports
    uv run python scripts/one_time/analyze_catalog.py --report mpeg2_only
    uv run python scripts/one_time/analyze_catalog.py --report mpeg2_only --verbose
"""

import argparse
import sqlite3
import sys
import textwrap
from typing import Callable

DB_PATH = "database/catalog.db"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEPARATOR = "=" * 72
SUBSEP    = "-" * 72


def section(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def subsection(title: str) -> None:
    print(f"\n{SUBSEP}")
    print(f"  {title}")
    print(SUBSEP)


# ---------------------------------------------------------------------------
# Report: mpeg2_only
#
# Identifiers whose only on-disk proxy lives in MPEG-Proxies/MPEG-2 —
# meaning they are NOT also covered by any other proxy subfolder
# (MPEG-2_FR/, NARA/, MPEG-2_Imagery_Online_proxy_files/, etc.).
# ---------------------------------------------------------------------------

def report_mpeg2_only(db: sqlite3.Connection, verbose: bool = False) -> None:
    """
    Report: identifiers only reachable via MPEG-Proxies/MPEG-2

    Finds identifiers that have at least one matched file under
    O:/MPEG-Proxies/MPEG-2/ but NO matched file under any other subfolder
    of O:/MPEG-Proxies.

    Files in Master 1-4 / FR-Masters / 70mm are *not* considered proxies and
    are excluded from this comparison — this report is purely about proxy
    folder coverage.
    """
    section("REPORT: mpeg2_only — identifiers exclusive to MPEG-Proxies/MPEG-2")
    print(textwrap.dedent("""\
        Looks for reel identifiers that are matched to at least one file under
        O:/MPEG-Proxies/MPEG-2/ but have NO match in any other subfolder of
        O:/MPEG-Proxies (e.g. MPEG-2_FR/, NARA/, MPEG-2_Imagery_Online_proxy_files/).
    """))

    # Identifiers covered by MPEG-2/ subfolder
    in_mpeg2 = db.execute("""
        SELECT DISTINCT tfm.reel_identifier
        FROM transfer_file_matches tfm
        JOIN files_on_disk fod ON fod.id = tfm.file_id
        WHERE fod.folder_root = 'O:/MPEG-Proxies'
          AND fod.rel_path LIKE 'MPEG-2/%'
          AND tfm.reel_identifier IS NOT NULL
    """).fetchall()

    # Identifiers covered by OTHER proxy subfolders (anything under MPEG-Proxies
    # that is NOT MPEG-2/)
    in_other = db.execute("""
        SELECT DISTINCT tfm.reel_identifier
        FROM transfer_file_matches tfm
        JOIN files_on_disk fod ON fod.id = tfm.file_id
        WHERE fod.folder_root = 'O:/MPEG-Proxies'
          AND fod.rel_path NOT LIKE 'MPEG-2/%'
          AND tfm.reel_identifier IS NOT NULL
    """).fetchall()

    set_mpeg2 = {r[0] for r in in_mpeg2}
    set_other = {r[0] for r in in_other}

    mpeg2_only   = sorted(set_mpeg2 - set_other)
    in_both      = sorted(set_mpeg2 & set_other)
    other_only   = sorted(set_other - set_mpeg2)

    print(f"  Identifiers with a file in MPEG-2/:              {len(set_mpeg2):>6,}")
    print(f"  Identifiers with a file in another proxy folder: {len(set_other):>6,}")
    print(f"  In BOTH (overlap):                               {len(in_both):>6,}")
    print(f"  MPEG-2 only (no other proxy):                    {len(mpeg2_only):>6,}")
    print(f"  Other proxy only (not in MPEG-2):                {len(other_only):>6,}")

    # Breakdown of which specific proxy subfolders cover the MPEG-2-only set
    if mpeg2_only:
        subsection(f"Proxy subfolder breakdown for 'other' folders ({len(set_other):,} identifiers)")
        rows = db.execute("""
            SELECT
                CASE
                    WHEN fod.rel_path LIKE 'MPEG-2_FR/%'                              THEN 'MPEG-2_FR/'
                    WHEN fod.rel_path LIKE 'NARA/%'                                   THEN 'NARA/'
                    WHEN fod.rel_path LIKE 'MPEG-2_Imagery_Online_proxy_files/%'      THEN 'MPEG-2_Imagery_Online_proxy_files/'
                    ELSE 'other: ' || SUBSTR(fod.rel_path, 1, INSTR(fod.rel_path || '/', '/'))
                END AS subfolder,
                COUNT(DISTINCT tfm.reel_identifier) AS identifiers,
                COUNT(DISTINCT fod.id)              AS files
            FROM transfer_file_matches tfm
            JOIN files_on_disk fod ON fod.id = tfm.file_id
            WHERE fod.folder_root = 'O:/MPEG-Proxies'
              AND fod.rel_path NOT LIKE 'MPEG-2/%'
              AND tfm.reel_identifier IS NOT NULL
            GROUP BY subfolder
            ORDER BY identifiers DESC
        """).fetchall()
        print(f"  {'Subfolder':<50} {'Identifiers':>11}  {'Files':>6}")
        print(f"  {'-'*50} {'-'*11}  {'-'*6}")
        for subfolder, identifiers, files in rows:
            print(f"  {subfolder:<50} {identifiers:>11,}  {files:>6,}")

    # Listing of MPEG-2-only identifiers
    subsection(f"Identifiers exclusive to MPEG-Proxies/MPEG-2 ({len(mpeg2_only):,})")
    if not mpeg2_only:
        print("  (none — every MPEG-2 identifier is also covered by another proxy folder)")
        return

    if verbose:
        # Verbose: show each identifier with its matching file(s)
        print(f"  {'Identifier':<20}  {'MPEG-2 file(s)'}")
        print(f"  {'-'*20}  {'-'*48}")
        detail_rows = db.execute("""
            SELECT tfm.reel_identifier, fod.rel_path
            FROM transfer_file_matches tfm
            JOIN files_on_disk fod ON fod.id = tfm.file_id
            WHERE fod.folder_root = 'O:/MPEG-Proxies'
              AND fod.rel_path LIKE 'MPEG-2/%'
              AND tfm.reel_identifier IN ({})
            ORDER BY tfm.reel_identifier, fod.rel_path
        """.format(",".join("?" * len(mpeg2_only))), mpeg2_only).fetchall()

        current = None
        for identifier, rel_path in detail_rows:
            if identifier != current:
                print(f"  {identifier:<20}  {rel_path}")
                current = identifier
            else:
                print(f"  {'':20}  {rel_path}")
    else:
        # Compact: one identifier per line, columnar
        cols = 4
        col_w = 20
        for i in range(0, len(mpeg2_only), cols):
            row = mpeg2_only[i:i + cols]
            print("  " + "".join(f"{v:<{col_w}}" for v in row))

    print(f"\n  Total: {len(mpeg2_only):,} identifiers are ONLY covered by MPEG-Proxies/MPEG-2.")


# ---------------------------------------------------------------------------
# Report registry
# ---------------------------------------------------------------------------

REPORTS: dict[str, tuple[str, Callable]] = {
    "mpeg2_only": (
        "Identifiers whose only proxy is in MPEG-Proxies/MPEG-2 (not covered by other proxy subfolders)",
        report_mpeg2_only,
    ),
    # Add new reports here, e.g.:
    # "no_proxy": (
    #     "Film rolls with no proxy file at all",
    #     report_no_proxy,
    # ),
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-time catalog analysis reports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--report", "-r",
        metavar="NAME",
        help="Run a specific report by name (default: all reports)",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available reports and exit",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show extra detail in reports that support it",
    )
    parser.add_argument(
        "--db",
        default=DB_PATH,
        metavar="PATH",
        help=f"Path to catalog.db (default: {DB_PATH})",
    )
    args = parser.parse_args()

    if args.list:
        print("Available reports:")
        for name, (description, _) in REPORTS.items():
            print(f"  {name:<20}  {description}")
        return

    if args.report and args.report not in REPORTS:
        print(f"Error: unknown report '{args.report}'", file=sys.stderr)
        print(f"Available: {', '.join(REPORTS)}", file=sys.stderr)
        sys.exit(1)

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    to_run = [args.report] if args.report else list(REPORTS)

    for name in to_run:
        _, fn = REPORTS[name]
        fn(db, verbose=args.verbose)

    print(f"\n{SEPARATOR}")
    print(f"  Done. ({len(to_run)} report(s) run)")
    print(SEPARATOR)


if __name__ == "__main__":
    main()
