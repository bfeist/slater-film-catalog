#!/usr/bin/env python3
"""
One-time script: Download NARA shotlist PDFs from S3 and update the DB.

Source  : input_indexes/nara_apollo_70mm_metadata.json
Dest    : static_assets/shotlist_pdfs/<filename>.pdf
DB      : data/01b_excel.db
  - Appends filename to film_rolls.shotlist_pdfs (JSON array, same format as FR shotlists)
  - Sets film_rolls.has_shotlist_pdf = 1

Usage:
    uv run python scripts/one_time/1b_download_nara_shotlists.py
    uv run python scripts/one_time/1b_download_nara_shotlists.py --dry-run
    uv run python scripts/one_time/1b_download_nara_shotlists.py --limit 10
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent.parent
JSON_PATH  = ROOT / "input_indexes" / "nara_apollo_70mm_metadata.json"
DB_PATH    = ROOT / "data" / "01b_excel.db"
DEST_DIR   = ROOT / "static_assets" / "shotlist_pdfs"


# ---------------------------------------------------------------------------
# Identifier helper (mirrors 1b_ingest_first_steps.py)
# ---------------------------------------------------------------------------

def normalize_nara_id(raw: str) -> str:
    """Strip '255-' prefix from NARA RG-255 identifiers."""
    s = str(raw).strip()
    return s[4:] if s.startswith("255-") else s


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def collect_shotlist_urls(records: list[dict]) -> list[tuple[str, str]]:
    """Return list of (identifier, pdf_url) pairs where a document PDF exists."""
    results = []
    for rec in records:
        local_id = str(rec.get("local_identifier", "")).strip()
        if not local_id:
            continue
        identifier = normalize_nara_id(local_id)
        for dobj in (rec.get("digital_objects") or []):
            if not isinstance(dobj, dict):
                continue
            obj_type = str(dobj.get("type", "")).lower()
            if obj_type not in ("document", "pdf"):
                continue
            url = (dobj.get("download_url") or dobj.get("url") or "").strip()
            if url and url.lower().endswith(".pdf"):
                results.append((identifier, url))
                break  # one shotlist per reel
    return results


def download_one(url: str, dest: Path, retries: int = 3) -> bool:
    """Download *url* to *dest*. Returns True on success."""
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                dest.write_bytes(resp.read())
            return True
        except Exception as exc:
            wait = 2 ** attempt
            print(f"      [attempt {attempt}/{retries}] {exc} — retry in {wait}s", file=sys.stderr)
            if attempt < retries:
                time.sleep(wait)
    return False


def run(args: argparse.Namespace) -> None:
    with open(JSON_PATH, encoding="utf-8") as fh:
        records = json.load(fh)

    shotlists = collect_shotlist_urls(records)
    print(f"Found {len(shotlists)} shotlist PDF URLs in {JSON_PATH.name}")

    if args.limit:
        shotlists = shotlists[: args.limit]
        print(f"  Limiting to first {args.limit}")

    if args.dry_run:
        print("\nDry-run — no files will be downloaded or DB updated.\n")
        for identifier, url in shotlists:
            fn = url.split("/")[-1].split("?")[0]
            print(f"  {identifier:20s}  {fn}")
        return

    DEST_DIR.mkdir(parents=True, exist_ok=True)

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")

    downloaded = 0
    skipped    = 0
    failed     = 0

    for i, (identifier, url) in enumerate(shotlists, 1):
        fn   = url.split("/")[-1].split("?")[0]
        dest = DEST_DIR / fn

        prefix = f"[{i}/{len(shotlists)}] {identifier}"

        if dest.exists() and not args.force:
            print(f"  {prefix} — already exists, skipping")
            skipped += 1
        else:
            print(f"  {prefix} — downloading {fn} ...", end=" ", flush=True)
            ok = download_one(url, dest)
            if ok:
                size_kb = dest.stat().st_size // 1024
                print(f"OK ({size_kb} KB)")
                downloaded += 1
            else:
                print("FAILED", file=sys.stderr)
                failed += 1
                continue  # don't update DB for failed downloads

        # Append filename to shotlist_pdfs JSON array (same structure as FR shotlists)
        if fn:
            row = db.execute(
                "SELECT shotlist_pdfs FROM film_rolls WHERE identifier = ?", (identifier,)
            ).fetchone()
            existing: list[str] = json.loads(row[0]) if (row and row[0]) else []
            if fn not in existing:
                existing.append(fn)
            db.execute(
                "UPDATE film_rolls SET has_shotlist_pdf = 1, shotlist_pdfs = ? WHERE identifier = ?",
                (json.dumps(sorted(existing)), identifier),
            )

    db.execute(
        "INSERT OR REPLACE INTO _manifest VALUES (?,?)",
        ("nara_shotlists_downloaded_at", time.strftime("%Y-%m-%dT%H:%M:%S")),
    )
    db.execute(
        "INSERT OR REPLACE INTO _manifest VALUES (?,?)",
        ("nara_shotlists_count", str(downloaded + skipped)),
    )
    db.commit()
    db.close()

    print(
        f"\nDone. Downloaded: {downloaded}, Skipped (already present): {skipped}, "
        f"Failed: {failed}"
    )
    print(f"PDFs stored in: {DEST_DIR}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download NARA shotlist PDFs from S3 and update film_rolls DB."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be downloaded without doing anything",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-download even if the PDF already exists on disk",
    )
    parser.add_argument(
        "--limit", type=int, default=0, metavar="N",
        help="Stop after N downloads (0 = no limit; useful for testing)",
    )
    args = parser.parse_args()

    if not JSON_PATH.exists():
        print(f"ERROR: JSON not found: {JSON_PATH}", file=sys.stderr)
        sys.exit(1)
    if not DB_PATH.exists() and not args.dry_run:
        print(f"ERROR: DB not found: {DB_PATH}", file=sys.stderr)
        print("Run scripts/one_time/1b_ingest_excel.py first.", file=sys.stderr)
        sys.exit(1)

    run(args)


if __name__ == "__main__":
    main()
