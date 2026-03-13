"""
Disk vs Database audit.

Walks the entire O:/ drive and compares every file found against the
`files_on_disk` table in database/catalog.db. Surfaces:
  - Top-level folders on disk with their total size
  - How much of each folder is covered by the DB vs not
  - Folders/paths entirely absent from the DB
  - Optionally writes a full CSV of missing files

O:/ is READ-ONLY — this script only reads directory listings and sizes.

Usage examples
--------------
Fast folder-level summary (recommended first pass):
    uv run python scripts/files_audit/disk_vs_db.py --top-only

Fast summary + shallow size estimate for uncovered folders:
    uv run python scripts/files_audit/disk_vs_db.py --top-only --estimate-sizes

Full walk of the entire drive (very slow for 80 TB):
    uv run python scripts/files_audit/disk_vs_db.py

Full walk + write all missing files to CSV:
    uv run python scripts/files_audit/disk_vs_db.py --csv scripts/files_audit/missing_files.csv

Scan one subfolder only:
    uv run python scripts/files_audit/disk_vs_db.py --root "O:/BBC Apollo Coverage"
"""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

DB_PATH = "database/catalog.db"
DRIVE_ROOT = "O:/"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def fmt_bytes(n: int) -> str:
    """Human-readable bytes (TB/GB/MB/KB)."""
    for unit, threshold in [("TB", 1 << 40), ("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)]:
        if abs(n) >= threshold:
            return f"{n / threshold:.2f} {unit}"
    return f"{n} B"


def normalise(path: str) -> str:
    """Lowercase, forward slashes, no trailing slash."""
    return path.replace("\\", "/").rstrip("/").lower()


def top_folder_of(full_path: str, root: str) -> str:
    """
    Return the immediate child of 'root' that 'full_path' lives under.
    E.g.  top_folder_of("O:/Master 1/foo/bar.mov", "O:/")  ->  "O:/Master 1"
    """
    rel = os.path.relpath(full_path, root)
    parts = Path(rel).parts
    return os.path.join(root, parts[0]).replace("\\", "/") if parts else root


# Roots crawled by 1c_verify_transfers.py -- used purely for annotation.
SCANNED_ROOTS_1C = {
    normalise(p) for p in [
        "O:/Master 1",
        "O:/Master 2",
        "O:/Master 3",
        "O:/Master 4",
        "O:/70mm Panavision Collection",
        "O:/FR-Masters",
        "O:/MPEG-Proxies",
    ]
}


# ---------------------------------------------------------------------------
# DB loading
# ---------------------------------------------------------------------------

def load_db_files(db_path: str) -> tuple[set[str], dict[str, int]]:
    """
    Returns:
        known_paths -- set of normalised full paths present in files_on_disk
        path_sizes  -- normalised path -> size_bytes
    """
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT folder_root, rel_path, size_bytes FROM files_on_disk"
    ).fetchall()
    conn.close()

    known: set[str] = set()
    sizes: dict[str, int] = {}
    for folder_root, rel_path, size_bytes in rows:
        full = (folder_root.rstrip("/") + "/" + rel_path).replace("\\", "/")
        norm = normalise(full)
        known.add(norm)
        sizes[norm] = size_bytes or 0

    print(f"  Loaded {len(known):,} paths from database  ({fmt_bytes(sum(sizes.values()))} indexed)")
    return known, sizes


def build_folder_index(db_sizes: dict[str, int]) -> dict[str, tuple[int, int]]:
    """
    Pre-aggregate DB sizes by top-level folder prefix for fast lookups.
    Returns {normalised_top_folder: (file_count, total_bytes)}
    """
    agg: dict[str, list] = defaultdict(lambda: [0, 0])
    for norm_path, sz in db_sizes.items():
        parts = norm_path.split("/")   # e.g. ["o:", "master 1", "foo", "bar.mov"]
        top = (parts[0] + "/" + parts[1]) if len(parts) >= 2 else parts[0]
        agg[top][0] += 1
        agg[top][1] += sz
    return {k: (v[0], v[1]) for k, v in agg.items()}


# ---------------------------------------------------------------------------
# shallow size estimator
# ---------------------------------------------------------------------------

def estimate_folder_size(root: str) -> tuple[int, int]:
    """Walk 'root' and return (file_count, total_bytes). Prints progress every 30 s."""
    count = total = 0
    t_last = time.time()
    for dirpath, _, filenames in os.walk(root, onerror=lambda e: None):
        for fname in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, fname))
                count += 1
            except OSError:
                pass
        if time.time() - t_last > 30:
            t_last = time.time()
            print(f"    ... {count:,} files / {fmt_bytes(total)}  [{dirpath[:70]}]")
    return count, total


