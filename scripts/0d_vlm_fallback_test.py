"""
VLM fallback extraction for PDFs where marker-pdf produces poor/noisy output.

Uses Qwen2.5-VL-7B-Instruct to directly read page images from scanned PDFs.
This model excels at document understanding and text extraction from degraded scans.

Designed to process PDFs that scored "poor" or "uncertain" in the spot check
(scripts/0c_spot_check_100.py), where marker's OCR captured table structure
but failed to read the actual text content.

Usage:
    uv run python scripts/0d_vlm_fallback_test.py
    uv run python scripts/0d_vlm_fallback_test.py --quality poor          # only poor
    uv run python scripts/0d_vlm_fallback_test.py --quality poor,uncertain # both
    uv run python scripts/0d_vlm_fallback_test.py --files FR-0146.pdf,FR-9215.pdf
"""

import argparse
import gc
import json
import os
import re
import time
from io import BytesIO
from pathlib import Path

import torch

INPUT_DIR = "input_indexes/MASTER FR shotlist folder"
SPOT_CHECK_RESULTS = "data/spot_check_100/_results.json"
OUTPUT_DIR = "data/vlm_fallback"

# The model to use — 7B fits comfortably on RTX 4090 in float16
MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"

EXTRACTION_PROMPT = """\
You are reading a scanned NASA film shot list document from the 1960s-1970s.
This is a photograph of a typewritten or handwritten form.

Extract ALL text content from this page exactly as written. Preserve the document structure.

Output format — use this exact structure:

HEADER:
- CATEGORY: [category text]
- REF NO: [reference number]
- SOURCE: [source]
- FILM SITE: [film site]
- FILMED: [date filmed]
- DATE RECD: [date received]
- FILE ROLL NO: [number]
- CLASSIFICATION: [classification]
- MATERIAL: [material type]
- TOTAL FOOTAGE: [number]
- SUBJECT: [subject text]
- FOREWORD: [foreword text]
- REMARKS: [any remarks]
- PAGE: [page X of Y]

SHOTS:
| FOOTAGE | ANGLE | DESCRIPTION |
|---------|-------|-------------|
| [number] | [angle code like MS, LS, MCU, MLS, CU, etc.] | [description text] |

Read EXACTLY what is written. Do NOT invent or guess missing content.
If text is illegible, write [illegible]. For blank fields, write [blank].
Preserve all footage numbers exactly as printed.
Include EVERY shot entry, even "SLATE" or "END OF ROLL".
Output ONLY the extracted data — no commentary, no repetition of these instructions.
"""


