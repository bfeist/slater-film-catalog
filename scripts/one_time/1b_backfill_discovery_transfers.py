"""
Stage 1b (backfill): Add missing discovery_capture transfers to catalog.db.

Two gap types are fixed:

  Gap 1 — discovery_shotlist.identifier already names an FR roll, but no
           discovery_capture transfer was ingested from the Master List
           (because the Master List row had no Discovery Tape column value).

  Gap 2 — An FR number is referenced inside shotlist_raw text (e.g. "FR-9537"
           or "FR9537") but no discovery_capture transfer exists for that FR
           on that tape.

Both sources are cross-checked against film_rolls so only known identifiers
are inserted.

Usage:
    uv run python scripts/one_time/1b_backfill_discovery_transfers.py          # dry run
    uv run python scripts/one_time/1b_backfill_discovery_transfers.py --apply  # write to DB
    uv run python scripts/one_time/1b_backfill_discovery_transfers.py --stats  # summary only
"""

import argparse
import re
import sqlite3

DB_PATH = "database/catalog.db"

# Matches FR-9537, FR_9537, FR9537 (3-5 digit number)
FR_PATTERN = re.compile(r"\bFR[-_]?(\d{3,5})\b", re.IGNORECASE)

TAPE_FOLDER_RANGES = [
    (501, 562, "Master 1"),
    (563, 625, "Master 2"),
    (626, 712, "Master 3"),
    (713, 886, "Master 4"),
]


def tape_path(tape_num: int) -> tuple[str | None, str | None]:
    for start, end, folder in TAPE_FOLDER_RANGES:
        if start <= tape_num <= end:
            fn = f"Tape {tape_num} - Self Contained.mov"
            return fn, f"/o/{folder}/{fn}"
    return None, None


def find_missing_transfers(db: sqlite3.Connection) -> list[dict]:
    """Return list of dicts describing every new transfer that should be inserted."""
    known_fr: set[str] = {
        row[0]
        for row in db.execute("SELECT identifier FROM film_rolls WHERE id_prefix='FR'")
    }

    # Pre-load existing discovery_capture transfers as (reel_identifier, tape_number) set
    existing: set[tuple[str, str]] = {
        (row[0], row[1])
        for row in db.execute(
            "SELECT reel_identifier, tape_number FROM transfers WHERE transfer_type='discovery_capture'"
        )
    }

    missing: list[dict] = []

    rows = db.execute(
        "SELECT rowid, identifier, tape_number, shotlist_raw FROM discovery_shotlist"
    ).fetchall()

    for _rowid, ident, tape, raw in rows:
        if tape is None:
            continue

        tape_str = str(tape)
        fn, fp = tape_path(tape)

        candidates: set[str] = set()

        # --- Gap 1: identifier column names a known FR roll ---
        if ident and re.match(r"^FR-", str(ident)):
            if ident in known_fr:
                candidates.add(ident)

        # --- Gap 2: FR numbers embedded in shotlist_raw text ---
        if raw:
            for num in FR_PATTERN.findall(raw):
                for candidate in (f"FR-{num}", f"FR-{int(num):04d}", f"FR-{int(num)}"):
                    if candidate in known_fr:
                        candidates.add(candidate)
                        break

        for fr_id in candidates:
            if (fr_id, tape_str) not in existing:
                missing.append(
                    {
                        "reel_identifier": fr_id,
                        "tape_number": tape_str,
                        "filename": fn,
                        "file_path": fp,
                        "source": (
                            "identifier_column"
                            if (ident and fr_id == ident)
                            else "shotlist_raw_scan"
                        ),
                    }
                )
                # Prevent duplicates within this scan run
                existing.add((fr_id, tape_str))

    return missing


def apply_transfers(db: sqlite3.Connection, missing: list[dict]) -> int:
    inserted = 0
    for m in missing:
        db.execute(
            "INSERT INTO transfers "
            "(reel_identifier, transfer_type, source_tab, tape_number, filename, file_path) "
            "VALUES (?,?,?,?,?,?)",
            (
                m["reel_identifier"],
                "discovery_capture",
                f"backfill_{m['source']}",
                m["tape_number"],
                m["filename"],
                m["file_path"],
            ),
        )
        inserted += 1
    db.commit()
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill missing discovery_capture transfers in catalog.db"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write to the database (default is dry-run)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show current transfer counts and exit without scanning",
    )
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH)

    if args.stats:
        total = db.execute("SELECT COUNT(*) FROM transfers WHERE transfer_type='discovery_capture'").fetchone()[0]
        by_src = db.execute(
            "SELECT source_tab, COUNT(*) FROM transfers WHERE transfer_type='discovery_capture' GROUP BY source_tab ORDER BY 2 DESC"
        ).fetchall()
        print(f"discovery_capture transfers: {total:,}")
        for src, cnt in by_src:
            print(f"  {src or '(null)':40s}: {cnt:,}")
        db.close()
        return

    missing = find_missing_transfers(db)

    by_source: dict[str, list[dict]] = {}
    for m in missing:
        by_source.setdefault(m["source"], []).append(m)

    print(f"Missing transfers found: {len(missing)}")
    for src, items in sorted(by_source.items()):
        print(f"\n  Source: {src} ({len(items)} entries)")
        for m in sorted(items, key=lambda x: (int(x['tape_number']), x['reel_identifier'])):
            print(f"    tape={m['tape_number']}  reel={m['reel_identifier']}")

    if not missing:
        print("Nothing to do.")
        db.close()
        return

    if args.apply:
        n = apply_transfers(db, missing)
        print(f"\nInserted {n} new discovery_capture transfers.")
        # Update manifest
        db.execute(
            "INSERT OR REPLACE INTO _manifest VALUES (?,?)",
            ("backfill_discovery_transfers", str(n)),
        )
        db.commit()
        print("Manifest updated.")
    else:
        print("\n(Dry run — use --apply to write to the database)")

    db.close()


if __name__ == "__main__":
    main()