# ---------------------------------------------------------------------------
# full disk walk
# ---------------------------------------------------------------------------

def walk_root(
    root: str,
    known_paths: set[str],
    *,
    collect_missing: bool = False,
) -> dict[str, dict]:
    """
    Full recursive walk of 'root'. Returns stats dict keyed by top-level folder.
    collect_missing=True populates 'missing_files' lists (needed for CSV export).
    """
    def blank():
        return {
            "disk_bytes": 0, "db_bytes": 0, "missing_bytes": 0,
            "disk_count": 0, "db_count": 0, "missing_count": 0,
            "missing_files": [],
        }

    stats: dict[str, dict] = defaultdict(blank)
    scanned = errors = 0
    t_last = time.time()

    print(f"\n  Walking {root} ...  (may take a long time for large volumes)")

    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
        dirnames.sort()
        for fname in filenames:
            full_path = os.path.join(dirpath, fname).replace("\\", "/")
            norm = normalise(full_path)
            top = top_folder_of(full_path, root)

            try:
                size = os.path.getsize(full_path)
            except OSError:
                errors += 1
                continue

            scanned += 1
            s = stats[top]
            s["disk_bytes"] += size
            s["disk_count"] += 1

            if norm in known_paths:
                s["db_bytes"] += size
                s["db_count"] += 1
            else:
                s["missing_bytes"] += size
                s["missing_count"] += 1
                if collect_missing:
                    s["missing_files"].append({"path": full_path, "size": size})

            if time.time() - t_last > 30:
                t_last = time.time()
                total_disk = sum(x["disk_bytes"] for x in stats.values())
                print(f"    ... {scanned:,} files | {fmt_bytes(total_disk)} on disk | {dirpath[:70]}")

    print(f"  Walk complete: {scanned:,} files, {errors} read errors.")
    return dict(stats)


# ---------------------------------------------------------------------------
# reporting: full walk
# ---------------------------------------------------------------------------

def print_full_summary(stats: dict, db_total_bytes: int, root: str = "") -> None:
    N = 30
    SEP = "  " + "-" * 72
    strip = root.replace("\\", "/").rstrip("/") + "/"
    print()
    print(f"  {'FOLDER':<{N}} {'DISK':>10} {'IN DB':>10} {'MISSING':>10} {'#MISS':>6}")
    print(SEP)
    total_disk = total_db = total_miss = total_miss_ct = 0
    for folder in sorted(stats):
        s = stats[folder]
        name = folder.replace("\\", "/")
        if strip:
            name = name.replace(strip, "").replace(strip.lower(), "")
        if not name:
            name = "(root)"
        if len(name) > N:
            name = name[:N - 1] + "~"
        print(
            f"  {name:<{N}} {fmt_bytes(s['disk_bytes']):>10} "
            f"{fmt_bytes(s['db_bytes']):>10} {fmt_bytes(s['missing_bytes']):>10} "
            f"{s['missing_count']:>6,}"
        )
        total_disk += s["disk_bytes"]
        total_db += s["db_bytes"]
        total_miss += s["missing_bytes"]
        total_miss_ct += s["missing_count"]
    print(SEP)
    print(
        f"  {'TOTAL':<{N}} {fmt_bytes(total_disk):>10} "
        f"{fmt_bytes(total_db):>10} {fmt_bytes(total_miss):>10} "
        f"{total_miss_ct:>6,}"
    )
    print()
    print(f"  DB total (files_on_disk):  {fmt_bytes(db_total_bytes)}")
    print(f"  Disk total (this scan):    {fmt_bytes(total_disk)}")
    print(f"  Unindexed gap:             {fmt_bytes(total_disk - total_db)}")
    print()


def write_csv(stats: dict, csv_path: str) -> None:
    rows = sum(len(s["missing_files"]) for s in stats.values())
    print(f"  Writing {rows:,} missing-file rows -> {csv_path}")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["top_level_folder", "full_path", "size_bytes", "size_human"])
        for folder in sorted(stats):
            for e in stats[folder]["missing_files"]:
                w.writerow([folder, e["path"], e["size"], fmt_bytes(e["size"])])
    print("  Done.")


