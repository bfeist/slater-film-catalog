"""
Spot-check script: run marker-pdf on a few sample shotlist PDFs
to evaluate OCR quality on these scanned typewritten documents.

Usage:
    uv run python scripts/0_spot_check_marker.py
"""

import json
import os
import sys
import time

INPUT_DIR = "input_indexes/MASTER FR shotlist folder"
OUTPUT_DIR = "data/marker_spot_checks"

# Pick a small, medium, and large PDF
SPOT_CHECK_FILES = [
    "FR-0001.pdf",      # first reel
    "FR-2041.pdf",      # median-sized
    "FR-1902.pdf",      # largest file
]


def main():
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered
    from marker.config.parser import ConfigParser

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # These PDFs are scanned images of typewritten documents, so force OCR
    config = {
        "output_format": "markdown",
        "force_ocr": True,
    }
    config_parser = ConfigParser(config)

    print("Loading marker models (first run downloads them)...")
    t0 = time.time()
    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
    )
    print(f"Models loaded in {time.time() - t0:.1f}s")

    for pdf_name in SPOT_CHECK_FILES:
        pdf_path = os.path.join(INPUT_DIR, pdf_name)
        if not os.path.exists(pdf_path):
            print(f"SKIP: {pdf_path} not found")
            continue

        print(f"\nProcessing {pdf_name} ({os.path.getsize(pdf_path)/1024:.1f} KB)...")
        t1 = time.time()
        rendered = converter(pdf_path)
        text, metadata, images = text_from_rendered(rendered)
        elapsed = time.time() - t1

        # Save markdown output
        base = os.path.splitext(pdf_name)[0]
        md_path = os.path.join(OUTPUT_DIR, f"{base}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(text)

        # Save metadata as JSON
        meta_path = os.path.join(OUTPUT_DIR, f"{base}_metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, default=str)

        # Summary
        lines = text.strip().split("\n")
        print(f"  Done in {elapsed:.1f}s")
        print(f"  Output: {len(text)} chars, {len(lines)} lines")
        print(f"  Images extracted: {len(images)}")
        print(f"  First 500 chars:\n{'='*60}")
        print(text[:500])
        print("=" * 60)


if __name__ == "__main__":
    main()
