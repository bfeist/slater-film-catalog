"""
Stage 1d: Extract ffprobe metadata for all video files on /o/.

Runs `ffprobe -v quiet -print_format json -show_format -show_streams` on every
video file in the files_on_disk table and stores the output in a new
ffprobe_metadata table.

This is designed to run overnight on ~964 video files over a network share.
ffprobe only reads container headers, so each call should take 1–10 seconds
even for 200 GB ProRes .mov files — the bottleneck is network latency, not
file size.

Features:
    - Incremental: skips files already probed (safe to re-run)
    - Stores raw JSON (full fidelity) + extracted columns (easy querying)
    - Configurable timeout per file (default 120s)
    - Detailed progress logging with ETA
    - Handles network errors gracefully (records error, continues)

Usage:
    uv run python scripts/1d_ffprobe_metadata.py                       # probe all video files
    uv run python scripts/1d_ffprobe_metadata.py --stats               # show existing stats
    uv run python scripts/1d_ffprobe_metadata.py --retry-errors        # re-probe files that errored
    uv run python scripts/1d_ffprobe_metadata.py --timeout 180         # custom timeout (seconds)
    uv run python scripts/1d_ffprobe_metadata.py --purge-missing       # delete stale records (re-run 1c first)
    uv run python scripts/1d_ffprobe_metadata.py --purge-missing --dry-run  # preview without deleting

⚠️  /o/ is STRICTLY READ-ONLY — this script only reads file headers via ffprobe.
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone

DB_PATH = "database/catalog.db"

# Video extensions to probe (lowercase, with dot).
VIDEO_EXTENSIONS = {".mov", ".mpg", ".mp4", ".mxf", ".m4v", ".ts", ".avi", ".mkv"}

# Default ffprobe timeout in seconds.  Master tape .mov files are on a network
# share and may take a few seconds to open — 120s is generous.
DEFAULT_TIMEOUT = 120

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

STAGE_1D_SCHEMA = """
-- ffprobe metadata for video files discovered on /o/.
-- One row per file_id (from files_on_disk).  Stores both the raw JSON
-- output and commonly-queried fields extracted for fast SQL access.
CREATE TABLE IF NOT EXISTS ffprobe_metadata (
    file_id             INTEGER PRIMARY KEY REFERENCES files_on_disk(id),

    -- Raw ffprobe output (full fidelity)
    probe_json          TEXT,                    -- complete ffprobe JSON

    -- Extracted from format{}
    format_name         TEXT,                    -- e.g. 'mov,mp4,m4a,3gp,3g2,mj2'
    format_long_name    TEXT,                    -- e.g. 'QuickTime / MOV'
    duration_secs       REAL,                    -- seconds (float)
    bit_rate            INTEGER,                 -- bits/sec
    probe_size_bytes    INTEGER,                 -- format.size (ffprobe-reported)
    nb_streams          INTEGER,                 -- total stream count

    -- Extracted from first video stream
    video_codec         TEXT,                    -- codec_name (e.g. 'prores')
    video_codec_long    TEXT,                    -- codec_long_name
    video_profile       TEXT,                    -- profile (e.g. 'HQ')
    video_width         INTEGER,
    video_height        INTEGER,
    video_frame_rate    TEXT,                    -- r_frame_rate (e.g. '30000/1001')
    video_display_ar    TEXT,                    -- display_aspect_ratio
    video_pix_fmt       TEXT,                    -- pix_fmt (e.g. 'yuv422p10le')
    video_color_space   TEXT,                    -- color_space
    video_bits_per_raw  TEXT,                    -- bits_per_raw_sample
    video_field_order   TEXT,                    -- field_order (interlaced?)

    -- Extracted from first audio stream
    audio_codec         TEXT,                    -- codec_name (e.g. 'pcm_s24le')
    audio_codec_long    TEXT,
    audio_sample_rate   INTEGER,                 -- e.g. 48000
    audio_channels      INTEGER,                 -- e.g. 2
    audio_channel_layout TEXT,                   -- e.g. 'stereo'
    audio_bit_rate      INTEGER,                 -- bits/sec for audio stream

    -- Derived quality label
    quality_tier        TEXT,                    -- 'master', 'hd_transfer', 'mpeg2_proxy', etc.
    quality_label       TEXT,                    -- human-readable, e.g. 'ProRes 422 HQ 1080p'

    -- Metadata
    probed_at           TEXT NOT NULL,           -- ISO 8601 timestamp
    probe_duration_secs REAL,                    -- how long the ffprobe call took
    probe_error         TEXT                     -- error message if probe failed
);

