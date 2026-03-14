"""
Generate alternate titles for film reels using Ollama (gemma3:12b).

Purpose: Rephrase each reel title just enough that it won't surface in searches
against other archival databases, while preserving all factual content.
The alternate title must be NO more elaborate than the original — if the
original is terse, the alternate should be equally terse.

Schema change: adds  film_rolls.alternate_title  TEXT  (nullable) on first run.

Usage:
    # Sample 50 random titles (default)
    uv run python scripts/title_gen/generate_alt_titles.py

    # Process all reels that lack an alternate title
    uv run python scripts/title_gen/generate_alt_titles.py --all

    # Force-regenerate titles for ALL reels (including existing titles)
    uv run python scripts/title_gen/generate_alt_titles.py --force

    # Force-regenerate for specific identifiers
    uv run python scripts/title_gen/generate_alt_titles.py --ids FR-0133 FR-5315

    # Dry-run: print results without writing to DB
    uv run python scripts/title_gen/generate_alt_titles.py --dry-run

    # Custom sample size
    uv run python scripts/title_gen/generate_alt_titles.py --sample 100
"""

import argparse
import concurrent.futures
import json
import os
import sqlite3
import sys
import textwrap
import time
import re
import urllib.error
import urllib.request

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DB_PATH = os.path.join(PROJECT_ROOT, "database", "catalog.db")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma3:12b"

# Words too common to use for overlap checking
_STOP_WORDS = frozenset(
    "a an and at by for from in of on or the to with is was were be".split()
)

# Matches film-roll identifiers that may be embedded in title strings.
# Ordered most-specific first so parenthesised annotations like
# "(FR-0046 DISCOVERY 24P HDCAM)" are consumed before the bare ID.
_REEL_ID_RE = re.compile(
    r'\(\s*(?:FR-[A-G]?\d+(?:-\d+)?|AK-\d+|BRF\d+[A-Z]?)'
    r'(?:\s+[A-Z0-9][A-Z0-9\s\./]*?)?\s*\)'   # optional annotation + close paren
    r'|FR-[A-G]?\d+(?:-\d+)?'                   # bare FR-XXXX[-N]
    r'|AK-\d+'                                   # bare AK-NNN
    r'|BRF\d+[A-Z]?',                            # bare BRFnnnX
    re.IGNORECASE,
)


def _strip_reel_ids(text: str) -> str:
    """Remove film-roll identifier patterns from *text* and tidy whitespace."""
    text = _REEL_ID_RE.sub('', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)          # collapse runs of spaces
    text = re.sub(r'\s+([,;:\)])', r'\1', text)     # remove space before punctuation
    text = text.strip(' \t\n-.,;:')
    return text


def _significant_words(text: str) -> set[str]:
    """Extract significant lowercase words (length >= 2, not stop words)."""
    return {
        w for w in re.sub(r"[^a-zA-Z0-9]", " ", text).lower().split()
        if len(w) >= 2 and w not in _STOP_WORDS
    }

SYSTEM_PROMPT = textwrap.dedent("""\
    You rephrase archival NASA film-reel titles. Your goal is minimal rewording — just enough
    that the exact original phrase won't match a verbatim text search.

    Rules — follow ALL of them:
    1. Output ONLY the rephrased title. No quotes, no explanation, no preamble.
    2. Preserve every factual detail EXACTLY: names, dates, numbers, missions, locations,
       timecodes, GMT values. Do NOT alter any numeric or date value.
    3. Do NOT expand abbreviations or acronyms. Keep JSC, KSC, MSC, EVA, STS, MOCR, AV,
       ALSEP, OMS, FGB, ISS, SRB, ASCAN, H-8mm, OVCR, HDCAM, CSM, LM, SM, CM, SMS,
       WSTF, LEM, S-IVB, S-IB, ESSA, PFPC, TGS, OAST, GT, SA, MILA, etc. as-is.
       Also keep state abbreviations (Ga, Ut, Oh, Wa, Id, etc.) abbreviated.
    4. Do NOT replace "Astronaut" with "Cosmonaut" — these are NASA records about American
       astronauts. Keep terms like "Astronaut" and "Crew" unchanged.
    5. Make only small changes: swap word order, replace 1-2 common words with synonyms
       (e.g. "Part" → "Section", "Launch" → "Liftoff", "Press Conference" → "Media Briefing"),
       or lightly restructure phrasing.
    6. Do NOT add information, context, elaboration, or words not implied by the original.
    7. The rephrased title must have roughly the same word count as the original (±20%).
    8. Keep the same level of formality and technical tone.
    9. Never wrap output in quotes.
""")

