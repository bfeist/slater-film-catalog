"""
Stage 1: Batch-process all 10,590 FR shot list PDFs through marker-pdf.

Outputs one JSON + one markdown file per PDF in data/01_shotlist_raw/.
Each JSON contains the raw OCR text, quality analysis metrics, and a
quality gate flag indicating whether VLM fallback is recommended.

Features:
  - Skips PDFs that already have output files (unless --force)
  - Migrates existing spot_check_100 results on first run
  - Tracks progress in _manifest.json (resumable)
  - Prints ETA and progress every 10 PDFs
  - Quality gate flags poor/uncertain results for VLM fallback (Stage 1c)

Usage:
    uv run python scripts/1_ingest_shotlist_pdfs.py              # full batch
    uv run python scripts/1_ingest_shotlist_pdfs.py --limit 50   # test with 50
    uv run python scripts/1_ingest_shotlist_pdfs.py --force       # re-process all
    uv run python scripts/1_ingest_shotlist_pdfs.py --no-migrate  # skip migration
"""

import argparse
import json
import os
import re
import shutil
import statistics
import sys
import time
from pathlib import Path

INPUT_DIR = "static_assets/shotlist_pdfs"
OUTPUT_DIR = "data/01_shotlist_raw"
MANIFEST_PATH = os.path.join(OUTPUT_DIR, "_manifest.json")

# Existing spot check results to migrate
SPOT_CHECK_100_DIR = "data/spot_check_100"
SPOT_CHECK_100_RESULTS = os.path.join(SPOT_CHECK_100_DIR, "_results.json")


# ---------------------------------------------------------------------------
# Quality analysis (adapted from scripts/0c_spot_check_100.py)
# ---------------------------------------------------------------------------

def analyze_output(text: str) -> dict:
    """Analyze marker-pdf output quality using text heuristics.

    Returns quality metrics and a quality tier (good/fair/uncertain/poor/empty).
    No ground truth needed — works purely on the OCR output text.
    """
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    total_chars = len(text)

    # Count table rows (lines starting with |)
    table_rows = [l for l in lines if l.startswith("|")]
    non_empty_table_rows = [l for l in table_rows if re.search(r"[A-Za-z]{2,}", l)]

    # Look for footage numbers (1-4 digit numbers at start of table cells)
    footage_numbers = []
    for line in table_rows:
        m = re.match(r"^\|\s*(\d{1,4})\s*\|", line)
        if m:
            footage_numbers.append(int(m.group(1)))

    # Look for camera angles
    angle_pattern = re.compile(
        r"\b(LS|MS|MCU|MLS|CU|ECU|WS|MWS|ELS|CS|OTS|POV|ZOOM|PAN|TILT)\b"
    )
    angles_found = angle_pattern.findall(text)

    # Detect common OCR noise patterns
    noise_chars = len(re.findall(r"[•·◦▪▸►▶‣⁃※†‡§¶]", text))
    garbled_sequences = len(re.findall(r"[^\s]{20,}", text))

    # Look for key structural elements
    has_category = bool(re.search(r"CATEGORY|Category", text, re.IGNORECASE))
    has_source = bool(re.search(r"SOURCE|Source", text, re.IGNORECASE))
    has_subject = bool(re.search(r"SUBJECT|Subject", text, re.IGNORECASE))
    has_footage_header = bool(re.search(r"FOOTAGE|Footage", text, re.IGNORECASE))
    has_end_roll = bool(re.search(r"END\s*(OF)?\s*ROLL", text, re.IGNORECASE))
    has_classification = bool(re.search(r"CLASSIF|UN\b|CONF", text, re.IGNORECASE))
    has_slate = bool(re.search(r"SLATE", text, re.IGNORECASE))

    # Detect document type heuristically
    if re.search(r"SCENE\s*LOG|Documentary\s*Motion\s*Picture", text, re.IGNORECASE):
        doc_type = "scene_log_form"
    elif re.search(r"handwrit|script", text, re.IGNORECASE) or total_chars < 100:
        doc_type = "handwritten_or_minimal"
    elif len(footage_numbers) >= 3 and has_footage_header:
        doc_type = "typed_shot_list"
    elif len(table_rows) >= 3:
        doc_type = "tabular_unknown"
    else:
        doc_type = "unknown"

    # Meaningful text ratio: alpha chars vs total
    alpha_chars = len(re.findall(r"[A-Za-z]", text))
    alpha_ratio = alpha_chars / max(total_chars, 1)

    # Sequential footage check (are footage numbers roughly ascending?)
    is_sequential = False
    if len(footage_numbers) >= 3:
        ascending_pairs = sum(
            1 for a, b in zip(footage_numbers, footage_numbers[1:]) if b > a
        )
        is_sequential = ascending_pairs / (len(footage_numbers) - 1) > 0.7

    # Quality tier assignment
    structural_score = sum([
        has_category, has_source, has_subject, has_footage_header,
        has_end_roll, has_classification,
    ])

    if total_chars < 50:
        quality = "empty"
    elif doc_type == "typed_shot_list" and is_sequential and structural_score >= 3:
        quality = "good"
    elif doc_type == "typed_shot_list" and len(footage_numbers) >= 3:
        quality = "fair"
    elif len(non_empty_table_rows) >= 3 and alpha_ratio > 0.15:
        quality = "fair"
    elif alpha_ratio < 0.05 or total_chars < 200:
        quality = "poor"
    else:
        quality = "uncertain"

    # Quality gate: should this PDF be re-processed by VLM fallback?
    needs_vlm_fallback = (
        quality in ("poor", "empty")
        or (alpha_ratio < 0.10)
        or (len(footage_numbers) == 0 and total_chars > 500)
    )

    return {
        "total_chars": total_chars,
        "total_lines": len(lines),
        "table_rows": len(table_rows),
        "non_empty_table_rows": len(non_empty_table_rows),
        "footage_numbers_found": len(footage_numbers),
        "footage_numbers": footage_numbers,
        "is_sequential": is_sequential,
        "angles_found": len(angles_found),
        "unique_angles": sorted(set(angles_found)),
        "noise_chars": noise_chars,
        "garbled_sequences": garbled_sequences,
        "alpha_ratio": round(alpha_ratio, 3),
        "structural_elements": {
            "category": has_category,
            "source": has_source,
            "subject": has_subject,
            "footage_header": has_footage_header,
            "end_of_roll": has_end_roll,
            "classification": has_classification,
            "slate": has_slate,
        },
        "structural_score": structural_score,
        "doc_type": doc_type,
        "quality": quality,
        "needs_vlm_fallback": needs_vlm_fallback,
    }