CREATE INDEX IF NOT EXISTS idx_ffp_format ON ffprobe_metadata(format_name);
CREATE INDEX IF NOT EXISTS idx_ffp_vcodec ON ffprobe_metadata(video_codec);
CREATE INDEX IF NOT EXISTS idx_ffp_res ON ffprobe_metadata(video_width, video_height);
CREATE INDEX IF NOT EXISTS idx_ffp_tier ON ffprobe_metadata(quality_tier);
CREATE INDEX IF NOT EXISTS idx_ffp_error ON ffprobe_metadata(probe_error);
"""


# ---------------------------------------------------------------------------
# ffprobe execution
# ---------------------------------------------------------------------------

def resolve_path(folder_root: str, rel_path: str) -> str:
    """Build an OS-appropriate path from files_on_disk columns.

    files_on_disk stores folder_root as 'O:/Master 1' and rel_path as
    'Tape 508 - Self Contained.mov'.  On Windows/GitBash this works directly.
    """
    return os.path.join(folder_root, rel_path)


def run_ffprobe(file_path: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[dict | None, str | None]:
    """Run ffprobe on a single file and return (parsed_json, error_string).

    Returns (dict, None) on success, (None, error_message) on failure.
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, f"timeout after {timeout}s"
    except FileNotFoundError:
        return None, "ffprobe not found on PATH"
    except OSError as e:
        return None, f"OS error: {e}"

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()[:500]
        return None, f"ffprobe exit code {result.returncode}: {stderr}"

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {e}"

    return data, None


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------

def _first_stream(probe: dict, codec_type: str) -> dict | None:
    """Return the first stream of a given codec_type, or None."""
    for s in probe.get("streams", []):
        if s.get("codec_type") == codec_type:
            return s
    return None


def _safe_int(val) -> int | None:
    """Convert to int, returning None on failure."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    """Convert to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def derive_quality(folder_root: str, video_codec: str | None,
                   video_profile: str | None, width: int | None,
                   height: int | None) -> tuple[str, str]:
    """Derive (quality_tier, quality_label) from folder + codec info.

    Returns human-friendly labels for general searching.
    """
    # Determine tier from folder — check more-specific paths first.
    folder_lower = folder_root.lower()
    if "70mm" in folder_lower or "panavision" in folder_lower:
        tier = "nara_70mm_scan"
    elif "master" in folder_lower:
        tier = "master"
    elif "mpeg-2" in folder_lower or "mpeg2" in folder_lower:
        tier = "mpeg2_proxy"
    elif "stephen" in folder_lower:
        tier = "stephen_hd"
    elif "shuttle" in folder_lower:
        tier = "shuttle"
    else:
        tier = "unknown"

    # Build human-readable label
    parts = []
    if video_codec:
        codec_display = video_codec
        if video_codec.lower() == "prores":
            codec_display = "ProRes"
            if video_profile:
                codec_display = f"ProRes {video_profile}"
        elif video_codec.lower() == "mpeg2video":
            codec_display = "MPEG-2"
        parts.append(codec_display)

    if width and height:
        # Standard resolution labels
        if height >= 2160:
            parts.append("4K")
        elif height >= 1080:
            parts.append("1080p")
        elif height >= 720:
            parts.append("720p")
        elif height >= 480:
            parts.append("480p")
        else:
            parts.append(f"{width}x{height}")

    label = " ".join(parts) if parts else "Unknown format"
    return tier, label