SYSTEM_PROMPT_CONSERVATIVE = textwrap.dedent("""\
    You make the absolute minimum change to an archival NASA film-reel title so it no longer
    matches a verbatim text search.

    Rules — follow ALL of them:
    1. Output ONLY the modified title. No quotes, no explanation, no preamble.
    2. Change NO MORE than 1 or 2 words in the entire title. Every other word must be kept
       exactly as written, including all numbers, dates, abbreviations, and proper nouns.
    3. Acceptable change types: swap a single common word for a direct synonym
       (e.g. "Part" → "Segment", "Launch" → "Liftoff", "View" → "Shot"),
       or reorder two adjacent words if it reads naturally.
    4. Do NOT change acronyms, abbreviations, numbers, names, locations, or dates.
    5. Do NOT add or remove words — keep word count identical.
    6. Never wrap output in quotes.
""")


def ensure_column(db: sqlite3.Connection) -> None:
    """Add alternate_title column to film_rolls if it doesn't exist."""
    cols = {row[1] for row in db.execute("PRAGMA table_info(film_rolls)")}
    if "alternate_title" not in cols:
        db.execute("ALTER TABLE film_rolls ADD COLUMN alternate_title TEXT")
        db.commit()
        print("[migration] film_rolls += alternate_title")


def call_ollama(title: str, *, conservative: bool = False) -> str:
    """Call Ollama API to generate an alternate title."""
    clean_title = _strip_reel_ids(title)  # remove embedded identifiers before prompting
    system = SYSTEM_PROMPT_CONSERVATIVE if conservative else SYSTEM_PROMPT
    prompt = (
        f"Change only 1 or 2 words in this archival film title:\n{clean_title}"
        if conservative
        else f"Rephrase this archival film title:\n{clean_title}"
    )
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {
            "temperature": 0.4,
            "num_predict": 256,
        },
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read())
    return body["response"].strip().strip('"').strip("'")


def fetch_sample(db: sqlite3.Connection, n: int) -> list[tuple[str, str]]:
    """Return n random (identifier, title) pairs that have a title but no alternate_title."""
    return db.execute(
        """SELECT identifier, title FROM film_rolls
           WHERE title IS NOT NULL AND (alternate_title IS NULL OR alternate_title = '')
           ORDER BY RANDOM() LIMIT ?""",
        (n,),
    ).fetchall()


def fetch_by_ids(db: sqlite3.Connection, ids: list[str]) -> list[tuple[str, str]]:
    """Return (identifier, title) for specific identifiers."""
    placeholders = ",".join("?" for _ in ids)
    return db.execute(
        f"SELECT identifier, title FROM film_rolls WHERE identifier IN ({placeholders})",
        ids,
    ).fetchall()


def fetch_all_missing(db: sqlite3.Connection) -> list[tuple[str, str]]:
    """Return all (identifier, title) pairs missing an alternate_title."""
    return db.execute(
        """SELECT identifier, title FROM film_rolls
           WHERE title IS NOT NULL AND (alternate_title IS NULL OR alternate_title = '')
           ORDER BY identifier"""
    ).fetchall()


def fetch_all_reels(db: sqlite3.Connection) -> list[tuple[str, str]]:
    """Return all (identifier, title) pairs with a title (regardless of alternate_title status)."""
    return db.execute(
        """SELECT identifier, title FROM film_rolls
           WHERE title IS NOT NULL
           ORDER BY identifier"""
    ).fetchall()


