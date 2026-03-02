"""
Test chunked LLM cleanup of marker-pdf OCR output.

Problem: marker's built-in use_llm mode sends the full page to the LLM,
which "cleans" the table by DROPPING rows it considers noisy (data loss).

Solution tested here: run marker baseline first, then post-process the
raw markdown by sending SMALL CHUNKS (3-5 table rows) to the LLM for
cleanup. This prevents the LLM from summarizing/compressing.

Tests multiple Ollama models to find the most faithful one.

Usage:
    uv run python scripts/0b_compare_ocr_approaches.py
    uv run python scripts/0b_compare_ocr_approaches.py --skip-baseline
    uv run python scripts/0b_compare_ocr_approaches.py -f FR-0001.pdf -m gemma3:12b -c 5
"""

import json
import os
import re
import time
from pathlib import Path

INPUT_DIR = "static_assets/shotlist_pdfs"
OUTPUT_DIR = "data/ocr_comparison"

SPOT_CHECK_FILES = [
    "FR-0001.pdf",  # typed shot list, simple
    "FR-2041.pdf",  # typed shot list, median
]

# Models to test (must fit in ~18GB VRAM)
MODELS = [
    "gemma3:12b",
    "qwen3:14b",
    "gemma3:27b",
]

CHUNK_SIZE = 5  # rows per chunk

# Ground truth shot entries for validation (from visual inspection of PDFs)
GROUND_TRUTH = {
    "FR-0001.pdf": {
        "header": {
            "category": "Facilities & Support Activities, Spacecraft - Mercury",
            "source": "Unknown",
            "subject": "Swings Test at NAS Hanger S",
            "classification": "UN",
            "material": "ECN",
            "total_footage": 207,
        },
        "shots": [
            {"footage": 10, "desc_fragment": "SLATE"},
            {"footage": 13, "angle": "MS", "desc_fragment": "guiding Mercury Capsule"},
            {"footage": 21, "angle": "MS", "desc_fragment": "Same action"},
            {"footage": 32, "angle": "MS", "desc_fragment": "lowered onto dolly"},
            {"footage": 47, "angle": "MS", "desc_fragment": "Mercury Capsule on dolly"},
            {"footage": 57, "angle": "MS", "desc_fragment": "adjusting hoist sling"},
            {"footage": 70, "angle": "MS", "desc_fragment": ""},
            {"footage": 86, "angle": "LS", "desc_fragment": "rear hoist mount"},
            {"footage": 104, "angle": "MLS", "desc_fragment": "hoist capsule"},
            {"footage": 144, "angle": "MS", "desc_fragment": "nose pointed"},
            {"footage": 158, "angle": "MS", "desc_fragment": "Suspended capsule"},
            {"footage": 166, "angle": "MLS", "desc_fragment": "different angle"},
            {"footage": 173, "angle": "MS", "desc_fragment": "reverse angle"},
            {"footage": 179, "angle": "LS", "desc_fragment": "step ladder"},
            {"footage": 188, "angle": "MCU", "desc_fragment": "R&R"},
            {"footage": 207, "desc_fragment": "END OF ROLL"},
        ],
    },
    "FR-2041.pdf": {
        "header": {
            "source": "Marshall",
            "subject": "Saturn Table Models",
            "classification": "UN",
            "total_footage": 312,
        },
        "shots": [
            {"footage": 20, "angle": "LS", "desc_fragment": "Saturn V"},
            {"footage": 35, "angle": "LS", "desc_fragment": "Take 2"},
            {"footage": 50, "angle": "MLS", "desc_fragment": "S-IC Booster"},
            {"footage": 66, "angle": "MLS", "desc_fragment": "S-II Booster"},
            {"footage": 82, "angle": "MS", "desc_fragment": "S-IV-B"},
            {"footage": 96, "angle": "MS", "desc_fragment": "cursion Module"},
            {"footage": 111, "angle": "LS", "desc_fragment": "Saturn V"},
            {"footage": 132, "angle": "LS", "desc_fragment": "Saturn I"},
            {"footage": 148, "angle": "MLS", "desc_fragment": "S-I Booster"},
            {"footage": 164, "angle": "MS", "desc_fragment": "S-IV Booster"},
            {"footage": 180, "angle": "MLS", "desc_fragment": "Launch Escape"},
            {"footage": 194, "angle": "LS", "desc_fragment": "Saturn I-B"},
            {"footage": 215, "angle": "MLS", "desc_fragment": "S-I-B Booster"},
            {"footage": 235, "angle": "MS", "desc_fragment": "S-IV Booster"},
            {"footage": 251, "angle": "MLS", "desc_fragment": "Launch Escape"},
            {"footage": 269, "angle": "LS", "desc_fragment": "Saturn"},
            {"footage": 289, "desc_fragment": "NG FOOTAGE"},
            {"footage": 290, "angle": "LS", "desc_fragment": "Saturn V"},
            {"footage": 308, "desc_fragment": "footage"},
            {"footage": 312, "desc_fragment": "END OF ROLL"},
        ],
    },
}