def extract_fields(probe: dict, folder_root: str) -> dict:
    """Extract queryable fields from ffprobe JSON output.

    Returns a dict of column_name → value for the ffprobe_metadata table.
    """
    fmt = probe.get("format", {})
    vs = _first_stream(probe, "video")
    aus = _first_stream(probe, "audio")

    video_codec = vs.get("codec_name") if vs else None
    video_profile = vs.get("profile") if vs else None
    video_width = _safe_int(vs.get("width")) if vs else None
    video_height = _safe_int(vs.get("height")) if vs else None

    tier, label = derive_quality(
        folder_root, video_codec, video_profile, video_width, video_height
    )

    return {
        "format_name": fmt.get("format_name"),
        "format_long_name": fmt.get("format_long_name"),
        "duration_secs": _safe_float(fmt.get("duration")),
        "bit_rate": _safe_int(fmt.get("bit_rate")),
        "probe_size_bytes": _safe_int(fmt.get("size")),
        "nb_streams": len(probe.get("streams", [])),

        "video_codec": video_codec,
        "video_codec_long": vs.get("codec_long_name") if vs else None,
        "video_profile": video_profile,
        "video_width": video_width,
        "video_height": video_height,
        "video_frame_rate": vs.get("r_frame_rate") if vs else None,
        "video_display_ar": vs.get("display_aspect_ratio") if vs else None,
        "video_pix_fmt": vs.get("pix_fmt") if vs else None,
        "video_color_space": vs.get("color_space") if vs else None,
        "video_bits_per_raw": vs.get("bits_per_raw_sample") if vs else None,
        "video_field_order": vs.get("field_order") if vs else None,

        "audio_codec": aus.get("codec_name") if aus else None,
        "audio_codec_long": aus.get("codec_long_name") if aus else None,
        "audio_sample_rate": _safe_int(aus.get("sample_rate")) if aus else None,
        "audio_channels": _safe_int(aus.get("channels")) if aus else None,
        "audio_channel_layout": aus.get("channel_layout") if aus else None,
        "audio_bit_rate": _safe_int(aus.get("bit_rate")) if aus else None,

        "quality_tier": tier,
        "quality_label": label,
    }


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

def ensure_schema(db: sqlite3.Connection):
    """Create the ffprobe_metadata table if it doesn't exist."""
    db.executescript(STAGE_1D_SCHEMA)


def get_video_files(db: sqlite3.Connection,
                    retry_errors: bool = False) -> list[tuple[int, str, str]]:
    """Return list of (file_id, folder_root, rel_path) for video files to probe.

    By default, skips files already probed (including errors).
    With retry_errors=True, also re-probes files that previously errored.
    """
    if retry_errors:
        # Probe files that haven't been probed OR that had errors
        return db.execute("""
            SELECT f.id, f.folder_root, f.rel_path
            FROM files_on_disk f
            WHERE f.extension IN ({exts})
              AND (f.id NOT IN (SELECT file_id FROM ffprobe_metadata)
                   OR f.id IN (SELECT file_id FROM ffprobe_metadata WHERE probe_error IS NOT NULL))
            ORDER BY f.folder_root, f.rel_path
        """.format(exts=",".join(f"'{e}'" for e in VIDEO_EXTENSIONS))).fetchall()
    else:
        # Only probe files not yet in the table at all
        return db.execute("""
            SELECT f.id, f.folder_root, f.rel_path
            FROM files_on_disk f
            WHERE f.extension IN ({exts})
              AND f.id NOT IN (SELECT file_id FROM ffprobe_metadata)
            ORDER BY f.folder_root, f.rel_path
        """.format(exts=",".join(f"'{e}'" for e in VIDEO_EXTENSIONS))).fetchall()