def process_batch(
    db: sqlite3.Connection,
    rows: list[tuple[str, str]],
    *,
    dry_run: bool = False,
    workers: int = 3,
    offset: int = 0,
    global_total: int | None = None,
) -> tuple[int, int, list[tuple[str, str]]]:
    """Generate alternate titles for a batch of rows using parallel Ollama calls.

    Returns (success, fail, failed_rows) where failed_rows can be retried.
    """
    ok = 0
    fail = 0
    total = len(rows)
    display_total = global_total if global_total is not None else total
    failed_rows: list[tuple[str, str]] = []

    def _generate(job: tuple[int, str, str]) -> tuple[int, str, str, str]:
        """Call Ollama for one reel; returns (index, ident, title, alt)."""
        idx, ident, title = job
        return idx, ident, title, call_ollama(title)

    jobs = [(offset + i, ident, title) for i, (ident, title) in enumerate(rows, 1)]

    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
    )
    task = progress.add_task("Generating titles", total=total)

    with progress:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {executor.submit(_generate, job): job for job in jobs}

            try:
                for future in concurrent.futures.as_completed(future_map):
                    i, ident, title = future_map[future]
                    try:
                        _, ident, title, alt = future.result()
                        alt = _strip_reel_ids(alt)  # strip any identifiers the LLM echoed back
                        # Use the identifier-stripped title as baseline for all comparisons so
                        # that annotation tokens (e.g. "FR", "0046", "DISCOVERY") don't skew
                        # word-count or overlap checks.
                        clean_orig = _strip_reel_ids(title)
                        # Validation 1: reject if notably longer than original
                        orig_words = len(clean_orig.split())
                        alt_words = len(alt.split())
                        if alt_words > orig_words * 1.3 + 3:
                            progress.console.print(f"  [{i}/{display_total}] {ident}: too wordy ({orig_words}→{alt_words}), trying conservative fallback...")
                            alt = _strip_reel_ids(call_ollama(title, conservative=True))
                            alt_words = len(alt.split())
                            if alt_words > orig_words * 1.3 + 3:
                                progress.console.print(f"  [{i}/{display_total}] {ident}: FAILED (still too wordy after fallback)")
                                progress.console.print(f"    orig: {title}")
                                progress.console.print(f"    alt:  {alt}")
                                fail += 1
                                failed_rows.append((ident, title))
                                progress.advance(task)
                                continue

                        # Validation 2: reject hallucinations — must share significant words.
                        # Short titles (≤3 sig words) need a stricter threshold because a single
                        # substituted word causes a large percentage drop.
                        # Titles with ≤2 sig words are skipped for overlap — a synonym swap will
                        # always land at 0% and there's no better option for single-concept titles.
                        orig_sig = _significant_words(clean_orig)
                        alt_sig = _significant_words(alt)
                        alt_sig_count = len(alt_sig)
                        overlap_threshold = 0.50 if len(orig_sig) <= 3 else 0.25
                        skip_overlap = len(orig_sig) <= 2
                        if orig_sig and alt_sig and not skip_overlap:
                            overlap = len(orig_sig & alt_sig) / len(orig_sig)
                            word_count_ok = alt_sig_count <= len(orig_sig) + 1
                            if overlap < overlap_threshold or not word_count_ok:
                                reason = f"{overlap:.0%} word overlap" if overlap < overlap_threshold else "added significant words"
                                progress.console.print(f"  [{i}/{display_total}] {ident}: {reason}, trying conservative fallback...")
                                alt = _strip_reel_ids(call_ollama(title, conservative=True))
                                alt_sig = _significant_words(alt)
                                alt_sig_count = len(alt_sig)
                                overlap = len(orig_sig & alt_sig) / len(orig_sig) if orig_sig else 1.0
                                word_count_ok = alt_sig_count <= len(orig_sig) + 1
                                if overlap < overlap_threshold or not word_count_ok:
                                    progress.console.print(f"  [{i}/{display_total}] {ident}: FAILED (still {overlap:.0%} overlap after fallback)")
                                    progress.console.print(f"    orig: {title}")
                                    progress.console.print(f"    alt:  {alt}")
                                    fail += 1
                                    failed_rows.append((ident, title))
                                    progress.advance(task)
                                    continue

                        if not dry_run:
                            db.execute(
                                "UPDATE film_rolls SET alternate_title = ? WHERE identifier = ?",
                                (alt, ident),
                            )
                            db.commit()

                        status = "DRY-RUN" if dry_run else "OK"
                        progress.console.print(f"  [{i}/{display_total}] {ident}: {status}")
                        progress.console.print(f"    orig: {title}")
                        progress.console.print(f"    alt:  {alt}")
                        ok += 1
                    except urllib.error.URLError as exc:
                        progress.console.print(f"  [{i}/{display_total}] {ident}: ERROR - {exc}")
                        fail += 1
                        failed_rows.append((ident, title))
                    except Exception as exc:
                        progress.console.print(f"  [{i}/{display_total}] {ident}: ERROR - {exc}")
                        fail += 1
                        failed_rows.append((ident, title))
                    finally:
                        progress.advance(task)
            except KeyboardInterrupt:
                progress.console.print("\n[interrupted] Cancelling pending jobs...")
                for f in future_map:
                    f.cancel()
                raise

    return ok, fail, failed_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate alternate reel titles via Ollama")
    parser.add_argument("--sample", type=int, default=50, help="Number of random titles to process (default: 50)")
    parser.add_argument("--all", action="store_true", help="Process ALL reels missing an alternate title")
    parser.add_argument("--force", action="store_true", help="Force-regenerate titles for ALL reels (including existing titles)")
    parser.add_argument("--ids", nargs="+", help="Process specific reel identifiers")
    parser.add_argument("--skip", type=int, default=0, metavar="N", help="Skip the first N records (use with --force/--all to resume; e.g. --skip 10381 resumes at record 10382)")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing to DB")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    db = sqlite3.connect(DB_PATH)
    ensure_column(db)

    if args.ids:
        rows = fetch_by_ids(db, args.ids)
        print(f"Processing {len(rows)} specified reels...")
    elif args.force:
        rows = fetch_all_reels(db)
        print(f"Processing all {len(rows)} reels (force mode)...")
    elif args.all:
        rows = fetch_all_missing(db)
        print(f"Processing all {len(rows)} reels missing alternate titles...")
    else:
        rows = fetch_sample(db, args.sample)
        print(f"Processing {len(rows)} random reels...")

    if args.skip and not args.ids:
        total_before = len(rows)
        rows = rows[args.skip:]
        print(f"Skipping first {args.skip} records — resuming at record {args.skip + 1} ({len(rows)} remaining of {total_before})")

    if not rows:
        print("No reels to process.")
        db.close()
        return

    t0 = time.time()
    try:
        ok, fail, failed_rows = process_batch(db, rows, dry_run=args.dry_run, offset=args.skip, global_total=total_before if args.skip else None)
    except KeyboardInterrupt:
        elapsed = time.time() - t0
        print(f"\nInterrupted after {elapsed:.1f}s. Progress saved to DB.")
        db.close()
        sys.exit(1)

    # Automatic single retry pass for anything that failed
    if failed_rows:
        print(f"\nRetrying {len(failed_rows)} failed record(s)...")
        try:
            r_ok, r_fail, _ = process_batch(db, failed_rows, dry_run=args.dry_run)
        except KeyboardInterrupt:
            elapsed = time.time() - t0
            print(f"\nInterrupted after {elapsed:.1f}s. Progress saved to DB.")
            db.close()
            sys.exit(1)
        ok += r_ok
        fail = r_fail  # only count still-failing after retry
        if r_ok:
            print(f"  Retry recovered {r_ok}/{len(failed_rows)} previously failed records")
    elapsed = time.time() - t0

    print(f"\nDone: {ok} succeeded, {fail} failed in {elapsed:.1f}s")
    if ok and not args.dry_run:
        total_alt = db.execute(
            "SELECT COUNT(*) FROM film_rolls WHERE alternate_title IS NOT NULL AND alternate_title != ''"
        ).fetchone()[0]
        total = db.execute("SELECT COUNT(*) FROM film_rolls WHERE title IS NOT NULL").fetchone()[0]
        print(f"Database: {total_alt}/{total} reels now have alternate titles")

    db.close()


if __name__ == "__main__":
    main()
