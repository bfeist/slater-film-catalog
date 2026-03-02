"""
Identifier extraction from arbitrary video filenames.

Given a filename, extracts one or more candidate reel identifiers (e.g. FR-1029,
AK-23, PV-54) plus ancillary metadata (LTO tape number, tape reel number).

The returned ``candidates`` list is ordered most-specific → least-specific.
The caller should try each against the database and use the first hit.

Handles all known naming conventions across /o/:

    Tape reel:         "Tape 508 - Self Contained.mov"
                         → tape_number=508

    LTO MPEG-2:        "L000003_FR-27.mpg"
                         → lto='L000003', candidates=['FR-27', 'FR-0027', ...]
                       "L000003_FR-419.mpg"
                         → lto='L000003', candidates=['FR-419', ...]
                       "L000007.mpg"  (bare tape-level proxy, no reel suffix)
                         → lto='L000007', candidates=[]  (method: lto_bare)

    Bare identifier:   "FR-8346.mpg"
                         → candidates=['FR-8346']

    JSC asset suffix:  "FR-C176_jsc2014m009788.mp4"
                         → candidates=['FR-C176']
                       "AK-023_jsc2014m000914.mp4"
                         → candidates=['AK-23', 'AK-023', ...]

    NARA 255- prefix:  "255-fr-1029.mp4"        → candidates=['FR-1029', ...]
                       "255-hq-199-NEG-r1.mov"  → candidates=['HQ-199-NEG-R1', 'HQ-199-NEG', 'HQ-199', ...]
                       "255-pv-10-r1_mar31.mov" → candidates=['PV-10-R1', 'PV-10', ...]
                       "255-FR-0145_HD_MASTER.mov" → candidates=['FR-145', 'FR-0145', ...]
                       "255-se-69-300.mov"      → candidates=['SE-69-300', 'SE-69', ...]

The 255- NARA prefix is ALWAYS stripped before identifier lookup — it is a
collection-level prefix and is never stored in the database.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Compiled regexes
# ---------------------------------------------------------------------------

# Files that are not real media (placeholder / missing entries) — skip entirely.
IGNORE_RE = re.compile(
    r"not missing.*doesn.?t exist|doesn.?t exist.*not missing|MISSING",
    re.IGNORECASE,
)

# NARA collection prefix: "255-" or "255_"
NARA_PREFIX_RE = re.compile(r"^255[-_]", re.IGNORECASE)

# LTO tape prefix: "L000003_FR-27" → lto='L000003', rest='FR-27'
LTO_RE = re.compile(r"^(L\d+)[_-](.+)$", re.IGNORECASE)

# Bare LTO tape file: "L000007.mpg" — whole-tape proxy with no reel suffix.
LTO_BARE_RE = re.compile(r"^L\d+$", re.IGNORECASE)

# Tape reel filenames: "Tape 508 - Self Contained.mov"
TAPE_RE = re.compile(r"^Tape\s+(\d+)\s*-", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class ParsedFilename:
    """Result of filename parsing."""

    filename: str               # original filename as given
    stem: str                   # filename without extension

    # Identifier candidates to try against the database, ordered most → least
    # specific.  Empty for tape/ignored files.
    candidates: list[str] = field(default_factory=list)

    # Set when the filename has an LTO prefix (L000NNN_...) so the resolver
    # can fall back to an LTO-level match in transfers.lto_number / video_file_ref.
    lto_number: str | None = None

    # Set for "Tape NNN - ..." style filenames.
    tape_number: int | None = None

    # How the filename was parsed (for logging / debugging).
    parse_method: str = "unknown"

    is_ignored: bool = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_filename(filename: str) -> ParsedFilename:
    """Parse *filename* and return a ``ParsedFilename``.

    The ``.candidates`` list holds identifier strings to try against the
    database, ordered most-specific first.  An empty list means there is
    nothing actionable to look up (ignored placeholder, or unrecognised format).
    """
    stem = os.path.splitext(filename)[0]

    # Skip placeholder / noise files.
    if IGNORE_RE.search(filename):
        return ParsedFilename(
            filename=filename, stem=stem,
            parse_method="ignored", is_ignored=True,
        )

    # ---- Tape reel files -----------------------------------------------
    m = TAPE_RE.match(stem)
    if m:
        return ParsedFilename(
            filename=filename, stem=stem,
            tape_number=int(m.group(1)),
            parse_method="tape",
        )

    working = stem
    lto_number: str | None = None
    parse_method = "bare"

    # ---- Strip NARA 255- prefix ----------------------------------------
    is_nara = bool(NARA_PREFIX_RE.match(working))
    if is_nara:
        working = NARA_PREFIX_RE.sub("", working, count=1)
        parse_method = "nara"

    # ---- Strip LTO prefix (not present on NARA files) ------------------
    if not is_nara:
        lto_m = LTO_RE.match(working)
        if lto_m:
            lto_number = lto_m.group(1).upper()
            working = lto_m.group(2)
            parse_method = "lto"
        elif LTO_BARE_RE.match(working):
            # Bare tape-level file: "L000007.mpg" — no reel suffix.
            # Return immediately with lto_number set and no candidates so that
            # _resolve_lto falls back to all transfers on this tape.
            return ParsedFilename(
                filename=filename, stem=stem,
                candidates=[],
                lto_number=working.upper(),
                parse_method="lto_bare",
            )

    # ---- Take only the segment before the first underscore -------------
    # "FR-C176_jsc2014m009788" → "FR-C176"
    # "pv-54_apr11_RESCAN"     → "pv-54"
    # "FR-0145_HD_MASTER"      → "FR-0145"
    core = working.split("_")[0]

    candidates = _build_candidates(core)

    return ParsedFilename(
        filename=filename, stem=stem,
        candidates=candidates,
        lto_number=lto_number,
        parse_method=parse_method,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_candidates(raw: str) -> list[str]:
    """Return identifier candidates from *raw* (most → least specific).

    Produces:
      * The full uppercased string.
      * Progressive right-trimmed variants (strip trailing hyphen segments).
      * Zero-padding / zero-stripping variants for purely-numeric terminal
        segments.

    Examples
    --------
    "FR-C176"          → ["FR-C176"]
    "FR-27"            → ["FR-27", "FR-0027"]
    "pv-54"            → ["PV-54", "PV-0054"]
    "hq-199-NEG-r1"   → ["HQ-199-NEG-R1", "HQ-199-NEG", "HQ-199", "HQ-0199"]
    "FR-1536-r1"       → ["FR-1536-R1", "FR-1536"]
    "ak-023"           → ["AK-023", "AK-23"]
    "se-69-300"        → ["SE-69-300", "SE-69"]
    "del-517"          → ["DEL-517"]
    """
    raw = raw.strip().upper()
    if not raw or "-" not in raw:
        return []

    parts = raw.split("-")
    if len(parts) < 2:
        return []

    seen: set[str] = set()
    result: list[str] = []

    def _add(c: str) -> None:
        if c and c not in seen:
            seen.add(c)
            result.append(c)

    # Walk from longest (full) to shortest (2 parts minimum).
    for i in range(len(parts), 1, -1):
        candidate = "-".join(parts[:i])
        _add(candidate)

        # For a purely-numeric terminal segment, also add zero-padded /
        # zero-stripped variants (e.g. "FR-27" ↔ "FR-0027").
        last = parts[i - 1]
        if last.isdigit():
            num = int(last)
            prefix_base = "-".join(parts[: i - 1]) + "-"
            _add(prefix_base + str(num))           # strip leading zeros
            _add(prefix_base + last.zfill(4))      # pad to 4 digits

    return result