CLEANUP_PROMPT = """\
You are cleaning up noisy OCR output from a scanned 1960s NASA film shot list.
The OCR was done by an automated tool and the markdown table has errors:
text split across columns, OCR artifacts (dots, symbols, etc.), and mangled formatting.

CRITICAL RULES:
1. Preserve EVERY row — do NOT remove, merge, or skip any rows
2. Fix OCR errors in the text (e.g. "souace" -> "source", "1,8" -> "LS")
3. Merge text that was incorrectly split across multiple columns back into the correct column
4. Remove obvious OCR noise characters (random dots, symbols, etc.)
5. Output a clean markdown table with these columns: FOOTAGE | ANGLE | DESCRIPTION
6. For header/metadata rows (not shot data), output them as plain text lines above the table
7. If a row has "<br>" joining two entries, split into two separate rows
8. Output ONLY the cleaned text, no commentary or explanation

Here is the chunk to clean:
"""


def run_marker_baseline(pdf_path: str) -> str:
    """Run marker-pdf with force_ocr to get raw markdown."""
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered
    from marker.config.parser import ConfigParser

    config = {"output_format": "markdown", "force_ocr": True}
    config_parser = ConfigParser(config)
    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
    )
    rendered = converter(pdf_path)
    text, _, _ = text_from_rendered(rendered)
    return text


