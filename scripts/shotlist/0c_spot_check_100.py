"""
Spot-check 100 randomly-sampled PDFs through marker-pdf to assess OCR quality
at scale before committing to a full 10,590-PDF batch run.

Stratified sampling ensures coverage across file sizes (which correlate with
document type — small = simple typed, large = multi-page or handwritten).

Outputs:
  - data/spot_check_100/  — raw markdown per PDF
  - docs/spot-check-100-report.md — quality assessment report

Usage:
    uv run python scripts/0c_spot_check_100.py
    uv run python scripts/0c_spot_check_100.py --count 50   # fewer samples
    uv run python scripts/0c_spot_check_100.py --resume      # skip already-processed
"""

import json
import os
import random
import re
import statistics
import sys
import time
from pathlib import Path

INPUT_DIR = "static_assets/shotlist_pdfs"
OUTPUT_DIR = "data/spot_check_100"
REPORT_PATH = "docs/spot-check-100-report.md"

# Seed for reproducibility
RANDOM_SEED = 42


def select_stratified_sample(all_pdfs: list[tuple[str, int]], count: int) -> list[tuple[str, int]]:
    """Select a stratified random sample across file size buckets.

    Ensures we cover the full range of document types/sizes rather than
    over-sampling the median.
    """
    # Define size buckets (in bytes)
    buckets = {
        "tiny_<10KB": (0, 10 * 1024),
        "small_10-30KB": (10 * 1024, 30 * 1024),
        "medium_30-50KB": (30 * 1024, 50 * 1024),
        "large_50-100KB": (50 * 1024, 100 * 1024),
        "xlarge_100-500KB": (100 * 1024, 500 * 1024),
        "huge_>500KB": (500 * 1024, float("inf")),
    }

    bucketed = {name: [] for name in buckets}
    for fname, size in all_pdfs:
        for name, (lo, hi) in buckets.items():
            if lo <= size < hi:
                bucketed[name].append((fname, size))
                break

    rng = random.Random(RANDOM_SEED)
    selected = []

    # Allocate proportional to bucket size, but ensure at least 1 from non-empty buckets
    total = sum(len(v) for v in bucketed.values())
    for name, items in bucketed.items():
        if not items:
            continue
        # Proportional allocation with minimum of 1
        n = max(1, round(count * len(items) / total))
        n = min(n, len(items))  # don't exceed bucket size
        selected.extend(rng.sample(items, n))

    # If we have too many, trim; if too few, add more from largest buckets
    if len(selected) > count:
        rng.shuffle(selected)
        selected = selected[:count]
    elif len(selected) < count:
        remaining = [(f, s) for f, s in all_pdfs if (f, s) not in selected]
        rng.shuffle(remaining)
        selected.extend(remaining[: count - len(selected)])

    return sorted(selected, key=lambda x: x[0])


