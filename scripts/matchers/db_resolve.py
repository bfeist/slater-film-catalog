"""
Database resolution: map a ParsedFilename to matching transfer rows.

Resolution strategies (tried in order):

    tape_number
        "Tape 508" files → transfers WHERE transfer_type='discovery_capture'
        AND tape_number=NNN.

    lto_vfr
        LTO-prefixed files (L000003_FR-27) → transfers WHERE
        video_file_ref = 'L000003/FR-27' (or padded variants from candidates).

    lto_fallback
        When no video_file_ref match is found, fall back to all transfers on
        the LTO tape: WHERE lto_number = 'L000003'.

    identifier
        All other files → film_rolls WHERE identifier = candidate (case-
        insensitive) → transfers WHERE reel_identifier = <DB canonical>.
        Each candidate in ParsedFilename.candidates is tried in order.

    *_no_transfer variants
        When the roll/tape is found in the DB but has no associated transfers,
        a match with transfer_id=NULL is returned so the file is still recorded
        in transfer_file_matches (and surfaces in the --stats report).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from matchers.filename_parser import ParsedFilename


@dataclass
class ResolvedMatch:
    """A single transfer (or no-transfer) match for a file."""
    transfer_id: int | None
    reel_identifier: str | None
    match_rule: str
    tape_number: int | None = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve(db: sqlite3.Connection, parsed: ParsedFilename) -> list[ResolvedMatch]:
    """Return transfer matches for *parsed*.

    Returns an empty list when the file should be skipped entirely (ignored
    placeholder) or when no match can be found anywhere.
    """
    if parsed.is_ignored:
        return []

    if parsed.tape_number is not None:
        return _resolve_tape(db, parsed.tape_number)

    if parsed.lto_number:
        return _resolve_lto(db, parsed.lto_number, parsed.candidates)

    if parsed.candidates:
        return _resolve_identifier(db, parsed.candidates)

    return []


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------

def _resolve_tape(db: sqlite3.Connection, tape_number: int) -> list[ResolvedMatch]:
    xfers = db.execute(
        "SELECT id, reel_identifier FROM transfers "
        "WHERE transfer_type = 'discovery_capture' AND tape_number = ?",
        (str(tape_number),),
    ).fetchall()
    if xfers:
        return [
            ResolvedMatch(xfer_id, reel_ident, "tape_number", tape_number)
            for xfer_id, reel_ident in xfers
        ]

    # No transfer rows — fall back to discovery_shotlist, which records which
    # film rolls live on each tape even when no formal transfer row was created.
    shotlist_rows = db.execute(
        "SELECT identifier FROM discovery_shotlist WHERE tape_number = ?",
        (tape_number,),
    ).fetchall()
    matches: list[ResolvedMatch] = []
    for (ident_raw,) in shotlist_rows:
        if ident_raw is None:
            continue
        # identifier may be comma-separated: "FR-7404,FR-7405,FR-7406"
        for ident in [s.strip() for s in ident_raw.split(",") if s.strip()]:
            matches.append(ResolvedMatch(None, ident, "tape_shotlist_only", tape_number))
    if matches:
        return matches

    # Tape appears in discovery_shotlist but rolls were never linked to it in the
    # spreadsheet.  Different from tape_number_no_transfer (tape unknown entirely).
    if shotlist_rows:
        return [ResolvedMatch(None, None, "tape_known_no_rolls", tape_number)]

    return [ResolvedMatch(None, None, "tape_number_no_transfer", tape_number)]


def _resolve_lto(
    db: sqlite3.Connection,
    lto_number: str,
    candidates: list[str],
) -> list[ResolvedMatch]:
    """Try video_file_ref match, then LTO-level fallback, then identifier search."""

    # 1. Try each candidate as a video_file_ref: "L000003/FR-27"
    for candidate in candidates:
        vfr = f"{lto_number}/{candidate}"
        xfers = db.execute(
            "SELECT id, reel_identifier FROM transfers WHERE video_file_ref = ?",
            (vfr,),
        ).fetchall()
        if xfers:
            return [
                ResolvedMatch(xfer_id, reel_ident, "lto_vfr")
                for xfer_id, reel_ident in xfers
            ]

    # 2. LTO-level fallback: all transfers stored on this LTO tape.
    xfers = db.execute(
        "SELECT id, reel_identifier FROM transfers WHERE lto_number = ?",
        (lto_number,),
    ).fetchall()
    if xfers:
        return [
            ResolvedMatch(xfer_id, reel_ident, "lto_fallback")
            for xfer_id, reel_ident in xfers
        ]

    # 3. Identifier-based fallback.
    if candidates:
        return _resolve_identifier(db, candidates)

    return []


def _resolve_identifier(
    db: sqlite3.Connection,
    candidates: list[str],
) -> list[ResolvedMatch]:
    """Try each candidate against film_rolls → transfers."""
    for candidate in candidates:
        row = db.execute(
            "SELECT identifier FROM film_rolls WHERE identifier = ? COLLATE NOCASE",
            (candidate,),
        ).fetchone()
        if not row:
            continue

        db_ident = row[0]  # canonical form from DB
        xfers = db.execute(
            "SELECT id, reel_identifier FROM transfers WHERE reel_identifier = ?",
            (db_ident,),
        ).fetchall()
        if xfers:
            return [
                ResolvedMatch(xfer_id, reel_ident, "identifier")
                for xfer_id, reel_ident in xfers
            ]
        # Roll exists but has no transfers yet.
        return [ResolvedMatch(None, db_ident, "identifier_no_transfer")]

    return []