def convert_pdf_to_images(pdf_path: str) -> list:
    """Convert PDF pages to PIL Image objects."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        # Fall back to pdf2image which uses poppler
        try:
            from pdf2image import convert_from_path
            return convert_from_path(pdf_path, dpi=200)
        except ImportError:
            pass

        # Last resort: use marker's built-in page rendering
        from marker.converters.pdf import PdfConverter
        raise ImportError(
            "Need PyMuPDF (fitz) or pdf2image. Install with: uv pip install pymupdf"
        )

    doc = fitz.open(pdf_path)
    images = []
    for page in doc:
        # Render at 200 DPI for good OCR quality without being too large
        mat = fitz.Matrix(200 / 72, 200 / 72)
        pix = page.get_pixmap(matrix=mat)
        from PIL import Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    doc.close()
    return images


def load_model():
    """Load Qwen2.5-VL model and processor."""
    from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor

    print(f"Loading {MODEL_ID}...")
    t0 = time.time()

    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        device_map="auto",
        # Limit image token count to manage VRAM
        # These scans are single-page documents, don't need huge resolution
    )

    processor = AutoProcessor.from_pretrained(
        MODEL_ID,
        min_pixels=256 * 28 * 28,
        max_pixels=1024 * 28 * 28,
    )

    print(f"Model loaded in {time.time() - t0:.1f}s")
    return model, processor


def extract_page(
    model, processor, image, page_num: int = 1, total_pages: int = 1
) -> str:
    """Extract text from a single page image using the VLM."""
    from qwen_vl_utils import process_vision_info

    page_context = ""
    if total_pages > 1:
        page_context = f"\nThis is page {page_num} of {total_pages}."

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": EXTRACTION_PROMPT + page_context},
            ],
        }
    ]

    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)

    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=4096,
            temperature=0.1,  # Near-deterministic for faithful extraction
            do_sample=True,
            top_p=0.9,
        )

    # Decode only the generated tokens (skip the input)
    generated_ids = output_ids[0][inputs.input_ids.shape[1]:]
    result = processor.tokenizer.decode(generated_ids, skip_special_tokens=True)

    return result


def process_pdf(model, processor, pdf_path: str) -> dict:
    """Process a complete PDF through the VLM pipeline."""
    t0 = time.time()

    images = convert_pdf_to_images(pdf_path)
    num_pages = len(images)

    page_results = []
    for i, img in enumerate(images, 1):
        print(f"      Page {i}/{num_pages}...", end=" ", flush=True)
        pt = time.time()
        text = extract_page(model, processor, img, i, num_pages)
        page_time = time.time() - pt
        print(f"{page_time:.1f}s, {len(text)} chars")
        page_results.append({
            "page": i,
            "text": text,
            "elapsed_s": round(page_time, 1),
        })

        # Clear image from memory
        del img

    total_time = time.time() - t0
    combined_text = "\n\n---\n\n".join(p["text"] for p in page_results)

    return {
        "num_pages": num_pages,
        "elapsed_s": round(total_time, 1),
        "pages": page_results,
        "combined_text": combined_text,
    }


def main():
    parser = argparse.ArgumentParser(description="VLM fallback for poor OCR PDFs")
    parser.add_argument(
        "--quality", "-q", default="poor",
        help="Comma-separated quality tiers to re-process (default: poor)",
    )
    parser.add_argument(
        "--files", "-f", default=None,
        help="Comma-separated specific PDF filenames to process (overrides --quality)",
    )
    parser.add_argument(
        "--limit", "-n", type=int, default=None,
        help="Max PDFs to process",
    )
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Determine which PDFs to process
    if args.files:
        pdf_files = [f.strip() for f in args.files.split(",")]
    else:
        # Load spot check results and filter by quality
        if not os.path.exists(SPOT_CHECK_RESULTS):
            print(f"ERROR: {SPOT_CHECK_RESULTS} not found. Run 0c_spot_check_100.py first.")
            return

        with open(SPOT_CHECK_RESULTS, "r") as f:
            results = json.load(f)

        target_qualities = {q.strip() for q in args.quality.split(",")}
        pdf_files = [
            r["filename"] for r in results
            if r["analysis"]["quality"] in target_qualities
        ]

    if args.limit:
        pdf_files = pdf_files[:args.limit]

    print(f"PDFs to process: {len(pdf_files)}")
    for f in pdf_files:
        print(f"  {f}")

    # Check pymupdf
    try:
        import fitz
        print(f"\nPyMuPDF version: {fitz.version}")
    except ImportError:
        print("\nWARNING: PyMuPDF not installed. Install with: uv pip install pymupdf")
        return

    # Load model
    model, processor = load_model()

    all_results = []

    for i, pdf_name in enumerate(pdf_files, 1):
        pdf_path = os.path.join(INPUT_DIR, pdf_name)
        if not os.path.exists(pdf_path):
            print(f"\n[{i}/{len(pdf_files)}] SKIP: {pdf_path} not found")
            continue

        base = os.path.splitext(pdf_name)[0]
        size_kb = os.path.getsize(pdf_path) / 1024

        print(f"\n[{i}/{len(pdf_files)}] {pdf_name} ({size_kb:.0f} KB)")

        try:
            result = process_pdf(model, processor, pdf_path)
        except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
            print(f"    ERROR: {e}")
            torch.cuda.empty_cache()
            gc.collect()
            all_results.append({
                "filename": pdf_name,
                "file_size_kb": round(size_kb, 1),
                "num_pages": 0,
                "elapsed_s": 0,
                "output_chars": 0,
                "error": str(e),
            })
            continue

        # Save VLM output
        out_md = os.path.join(OUTPUT_DIR, f"{base}_vlm.md")
        with open(out_md, "w", encoding="utf-8") as f:
            f.write(result["combined_text"])

        # Save full result with metadata
        out_json = os.path.join(OUTPUT_DIR, f"{base}_vlm.json")
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump({
                "filename": pdf_name,
                "model": MODEL_ID,
                "file_size_bytes": os.path.getsize(pdf_path),
                **result,
            }, f, indent=2)

        all_results.append({
            "filename": pdf_name,
            "file_size_kb": round(size_kb, 1),
            "num_pages": result["num_pages"],
            "elapsed_s": result["elapsed_s"],
            "output_chars": len(result["combined_text"]),
        })

        print(f"    Total: {result['elapsed_s']:.1f}s, {len(result['combined_text'])} chars")

        # Clear CUDA cache between PDFs
        torch.cuda.empty_cache()
        gc.collect()

    # Save summary
    summary_path = os.path.join(OUTPUT_DIR, "_summary.json")
    with open(summary_path, "w") as f:
        json.dump(all_results, f, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"{'PDF':<35} {'Pages':>5} {'Time':>7} {'Chars':>7}")
    print("-" * 60)
    for r in all_results:
        print(f"{r['filename']:<35} {r['num_pages']:>5} {r['elapsed_s']:>6.1f}s {r['output_chars']:>7}")

    total_time = sum(r["elapsed_s"] for r in all_results)
    print(f"\nTotal time: {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"Outputs in: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