def upsert_probe_result(db: sqlite3.Connection, file_id: int,
                        probe: dict | None, error: str | None,
                        folder_root: str, duration: float):
    """Insert or replace ffprobe result for a file."""
    now = datetime.now(timezone.utc).isoformat()

    if probe is not None:
        fields = extract_fields(probe, folder_root)
        probe_json = json.dumps(probe, separators=(",", ":"))
    else:
        fields = {k: None for k in [
            "format_name", "format_long_name", "duration_secs", "bit_rate",
            "probe_size_bytes", "nb_streams", "video_codec", "video_codec_long",
            "video_profile", "video_width", "video_height", "video_frame_rate",
            "video_display_ar", "video_pix_fmt", "video_color_space",
            "video_bits_per_raw", "video_field_order", "audio_codec",
            "audio_codec_long", "audio_sample_rate", "audio_channels",
            "audio_channel_layout", "audio_bit_rate", "quality_tier", "quality_label",
        ]}
        probe_json = None

    db.execute("""
        INSERT OR REPLACE INTO ffprobe_metadata (
            file_id, probe_json,
            format_name, format_long_name, duration_secs, bit_rate,
            probe_size_bytes, nb_streams,
            video_codec, video_codec_long, video_profile,
            video_width, video_height, video_frame_rate,
            video_display_ar, video_pix_fmt, video_color_space,
            video_bits_per_raw, video_field_order,
            audio_codec, audio_codec_long, audio_sample_rate,
            audio_channels, audio_channel_layout, audio_bit_rate,
            quality_tier, quality_label,
            probed_at, probe_duration_secs, probe_error
        ) VALUES (
            ?, ?,
            ?, ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?
        )
    """, (
        file_id, probe_json,
        fields["format_name"], fields["format_long_name"],
        fields["duration_secs"], fields["bit_rate"],
        fields["probe_size_bytes"], fields["nb_streams"],
        fields["video_codec"], fields["video_codec_long"], fields["video_profile"],
        fields["video_width"], fields["video_height"], fields["video_frame_rate"],
        fields["video_display_ar"], fields["video_pix_fmt"], fields["video_color_space"],
        fields["video_bits_per_raw"], fields["video_field_order"],
        fields["audio_codec"], fields["audio_codec_long"], fields["audio_sample_rate"],
        fields["audio_channels"], fields["audio_channel_layout"], fields["audio_bit_rate"],
        fields["quality_tier"], fields["quality_label"],
        now, duration, error,
    ))


# ---------------------------------------------------------------------------
# Purge stale records
# ---------------------------------------------------------------------------