def chunk_markdown_table(md_text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """Split markdown table into chunks of N rows each.

    Returns list of chunk strings. Each chunk includes the separator line
    so the LLM knows it's a table.
    """
    lines = md_text.strip().split("\n")

    # Find table rows (lines starting with |) and separator lines
    table_rows = []
    separator = None
    non_table_preamble = []

    for line in lines:
        stripped = line.strip()
        if re.match(r"^\|[-\s|]+\|$", stripped):
            separator = stripped
        elif stripped.startswith("|"):
            table_rows.append(stripped)
        elif not table_rows:
            non_table_preamble.append(stripped)

    if not table_rows:
        return [md_text]  # no table found, return as-is

    chunks = []

    for i in range(0, len(table_rows), chunk_size):
        batch = table_rows[i : i + chunk_size]
        chunk_lines = []
        if i == 0 and non_table_preamble:
            chunk_lines.extend(non_table_preamble)
        if separator:
            chunk_lines.append(separator)
        chunk_lines.extend(batch)
        chunks.append("\n".join(chunk_lines))

    return chunks


def llm_clean_chunk(chunk: str, model: str) -> str:
    """Send a single chunk to Ollama for cleanup."""
    import ollama

    response = ollama.chat(
        model=model,
        messages=[
            {"role": "user", "content": CLEANUP_PROMPT + chunk},
        ],
        options={"temperature": 0.0, "num_predict": 2048},
    )
    return response["message"]["content"]


def chunked_llm_cleanup(
    raw_md: str, model: str, chunk_size: int = CHUNK_SIZE
) -> dict:
    """Run chunked LLM cleanup on raw marker output."""
    chunks = chunk_markdown_table(raw_md, chunk_size)

    print(f"      Split into {len(chunks)} chunks of ~{chunk_size} rows each")

    cleaned_chunks = []
    t0 = time.time()

    for i, chunk in enumerate(chunks):
        chunk_rows = len(
            [l for l in chunk.split("\n") if l.strip().startswith("|")]
        )
        print(
            f"      Chunk {i+1}/{len(chunks)} ({chunk_rows} rows)...",
            end=" ",
            flush=True,
        )

        ct = time.time()
        cleaned = llm_clean_chunk(chunk, model)
        chunk_elapsed = time.time() - ct
        print(f"{chunk_elapsed:.1f}s")
        cleaned_chunks.append(cleaned)

    elapsed = time.time() - t0

    combined = "\n\n".join(cleaned_chunks)

    return {
        "elapsed_s": round(elapsed, 1),
        "num_chunks": len(chunks),
        "chunk_size": chunk_size,
        "text": combined,
    }


def count_shot_rows(text: str) -> list[dict]:
    """Extract shot rows (footage number + description) from text output."""
    shots = []
    for line in text.split("\n"):
        # Match table rows: | 13 | MS | description... |
        # Also match plain text: 13  MS  description...
        m = re.match(
            r"^\|?\s*(\d{1,4})\s*\|?\s*([A-Z]{1,4})?\s*\|?\s*(.*?)(?:\|.*)?$",
            line.strip(),
        )
        if m:
            footage = int(m.group(1))
            angle = (m.group(2) or "").strip()
            desc = (m.group(3) or "").strip().rstrip("|").strip()
            if footage > 0:
                shots.append({"footage": footage, "angle": angle, "desc": desc})
    return shots


def evaluate_against_truth(shots: list[dict], pdf_name: str) -> dict:
    """Compare extracted shots against ground truth."""
    if pdf_name not in GROUND_TRUTH:
        return {"error": "no ground truth"}

    truth = GROUND_TRUTH[pdf_name]["shots"]
    truth_footages = {s["footage"] for s in truth}
    found_footages = {s["footage"] for s in shots}

    hits = truth_footages & found_footages
    missed = truth_footages - found_footages
    extra = found_footages - truth_footages

    return {
        "truth_count": len(truth),
        "found_count": len(shots),
        "hits": len(hits),
        "missed": sorted(missed),
        "extra": sorted(extra),
        "recall_pct": round(100.0 * len(hits) / len(truth), 1) if truth else 0,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test chunked LLM OCR cleanup")
    parser.add_argument(
        "--files",
        "-f",
        default=None,
        help="Comma-separated PDF filenames (default: FR-0001.pdf,FR-2041.pdf)",
    )
    parser.add_argument(
        "--models",
        "-m",
        default=None,
        help=f"Comma-separated model names (default: {','.join(MODELS)})",
    )
    parser.add_argument(
        "--chunk-sizes",
        "-c",
        default="3,5,10",
        help="Comma-separated chunk sizes to test (default: 3,5,10)",
    )
    parser.add_argument(
        "--skip-baseline",
        action="store_true",
        help="Skip marker baseline if raw output already exists",
    )
    args = parser.parse_args()

    files = (
        [x.strip() for x in args.files.split(",")]
        if args.files
        else SPOT_CHECK_FILES
    )
    models = (
        [x.strip() for x in args.models.split(",")]
        if args.models
        else MODELS
    )
    chunk_sizes = [int(x) for x in args.chunk_sizes.split(",")]

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_results = []

    for pdf_name in files:
        pdf_path = os.path.join(INPUT_DIR, pdf_name)
        if not os.path.exists(pdf_path):
            print(f"SKIP: {pdf_path} not found")
            continue

        base = os.path.splitext(pdf_name)[0]
        print(f"\n{'='*70}")
        print(f"  PDF: {pdf_name} ({os.path.getsize(pdf_path)/1024:.1f} KB)")
        print(f"{'='*70}")

        # Step 1: Get marker baseline
        raw_path = os.path.join(OUTPUT_DIR, f"{base}_raw.md")
        if args.skip_baseline and os.path.exists(raw_path):
            print(f"\n  [baseline] Loading cached: {raw_path}")
            with open(raw_path, "r", encoding="utf-8") as f:
                raw_md = f.read()
        else:
            print(f"\n  [baseline] Running marker-pdf force_ocr...")
            t0 = time.time()
            raw_md = run_marker_baseline(pdf_path)
            baseline_time = time.time() - t0
            print(f"      Time: {baseline_time:.1f}s, {len(raw_md)} chars")
            with open(raw_path, "w", encoding="utf-8") as f:
                f.write(raw_md)

        # Evaluate baseline
        baseline_shots = count_shot_rows(raw_md)
        baseline_eval = evaluate_against_truth(baseline_shots, pdf_name)
        print(f"      Baseline shots found: {len(baseline_shots)}")
        print(
            f"      Baseline recall: {baseline_eval['recall_pct']}% "
            f"({baseline_eval['hits']}/{baseline_eval['truth_count']})"
        )
        if baseline_eval["missed"]:
            print(f"      Baseline missed footages: {baseline_eval['missed']}")

        all_results.append(
            {
                "pdf": pdf_name,
                "approach": "baseline_marker",
                "model": "none",
                "chunk_size": "n/a",
                **{k: v for k, v in baseline_eval.items()},
            }
        )

        # Step 2: Test each model x chunk_size combination
        for model in models:
            for cs in chunk_sizes:
                label = f"{model.replace(':', '-')}_chunk{cs}"
                print(f"\n  [{label}]")

                try:
                    result = chunked_llm_cleanup(raw_md, model, cs)

                    out_path = os.path.join(OUTPUT_DIR, f"{base}_{label}.md")
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(result["text"])

                    shots = count_shot_rows(result["text"])
                    eval_result = evaluate_against_truth(shots, pdf_name)

                    print(f"      Total time: {result['elapsed_s']}s")
                    print(f"      Shots found: {len(shots)}")
                    print(
                        f"      Recall: {eval_result['recall_pct']}% "
                        f"({eval_result['hits']}/{eval_result['truth_count']})"
                    )
                    if eval_result["missed"]:
                        print(f"      MISSED footages: {eval_result['missed']}")
                    if eval_result["extra"]:
                        print(f"      Extra footages: {eval_result['extra']}")

                    # Show first 500 chars of output
                    print(f"      --- Output preview ---")
                    for line in result["text"][:500].split("\n"):
                        print(f"      {line}")
                    print(f"      ---")

                    all_results.append(
                        {
                            "pdf": pdf_name,
                            "approach": "chunked_llm",
                            "model": model,
                            "chunk_size": cs,
                            "elapsed_s": result["elapsed_s"],
                            "num_chunks": result["num_chunks"],
                            **{k: v for k, v in eval_result.items()},
                        }
                    )

                except Exception as e:
                    print(f"      ERROR: {e}")
                    import traceback

                    traceback.print_exc()

    # Save results
    summary_path = os.path.join(OUTPUT_DIR, "_comparison_summary.json")
    with open(summary_path, "w") as f:
        json.dump(all_results, f, indent=2)

    # Print summary table
    print(f"\n\n{'='*90}")
    print("SUMMARY")
    print(f"{'='*90}")
    print(
        f"{'PDF':<15} {'Approach':<40} {'Time':>6} {'Recall':>8} "
        f"{'Missed':>20} {'Extra':>20}"
    )
    print("-" * 110)
    for r in all_results:
        approach = r["approach"]
        if approach == "chunked_llm":
            approach = f"{r['model']}_chunk{r['chunk_size']}"
        print(
            f"{r['pdf']:<15} {approach:<40} "
            f"{str(r.get('elapsed_s', '-')):>6} "
            f"{r.get('recall_pct', '-'):>7}% "
            f"{str(r.get('missed', [])):>20} "
            f"{str(r.get('extra', [])):>20}"
        )

    print(f"\nDetailed results: {summary_path}")


if __name__ == "__main__":
    main()