# ---------------------------------------------------------------------------
# Manifest management
# ---------------------------------------------------------------------------

def load_manifest() -> dict:
    """Load or create the processing manifest."""
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r") as f:
            return json.load(f)
    return {
        "version": 1,
        "total_pdfs": 0,
        "processed": 0,
        "skipped": 0,
        "errors": 0,
        "migrated_from_spot_check": 0,
        "quality_counts": {},
        "vlm_fallback_count": 0,
        "last_updated": None,
        "timing": {
            "total_processing_s": 0,
            "times": [],
        },
    }


def save_manifest(manifest: dict):
    """Save manifest atomically (write to temp then rename)."""
    manifest["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    tmp = MANIFEST_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(manifest, f, indent=2)
    os.replace(tmp, MANIFEST_PATH)


# ---------------------------------------------------------------------------
# Migration: import existing spot_check_100 results
# ---------------------------------------------------------------------------

def migrate_spot_check_results(manifest: dict) -> int:
    """Copy spot_check_100 markdown files into 01_shotlist_raw and create JSONs.

    Returns number of files migrated. Reads the _results.json from the spot
    check to carry over the quality analysis rather than re-running OCR.
    """
    if not os.path.exists(SPOT_CHECK_100_RESULTS):
        print("  No spot_check_100 results found — skipping migration.")
        return 0

    with open(SPOT_CHECK_100_RESULTS, "r") as f:
        spot_results = json.load(f)

    migrated = 0
    for entry in spot_results:
        pdf_name = entry["filename"]
        base = os.path.splitext(pdf_name)[0]
        src_md = os.path.join(SPOT_CHECK_100_DIR, f"{base}.md")
        dst_md = os.path.join(OUTPUT_DIR, f"{base}.md")
        dst_json = os.path.join(OUTPUT_DIR, f"{base}.json")

        if not os.path.exists(src_md):
            continue

        # Read the markdown text
        with open(src_md, "r", encoding="utf-8") as f:
            text = f.read()

        # Copy markdown
        shutil.copy2(src_md, dst_md)

        # Re-analyze with our updated function (adds needs_vlm_fallback)
        analysis = analyze_output(text)

        # Build JSON output
        result = {
            "filename": pdf_name,
            "source": "marker-pdf",
            "marker_version": "1.10.x",
            "force_ocr": True,
            "file_size_bytes": entry.get("file_size_bytes", os.path.getsize(
                os.path.join(INPUT_DIR, pdf_name)
            ) if os.path.exists(os.path.join(INPUT_DIR, pdf_name)) else 0),
            "elapsed_s": entry.get("elapsed_s", 0),
            "migrated_from": "spot_check_100",
            "analysis": analysis,
            "text": text,
        }

        with open(dst_json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        # Update manifest quality counts
        q = analysis["quality"]
        manifest["quality_counts"][q] = manifest["quality_counts"].get(q, 0) + 1
        if analysis["needs_vlm_fallback"]:
            manifest["vlm_fallback_count"] += 1

        migrated += 1

    manifest["migrated_from_spot_check"] = migrated
    manifest["processed"] += migrated
    return migrated


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_pdf(converter, pdf_path: str, pdf_name: str) -> dict:
    """Process a single PDF through marker-pdf and return result dict."""
    from marker.output import text_from_rendered

    file_size = os.path.getsize(pdf_path)

    t0 = time.time()
    try:
        rendered = converter(pdf_path)
        text, metadata, images = text_from_rendered(rendered)
        elapsed = time.time() - t0
        error = None
    except Exception as e:
        elapsed = time.time() - t0
        text = ""
        error = str(e)

    analysis = analyze_output(text)

    return {
        "filename": pdf_name,
        "source": "marker-pdf",
        "force_ocr": True,
        "file_size_bytes": file_size,
        "elapsed_s": round(elapsed, 1),
        "error": error,
        "analysis": analysis,
        "text": text,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Stage 1: Batch OCR all shotlist PDFs through marker-pdf"
    )
    parser.add_argument(
        "--limit", "-n", type=int, default=0,
        help="Process only N PDFs (0 = all, default: 0)"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-process PDFs even if output already exists"
    )
    parser.add_argument(
        "--no-migrate", action="store_true",
        help="Skip migration of spot_check_100 results"
    )
    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # 1. Discover all PDFs
    # -----------------------------------------------------------------------
    all_pdfs = sorted([
        f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf")
    ])
    print(f"Found {len(all_pdfs)} PDFs in {INPUT_DIR}")

    if args.limit > 0:
        all_pdfs = all_pdfs[:args.limit]
        print(f"  --limit {args.limit}: will process at most {len(all_pdfs)}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    manifest = load_manifest()
    manifest["total_pdfs"] = len(all_pdfs)

    # -----------------------------------------------------------------------
    # 2. Migrate existing spot_check_100 results (unless --no-migrate)
    # -----------------------------------------------------------------------
    if not args.no_migrate and manifest.get("migrated_from_spot_check", 0) == 0:
        print("\nMigrating spot_check_100 results...")
        n_migrated = migrate_spot_check_results(manifest)
        if n_migrated > 0:
            save_manifest(manifest)
            print(f"  Migrated {n_migrated} files from spot_check_100")
        else:
            print("  Nothing to migrate")

    # -----------------------------------------------------------------------
    # 3. Determine which PDFs need processing
    # -----------------------------------------------------------------------
    to_process = []
    skipped = 0
    for pdf_name in all_pdfs:
        base = os.path.splitext(pdf_name)[0]
        json_path = os.path.join(OUTPUT_DIR, f"{base}.json")
        if not args.force and os.path.exists(json_path):
            skipped += 1
            continue
        to_process.append(pdf_name)

    print(f"\nTo process: {len(to_process)}  |  Skipped (existing): {skipped}")
    manifest["skipped"] = skipped

    if not to_process:
        print("Nothing to do — all PDFs already processed.")
        save_manifest(manifest)
        return

    # -----------------------------------------------------------------------
    # 4. Load marker-pdf models (once)
    # -----------------------------------------------------------------------
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.config.parser import ConfigParser

    config = {"output_format": "markdown", "force_ocr": True}
    config_parser = ConfigParser(config)

    print("\nLoading marker-pdf models...")
    t_load = time.time()
    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
    )
    load_time = time.time() - t_load
    print(f"Models loaded in {load_time:.1f}s\n")

    # -----------------------------------------------------------------------
    # 5. Process PDFs
    # -----------------------------------------------------------------------
    recent_times = []  # rolling window for ETA
    batch_start = time.time()
    errors = 0

    for i, pdf_name in enumerate(to_process, 1):
        pdf_path = os.path.join(INPUT_DIR, pdf_name)
        base = os.path.splitext(pdf_name)[0]
        json_path = os.path.join(OUTPUT_DIR, f"{base}.json")
        md_path = os.path.join(OUTPUT_DIR, f"{base}.md")

        # Progress + ETA
        if recent_times:
            avg_time = statistics.mean(recent_times[-100:])
            remaining = (len(to_process) - i + 1) * avg_time
            eta_str = f"  ETA: {remaining/3600:.1f}h" if remaining > 3600 else f"  ETA: {remaining/60:.0f}m"
        else:
            eta_str = ""
            avg_time = 0

        file_kb = os.path.getsize(pdf_path) / 1024
        print(
            f"[{i:5d}/{len(to_process)}] {pdf_name:<40s} ({file_kb:6.0f} KB)",
            end="",
            flush=True,
        )

        # Process
        result = process_pdf(converter, pdf_path, pdf_name)

        if result["error"]:
            errors += 1
            print(f"  ERROR: {result['error']}")
        else:
            q = result["analysis"]["quality"]
            vlm_flag = " [VLM]" if result["analysis"]["needs_vlm_fallback"] else ""
            print(
                f"  {result['elapsed_s']:5.1f}s  {result['analysis']['total_chars']:6d} chars"
                f"  [{q}]{vlm_flag}{eta_str}"
            )

        # Save markdown
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(result["text"])

        # Save JSON (text is included in JSON — md file is for easy browsing)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        # Update tracking
        recent_times.append(result["elapsed_s"])
        q = result["analysis"]["quality"]
        manifest["quality_counts"][q] = manifest["quality_counts"].get(q, 0) + 1
        if result["analysis"]["needs_vlm_fallback"]:
            manifest["vlm_fallback_count"] += 1
        manifest["processed"] += 1
        manifest["errors"] = errors
        manifest["timing"]["total_processing_s"] += result["elapsed_s"]

        # Save manifest every 50 PDFs (cheap insurance against crashes)
        if i % 50 == 0:
            manifest["timing"]["times"] = recent_times[-500:]  # keep last 500
            save_manifest(manifest)

    # -----------------------------------------------------------------------
    # 6. Final summary
    # -----------------------------------------------------------------------
    total_time = time.time() - batch_start
    manifest["timing"]["total_processing_s"] = round(
        manifest["timing"]["total_processing_s"], 1
    )
    manifest["timing"]["times"] = recent_times[-500:]
    save_manifest(manifest)

    print(f"\n{'='*70}")
    print("STAGE 1 COMPLETE")
    print(f"{'='*70}")
    print(f"  Processed:   {len(to_process)}")
    print(f"  Skipped:     {skipped}")
    print(f"  Errors:      {errors}")
    print(f"  Wall time:   {total_time/3600:.1f}h ({total_time:.0f}s)")
    if recent_times:
        print(f"  Avg per PDF: {statistics.mean(recent_times):.1f}s"
              f" (median {statistics.median(recent_times):.1f}s)")
    print()
    print("  Quality distribution:")
    for q in ["good", "fair", "uncertain", "poor", "empty"]:
        c = manifest["quality_counts"].get(q, 0)
        if c > 0:
            pct = 100 * c / max(manifest["processed"], 1)
            print(f"    {q:>10}: {c:5d} ({pct:4.1f}%)")
    print(f"\n  VLM fallback needed: {manifest['vlm_fallback_count']}")
    print(f"  Manifest: {MANIFEST_PATH}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