def purge_missing(db: sqlite3.Connection, dry_run: bool = False) -> int:
    """Delete ffprobe_metadata rows whose file_id no longer exists in files_on_disk.

    This happens when 1c_verify_transfers.py is re-run and a previously-scanned
    file was not rediscovered (e.g. a folder was removed or the share was
    partially unavailable during the last 1c run).

    With dry_run=True, prints what would be deleted without touching the DB.
    Returns the count of rows deleted (or that would be deleted).
    """
    stale = db.execute("""
        SELECT m.file_id, f_old.folder_root, f_old.filename
        FROM ffprobe_metadata m
        LEFT JOIN files_on_disk f_old ON f_old.id = m.file_id
        WHERE f_old.id IS NULL
        ORDER BY m.file_id
    """).fetchall()

    if not stale:
        print("No stale ffprobe_metadata records found — nothing to purge.")
        return 0

    print(f"{'Would delete' if dry_run else 'Deleting'} {len(stale):,d} stale record(s):")
    for file_id, folder_root, filename in stale[:50]:
        folder = (folder_root or "?").split("/")[-1]
        print(f"  file_id={file_id}  [{folder}] {filename or '(unknown)'}")
    if len(stale) > 50:
        print(f"  ... and {len(stale) - 50} more")

    if not dry_run:
        ids = [row[0] for row in stale]
        db.execute(
            f"DELETE FROM ffprobe_metadata WHERE file_id IN ({','.join('?' * len(ids))})",
            ids,
        )
        db.commit()
        print(f"Purged {len(stale):,d} stale record(s).")
    else:
        print("(dry-run — no records deleted)")

    return len(stale)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_stats(db: sqlite3.Connection):
    """Print statistics from existing ffprobe data."""
    try:
        total = db.execute("SELECT COUNT(*) FROM ffprobe_metadata").fetchone()[0]
    except sqlite3.OperationalError:
        print("No ffprobe_metadata table found. Run the script first.")
        return

    if total == 0:
        print("ffprobe_metadata table is empty. Run the script first.")
        return

    errors = db.execute(
        "SELECT COUNT(*) FROM ffprobe_metadata WHERE probe_error IS NOT NULL"
    ).fetchone()[0]
    success = total - errors

    print()
    print("=" * 70)
    print("STAGE 1d: FFPROBE METADATA REPORT")
    print("=" * 70)

    print(f"\n  Total files probed:  {total:>6,d}")
    print(f"  Successful:          {success:>6,d}")
    print(f"  Errors:              {errors:>6,d}")

    # Video files in files_on_disk that haven't been probed yet
    remaining = db.execute("""
        SELECT COUNT(*) FROM files_on_disk f
        WHERE f.extension IN ({exts})
          AND f.id NOT IN (SELECT file_id FROM ffprobe_metadata)
    """.format(exts=",".join(f"'{e}'" for e in VIDEO_EXTENSIONS))).fetchone()[0]
    print(f"  Not yet probed:      {remaining:>6,d}")

    # By quality tier
    print(f"\n  {'--- By quality tier ---':^50}")
    for row in db.execute("""
        SELECT quality_tier, COUNT(*),
               ROUND(SUM(duration_secs) / 3600.0, 1),
               ROUND(SUM(probe_size_bytes) / 1e12, 2)
        FROM ffprobe_metadata
        WHERE probe_error IS NULL
        GROUP BY quality_tier
        ORDER BY quality_tier
    """):
        tier, cnt, hours, tb = row
        hours_str = f"{hours:.1f} hrs" if hours else "?"
        tb_str = f"{tb:.2f} TB" if tb else "?"
        print(f"    {tier or 'unknown':20s}: {cnt:>5,d} files, {hours_str:>12}, {tb_str:>8}")

    # By video codec
    print(f"\n  {'--- By video codec ---':^50}")
    for row in db.execute("""
        SELECT video_codec, video_profile, COUNT(*)
        FROM ffprobe_metadata
        WHERE probe_error IS NULL
        GROUP BY video_codec, video_profile
        ORDER BY COUNT(*) DESC
    """):
        codec, profile, cnt = row
        label = codec or "none"
        if profile:
            label = f"{codec} ({profile})"
        print(f"    {label:30s}: {cnt:>5,d}")

    # By resolution
    print(f"\n  {'--- By resolution ---':^50}")
    for row in db.execute("""
        SELECT video_width, video_height, COUNT(*)
        FROM ffprobe_metadata
        WHERE probe_error IS NULL AND video_width IS NOT NULL
        GROUP BY video_width, video_height
        ORDER BY COUNT(*) DESC
    """):
        w, h, cnt = row
        print(f"    {w}x{h:>5d}: {cnt:>5,d}")

    # Duration summary
    dur = db.execute("""
        SELECT ROUND(SUM(duration_secs) / 3600.0, 1),
               ROUND(MIN(duration_secs), 1),
               ROUND(MAX(duration_secs), 1),
               ROUND(AVG(duration_secs), 1)
        FROM ffprobe_metadata WHERE probe_error IS NULL AND duration_secs IS NOT NULL
    """).fetchone()
    if dur[0]:
        print(f"\n  {'--- Duration ---':^50}")
        print(f"    Total:   {dur[0]:>10.1f} hours")
        print(f"    Min:     {dur[1]:>10.1f} seconds")
        print(f"    Max:     {dur[2]:>10.1f} seconds ({dur[2]/3600:.1f} hrs)")
        print(f"    Average: {dur[3]:>10.1f} seconds ({dur[3]/60:.1f} min)")

    # Probe timing
    timing = db.execute("""
        SELECT ROUND(SUM(probe_duration_secs), 1),
               ROUND(AVG(probe_duration_secs), 2),
               ROUND(MAX(probe_duration_secs), 1)
        FROM ffprobe_metadata
    """).fetchone()
    if timing[0]:
        print(f"\n  {'--- Probe timing ---':^50}")
        print(f"    Total probe time:  {timing[0]:>8.1f}s ({timing[0]/60:.1f} min)")
        print(f"    Average per file:  {timing[1]:>8.2f}s")
        print(f"    Max single file:   {timing[2]:>8.1f}s")

    # Errors detail
    if errors > 0:
        print(f"\n  {'--- Errors ---':^50}")
        err_rows = db.execute("""
            SELECT f.folder_root, f.filename, m.probe_error
            FROM ffprobe_metadata m
            JOIN files_on_disk f ON f.id = m.file_id
            WHERE m.probe_error IS NOT NULL
            ORDER BY f.folder_root, f.filename
        """).fetchall()
        for root, fname, err in err_rows[:20]:
            folder = root.split("/")[-1]
            print(f"    [{folder}] {fname}")
            print(f"      → {err[:120]}")
        if len(err_rows) > 20:
            print(f"    ... and {len(err_rows) - 20} more errors")

    print("=" * 70)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 1d: Extract ffprobe metadata for video files on /o/"
    )
    parser.add_argument("--stats", action="store_true",
                        help="Show existing stats (no probing)")
    parser.add_argument("--purge-missing", action="store_true",
                        help="Delete records for files no longer in files_on_disk (re-run 1c first)")
    parser.add_argument("--dry-run", action="store_true",
                        help="With --purge-missing: show what would be deleted without deleting")
    parser.add_argument("--retry-errors", action="store_true",
                        help="Re-probe files that previously errored")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"Timeout per ffprobe call in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--limit", type=int, default=0,
                        help="Only probe this many files (0 = all, useful for testing)")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"Database not found: {DB_PATH}")
        print("Run scripts/1b_ingest_excel.py and scripts/1c_verify_transfers.py first.")
        sys.exit(1)

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")

    # Always ensure table exists
    ensure_schema(db)

    if args.stats:
        print_stats(db)
        db.close()
        return

    if args.purge_missing:
        purge_missing(db, dry_run=args.dry_run)
        db.close()
        return

    # Auto-purge ffprobe records for files removed since the last 1c run.
    # This keeps the table consistent without requiring a manual --purge-missing.
    purge_missing(db, dry_run=False)

    # Get list of files to probe
    files = get_video_files(db, retry_errors=args.retry_errors)

    if args.limit > 0:
        files = files[:args.limit]

    if not files:
        print("All video files have already been probed.")
        print("Use --retry-errors to re-probe files that had errors.")
        print("Use --stats to view results.")
        db.close()
        return

    total = len(files)
    print(f"Files to probe: {total:,d}")
    print(f"Timeout per file: {args.timeout}s")
    print()

    # Track progress
    t_start = time.time()
    success_count = 0
    error_count = 0
    cumulative_probe_time = 0.0

    for i, (file_id, folder_root, rel_path) in enumerate(files, 1):
        file_path = resolve_path(folder_root, rel_path)
        short_name = f"[{folder_root.split('/')[-1]}] {os.path.basename(rel_path)}"

        # Progress + ETA
        elapsed = time.time() - t_start
        if i > 1:
            avg_per_file = elapsed / (i - 1)
            remaining_est = avg_per_file * (total - i + 1)
            eta_str = f"ETA {remaining_est/60:.0f}m" if remaining_est > 60 else f"ETA {remaining_est:.0f}s"
        else:
            eta_str = "ETA ?"

        print(f"  [{i:>4d}/{total}] {short_name:60s} ", end="", flush=True)

        t0 = time.time()
        probe, error = run_ffprobe(file_path, timeout=args.timeout)
        probe_time = time.time() - t0
        cumulative_probe_time += probe_time

        # Store result
        upsert_probe_result(db, file_id, probe, error, folder_root, probe_time)
        db.commit()

        if error:
            error_count += 1
            print(f"ERROR ({probe_time:.1f}s) {error[:60]}")
        else:
            success_count += 1
            # Show a brief summary of what we found
            dur = probe.get("format", {}).get("duration")
            dur_str = f"{float(dur)/60:.1f}min" if dur else "?"
            vcodec = _first_stream(probe, "video")
            codec_str = vcodec.get("codec_name", "?") if vcodec else "no video"
            print(f"OK ({probe_time:.1f}s) {codec_str}, {dur_str}  {eta_str}")

    # Final summary
    elapsed_total = time.time() - t_start
    print()
    print("=" * 70)
    print(f"STAGE 1d COMPLETE")
    print(f"  Probed:    {total:>6,d} files in {elapsed_total/60:.1f} minutes")
    print(f"  Success:   {success_count:>6,d}")
    print(f"  Errors:    {error_count:>6,d}")
    print(f"  Avg time:  {cumulative_probe_time/total:.2f}s per file")
    print("=" * 70)

    # Show full stats
    print_stats(db)
    db.close()


if __name__ == "__main__":
    main()