# ---------------------------------------------------------------------------
# reporting: top-only mode
# ---------------------------------------------------------------------------

def top_only_mode(
    root: str,
    known_paths: set[str],
    db_sizes: dict[str, int],
    *,
    estimate_sizes: bool = False,
) -> None:
    """
    List top-level folders with DB coverage without a full disk walk.
    With --estimate-sizes, walks each uncovered folder for real disk sizes.
    """
    try:
        children = sorted(
            os.path.join(root, e.name).replace("\\", "/")
            for e in os.scandir(root)
            if e.is_dir(follow_symlinks=False)
        )
    except OSError as exc:
        print(f"ERROR listing {root}: {exc}", file=sys.stderr)
        return

    db_index = build_folder_index(db_sizes)

    print(f"  {len(children)} top-level folder(s) under {root}\n")

    N = 28   # folder name column width
    print(f"  {'FOLDER':<{N}}  STATUS")
    print("  " + "-" * 70)

    missing_folders: list[tuple[str, int, int]] = []   # (path, file_count, bytes)

    for child in children:
        norm_child = normalise(child)
        label = child.replace(root.rstrip("/") + "/", "")
        if len(label) > N:
            label = label[:N - 1] + "~"

        db_count, db_bytes = db_index.get(norm_child, (0, 0))
        in_1c = "[1c]" if norm_child in SCANNED_ROOTS_1C else "[!1c]"

        if db_count == 0:
            if estimate_sizes:
                print(f"  Estimating: {child} ...")
                disk_fc, disk_bc = estimate_folder_size(child)
            else:
                disk_fc, disk_bc = 0, 0

            size_str = f" ({fmt_bytes(disk_bc)}, {disk_fc:,} files)" if disk_bc else ""
            missing_folders.append((child, disk_fc, disk_bc))
            print(f"  {label:<{N}}  NOT IN DB{size_str}  {in_1c}")
        else:
            print(f"  {label:<{N}}  {db_count:,} files / {fmt_bytes(db_bytes)}  {in_1c}")

    print()

    if missing_folders:
        total_missing_bytes = sum(bc for _, _, bc in missing_folders)
        print(f"  FOLDERS WITH ZERO DB COVERAGE ({len(missing_folders)}):")
        print()
        for path, fc, bc in missing_folders:
            if bc:
                print(f"    {path}  ({fc:,} files, {fmt_bytes(bc)})")
            else:
                print(f"    {path}")
        print()
        if total_missing_bytes:
            print(f"  Total unindexed size:  {fmt_bytes(total_missing_bytes)}")
        else:
            print("  Add --estimate-sizes to walk each uncovered folder for real disk sizes.")
    else:
        print("  All top-level folders have at least some DB coverage.")
    print()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--db", default=DB_PATH, help=f"SQLite DB path (default: {DB_PATH})")
    ap.add_argument("--root", default=DRIVE_ROOT, help=f"Root to scan (default: {DRIVE_ROOT})")
    ap.add_argument("--csv", metavar="PATH", help="Write missing files to CSV at this path")
    ap.add_argument(
        "--top-only",
        action="store_true",
        help="Fast mode: list top-level folders with DB coverage, skip full disk walk",
    )
    ap.add_argument(
        "--estimate-sizes",
        action="store_true",
        help="Used with --top-only: walk each uncovered folder to calculate real disk sizes",
    )
    args = ap.parse_args()

    print(f"\nDisk vs Database Audit")
    print(f"  DB:   {args.db}")
    print(f"  Root: {args.root}")
    print()

    print("Loading database ...")
    known_paths, db_sizes = load_db_files(args.db)
    db_total_bytes = sum(db_sizes.values())

    if args.top_only:
        top_only_mode(
            args.root,
            known_paths,
            db_sizes,
            estimate_sizes=args.estimate_sizes,
        )
        return

    stats = walk_root(args.root, known_paths, collect_missing=bool(args.csv))
    print_full_summary(stats, db_total_bytes, root=args.root)

    if args.csv:
        write_csv(stats, args.csv)


if __name__ == "__main__":
    main()