def analyze_output(text: str) -> dict:
    """Analyze marker-pdf output quality without ground truth.

    Returns heuristic quality metrics that can be computed automatically.
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
    angle_pattern = re.compile(r"\b(LS|MS|MCU|MLS|CU|ECU|WS|MWS|ELS|CS|OTS|POV|ZOOM|PAN|TILT)\b")
    angles_found = angle_pattern.findall(text)

    # Detect common OCR noise patterns
    noise_chars = len(re.findall(r"[•·◦▪▸►▶‣⁃※†‡§¶]", text))
    garbled_sequences = len(re.findall(r"[^\s]{20,}", text))  # very long non-space runs

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
    }


def generate_report(results: list[dict], total_time: float) -> str:
    """Generate a markdown report from all spot check results."""
    # Aggregate stats
    qualities = [r["analysis"]["quality"] for r in results]
    doc_types = [r["analysis"]["doc_type"] for r in results]
    times = [r["elapsed_s"] for r in results]

    quality_counts = {}
    for q in qualities:
        quality_counts[q] = quality_counts.get(q, 0) + 1

    type_counts = {}
    for t in doc_types:
        type_counts[t] = type_counts.get(t, 0) + 1

    # Size bucket stats
    size_quality = {}
    for r in results:
        kb = r["file_size_bytes"] / 1024
        if kb < 10:
            bucket = "<10 KB"
        elif kb < 30:
            bucket = "10–30 KB"
        elif kb < 50:
            bucket = "30–50 KB"
        elif kb < 100:
            bucket = "50–100 KB"
        elif kb < 500:
            bucket = "100–500 KB"
        else:
            bucket = ">500 KB"

        if bucket not in size_quality:
            size_quality[bucket] = {"good": 0, "fair": 0, "poor": 0, "uncertain": 0, "empty": 0, "total": 0}
        size_quality[bucket][r["analysis"]["quality"]] += 1
        size_quality[bucket]["total"] += 1

    n = len(results)
    good_fair = quality_counts.get("good", 0) + quality_counts.get("fair", 0)

    report = []
    report.append("# Spot Check: 100 Random PDFs through marker-pdf")
    report.append("")
    report.append(f"**Date**: {time.strftime('%Y-%m-%d %H:%M')}")
    report.append(f"**Tool**: marker-pdf with `force_ocr` mode")
    report.append(f"**Sample**: {n} PDFs randomly stratified from 10,590 total")
    report.append(f"**Total processing time**: {total_time:.0f}s ({total_time/60:.1f} min)")
    report.append(f"**Average per PDF**: {statistics.mean(times):.1f}s (median {statistics.median(times):.1f}s)")
    report.append("")

    report.append("## Summary")
    report.append("")
    report.append(f"**{good_fair}/{n} ({100*good_fair/n:.0f}%)** PDFs produced good or fair OCR output.")
    report.append("")

    report.append("### Quality Distribution")
    report.append("")
    report.append("| Quality | Count | % | Description |")
    report.append("|---------|------:|--:|-------------|")
    quality_descriptions = {
        "good": "Typed shot list with sequential footage numbers and structural metadata detected",
        "fair": "Tabular content detected with readable text, some structural elements",
        "uncertain": "Text extracted but structure unclear — may need manual review",
        "poor": "Very little readable text or mostly noise",
        "empty": "Nearly empty output (<50 chars)",
    }
    for q in ["good", "fair", "uncertain", "poor", "empty"]:
        c = quality_counts.get(q, 0)
        report.append(f"| **{q}** | {c} | {100*c/n:.0f}% | {quality_descriptions.get(q, '')} |")

    report.append("")
    report.append("### Document Type Distribution")
    report.append("")
    report.append("| Type | Count | % |")
    report.append("|------|------:|--:|")
    for t in ["typed_shot_list", "scene_log_form", "tabular_unknown", "handwritten_or_minimal", "unknown"]:
        c = type_counts.get(t, 0)
        if c > 0:
            report.append(f"| {t} | {c} | {100*c/n:.0f}% |")

    report.append("")
    report.append("### Quality by File Size")
    report.append("")
    report.append("| Size Bucket | Total | Good | Fair | Uncertain | Poor | Empty |")
    report.append("|-------------|------:|-----:|-----:|----------:|-----:|------:|")
    for bucket in ["<10 KB", "10–30 KB", "30–50 KB", "50–100 KB", "100–500 KB", ">500 KB"]:
        if bucket in size_quality:
            s = size_quality[bucket]
            report.append(
                f"| {bucket} | {s['total']} | {s['good']} | {s['fair']} | "
                f"{s['uncertain']} | {s['poor']} | {s['empty']} |"
            )

    report.append("")
    report.append("### Processing Time Distribution")
    report.append("")
    report.append(f"- **Min**: {min(times):.1f}s")
    report.append(f"- **Max**: {max(times):.1f}s")
    report.append(f"- **Mean**: {statistics.mean(times):.1f}s")
    report.append(f"- **Median**: {statistics.median(times):.1f}s")
    report.append(f"- **Std Dev**: {statistics.stdev(times):.1f}s")
    if n >= 5:
        sorted_times = sorted(times)
        p95 = sorted_times[int(n * 0.95)]
        report.append(f"- **P95**: {p95:.1f}s")

    # Projected full-batch time
    avg = statistics.mean(times)
    total_est_hrs = avg * 10590 / 3600
    report.append("")
    report.append(f"### Projected Full Batch (10,590 PDFs)")
    report.append("")
    report.append(f"- At {avg:.1f}s average: **{total_est_hrs:.1f} hours**")
    report.append(f"- At {statistics.median(times):.1f}s median: **{statistics.median(times) * 10590 / 3600:.1f} hours**")
    report.append(f"- At P95 ({p95:.1f}s) worst-case bound: **{p95 * 10590 / 3600:.1f} hours**")

    report.append("")
    report.append("## Detailed Results")
    report.append("")
    report.append("| # | PDF | Size | Time | Quality | Type | Footage# | Angles | Struct | Chars |")
    report.append("|--:|-----|-----:|-----:|---------|------|----------|--------|--------|------:|")

    for i, r in enumerate(sorted(results, key=lambda x: x["filename"]), 1):
        a = r["analysis"]
        size_kb = r["file_size_bytes"] / 1024
        report.append(
            f"| {i} | {r['filename']} | {size_kb:.0f} KB | {r['elapsed_s']:.1f}s | "
            f"**{a['quality']}** | {a['doc_type']} | {a['footage_numbers_found']} | "
            f"{a['angles_found']} | {a['structural_score']}/6 | {a['total_chars']} |"
        )

    # Problem cases section
    problems = [r for r in results if r["analysis"]["quality"] in ("poor", "empty", "uncertain")]
    if problems:
        report.append("")
        report.append("## Notable Problem Cases")
        report.append("")
        for r in sorted(problems, key=lambda x: x["analysis"]["quality"]):
            a = r["analysis"]
            report.append(f"### {r['filename']} — {a['quality']}")
            report.append(f"- Size: {r['file_size_bytes']/1024:.0f} KB, Time: {r['elapsed_s']:.1f}s")
            report.append(f"- Type: {a['doc_type']}, Chars: {a['total_chars']}, Alpha ratio: {a['alpha_ratio']}")
            # Show first 300 chars of output
            preview = r.get("text_preview", "")
            if preview:
                report.append(f"- Preview:")
                report.append(f"  ```")
                for line in preview.split("\n")[:10]:
                    report.append(f"  {line}")
                report.append(f"  ```")
            report.append("")

    report.append("")
    report.append("## Conclusions")
    report.append("")
    report.append(f"Based on this {n}-PDF sample:")
    report.append("")
    if good_fair / n >= 0.8:
        report.append(f"- **{100*good_fair/n:.0f}% of PDFs produce usable OCR output** — marker-pdf is viable for Stage 1 batch processing.")
    elif good_fair / n >= 0.6:
        report.append(f"- **{100*good_fair/n:.0f}% of PDFs produce usable output** — majority is viable, but a significant portion may need alternative processing.")
    else:
        report.append(f"- **Only {100*good_fair/n:.0f}% produce usable output** — marker-pdf may not be sufficient as the primary OCR approach.")

    poor_empty = quality_counts.get("poor", 0) + quality_counts.get("empty", 0)
    if poor_empty > 0:
        report.append(f"- **{poor_empty} PDFs ({100*poor_empty/n:.0f}%)** produced poor/empty output — these will likely need a cloud VLM or manual handling.")

    report.append(f"- Estimated full batch time: **{total_est_hrs:.0f} hours** of GPU time.")
    report.append(f"- The Stage 2 parser will need to handle noisy table formatting, merged rows, and OCR number errors.")
    report.append("")

    return "\n".join(report)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Spot-check 100 random PDFs")
    parser.add_argument("--count", "-n", type=int, default=100, help="Number of PDFs to sample (default: 100)")
    parser.add_argument("--resume", action="store_true", help="Skip already-processed PDFs")
    args = parser.parse_args()

    # Collect all PDFs
    all_pdfs = []
    for fname in os.listdir(INPUT_DIR):
        if fname.endswith(".pdf"):
            fpath = os.path.join(INPUT_DIR, fname)
            all_pdfs.append((fname, os.path.getsize(fpath)))

    print(f"Found {len(all_pdfs)} PDFs total")

    # Select stratified sample
    sample = select_stratified_sample(all_pdfs, args.count)
    print(f"Selected {len(sample)} PDFs (stratified by size)")

    # Show sample distribution
    size_dist = {}
    for _, size in sample:
        kb = size / 1024
        if kb < 10: b = "<10KB"
        elif kb < 30: b = "10-30KB"
        elif kb < 50: b = "30-50KB"
        elif kb < 100: b = "50-100KB"
        elif kb < 500: b = "100-500KB"
        else: b = ">500KB"
        size_dist[b] = size_dist.get(b, 0) + 1
    print(f"  Size distribution: {size_dist}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load marker models once
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered
    from marker.config.parser import ConfigParser

    config = {"output_format": "markdown", "force_ocr": True}
    config_parser = ConfigParser(config)

    print("\nLoading marker models...")
    t0 = time.time()
    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
    )
    print(f"Models loaded in {time.time() - t0:.1f}s\n")

    results = []
    total_start = time.time()

    for i, (fname, fsize) in enumerate(sample, 1):
        pdf_path = os.path.join(INPUT_DIR, fname)
        base = os.path.splitext(fname)[0]
        md_path = os.path.join(OUTPUT_DIR, f"{base}.md")

        # Resume support
        if args.resume and os.path.exists(md_path):
            print(f"[{i:3d}/{len(sample)}] SKIP (cached): {fname}")
            with open(md_path, "r", encoding="utf-8") as f:
                text = f.read()
            elapsed = 0.0
        else:
            print(f"[{i:3d}/{len(sample)}] Processing {fname} ({fsize/1024:.0f} KB)...", end=" ", flush=True)
            t1 = time.time()
            try:
                rendered = converter(pdf_path)
                text, _, _ = text_from_rendered(rendered)
                elapsed = time.time() - t1
                print(f"{elapsed:.1f}s, {len(text)} chars")

                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(text)
            except Exception as e:
                elapsed = time.time() - t1
                print(f"ERROR: {e}")
                text = ""

        # Analyze output
        analysis = analyze_output(text)

        results.append({
            "filename": fname,
            "file_size_bytes": fsize,
            "elapsed_s": round(elapsed, 1),
            "analysis": analysis,
            "text_preview": text[:500] if analysis["quality"] in ("poor", "empty", "uncertain") else "",
        })

    total_time = time.time() - total_start

    # Save raw results as JSON
    results_path = os.path.join(OUTPUT_DIR, "_results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nRaw results saved to {results_path}")

    # Generate and save report
    report = generate_report(results, total_time)
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved to {REPORT_PATH}")

    # Print quick summary
    qualities = [r["analysis"]["quality"] for r in results]
    print(f"\n{'='*60}")
    print("QUICK SUMMARY")
    print(f"{'='*60}")
    for q in ["good", "fair", "uncertain", "poor", "empty"]:
        c = qualities.count(q)
        if c > 0:
            print(f"  {q:>10}: {c:3d} ({100*c/len(results):.0f}%)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
