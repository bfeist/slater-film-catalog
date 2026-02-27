"""
Benchmark: Qwen3-VL-8B fp16 vs Qwen3-VL-8B NF4 4-bit on VLM fallback PDFs.

Compares Qwen3-VL-8B at full precision vs NF4 4-bit quantization (bitsandbytes)
to measure speed/quality tradeoff. Qwen3-VL has significantly improved OCR
(32 languages, better degraded scan handling).

Both variants fit on RTX 4090 (24 GB):
  - Qwen3-VL-8B fp16:   ~16 GB VRAM
  - Qwen3-VL-8B NF4:    ~6 GB VRAM

Usage:
    uv run python scripts/0e_vlm_quant_benchmark.py                     # both defaults
    uv run python scripts/0e_vlm_quant_benchmark.py --limit 3           # quick test
    uv run python scripts/0e_vlm_quant_benchmark.py --variant qwen3     # Qwen3 fp16 only
    uv run python scripts/0e_vlm_quant_benchmark.py --variant qwen3_bnb4  # Qwen3 NF4 only
"""

import argparse
import gc
import json
import os
import time

import torch

INPUT_DIR = "input_indexes/MASTER FR shotlist folder"
SPOT_CHECK_RESULTS = "data/spot_check_100/_results.json"
OUTPUT_DIR = "data/vlm_quant_benchmark"

VARIANTS = {
    "qwen3": {
        "model_id": "Qwen/Qwen3-VL-8B-Instruct",
        "model_class": "Qwen3VLForConditionalGeneration",
        "description": "Qwen3-VL-8B fp16",
        "quantize": False,
    },
    "qwen3_bnb4": {
        "model_id": "Qwen/Qwen3-VL-8B-Instruct",
        "model_class": "Qwen3VLForConditionalGeneration",
        "description": "Qwen3-VL-8B NF4 4-bit (bitsandbytes)",
        "quantize": True,
    },
}

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
    """Convert PDF pages to PIL Image objects using PyMuPDF at 200 DPI."""
    import fitz
    from PIL import Image

    doc = fitz.open(pdf_path)
    images = []
    for page in doc:
        mat = fitz.Matrix(200 / 72, 200 / 72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    doc.close()
    return images


def load_model(variant_name: str):
    """Load model + processor for the given variant."""
    import transformers
    from transformers import AutoProcessor, BitsAndBytesConfig

    variant = VARIANTS[variant_name]
    model_id = variant["model_id"]
    model_cls = getattr(transformers, variant["model_class"])

    print(f"\n{'='*60}")
    print(f"Loading: {variant_name} — {variant['description']}")
    print(f"Model:   {model_id}")
    print(f"Class:   {variant['model_class']}")
    print(f"{'='*60}")

    load_kwargs = {"device_map": "auto"}

    if variant["quantize"]:
        load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
    else:
        load_kwargs["torch_dtype"] = torch.float16

    t0 = time.time()
    model = model_cls.from_pretrained(model_id, **load_kwargs)

    proc_kwargs = {
        "min_pixels": 256 * 28 * 28,
        "max_pixels": 1024 * 28 * 28,
    }

    processor = AutoProcessor.from_pretrained(model_id, **proc_kwargs)

    load_time = time.time() - t0
    print(f"Loaded in {load_time:.1f}s")

    if torch.cuda.is_available():
        vram_gb = torch.cuda.memory_allocated() / 1024**3
        print(f"VRAM allocated: {vram_gb:.1f} GB")

    return model, processor, load_time


def extract_page_qwen3(model, processor, image) -> str:
    """Extract text using Qwen3-VL API (processor.apply_chat_template handles images)."""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": EXTRACTION_PROMPT},
            ],
        }
    ]

    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=4096,
            temperature=0.1,
            do_sample=True,
            top_p=0.9,
        )

    generated_ids = output_ids[0][inputs.input_ids.shape[1]:]
    return processor.tokenizer.decode(generated_ids, skip_special_tokens=True)


def benchmark_variant(variant_name: str, pdf_files: list[str]) -> dict:
    """Run a single variant on all PDFs and collect timing + output."""
    model, processor, load_time = load_model(variant_name)

    extract_fn = extract_page_qwen3

    results = []

    # Warmup (first inference compiles CUDA kernels)
    warmup_path = os.path.join(INPUT_DIR, pdf_files[0])
    warmup_time = 0.0
    if os.path.exists(warmup_path):
        print(f"\nWarmup on {pdf_files[0]}...")
        warmup_images = convert_pdf_to_images(warmup_path)
        t0 = time.time()
        _ = extract_fn(model, processor, warmup_images[0])
        warmup_time = time.time() - t0
        print(f"  Warmup: {warmup_time:.1f}s")
        del warmup_images
        torch.cuda.empty_cache()

    for i, pdf_name in enumerate(pdf_files, 1):
        pdf_path = os.path.join(INPUT_DIR, pdf_name)
        if not os.path.exists(pdf_path):
            print(f"  [{i}/{len(pdf_files)}] SKIP: {pdf_name} not found")
            continue

        size_kb = os.path.getsize(pdf_path) / 1024
        images = convert_pdf_to_images(pdf_path)

        print(f"  [{i}/{len(pdf_files)}] {pdf_name} ({size_kb:.0f} KB, {len(images)} pg)")

        page_times = []
        page_texts = []
        for pi, img in enumerate(images, 1):
            t0 = time.time()
            text = extract_fn(model, processor, img)
            elapsed = time.time() - t0
            page_times.append(elapsed)
            page_texts.append(text)
            print(f"    Page {pi}: {elapsed:.1f}s, {len(text)} chars")
            del img

        combined_text = "\n\n---\n\n".join(page_texts)

        results.append({
            "filename": pdf_name,
            "file_size_kb": round(size_kb, 1),
            "num_pages": len(images),
            "page_times_s": [round(t, 2) for t in page_times],
            "total_time_s": round(sum(page_times), 2),
            "output_chars": len(combined_text),
            "combined_text": combined_text,
        })

        del images
        torch.cuda.empty_cache()

    # Capture peak VRAM
    vram_peak = 0.0
    if torch.cuda.is_available():
        vram_peak = torch.cuda.max_memory_allocated() / 1024**3

    # Unload
    del model, processor
    torch.cuda.empty_cache()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    return {
        "variant": variant_name,
        "description": VARIANTS[variant_name]["description"],
        "model_id": VARIANTS[variant_name]["model_id"],
        "load_time_s": round(load_time, 1),
        "warmup_time_s": round(warmup_time, 1),
        "vram_peak_gb": round(vram_peak, 2),
        "results": results,
    }


def print_comparison(benchmarks: list[dict]):
    """Print side-by-side comparison."""
    print(f"\n{'='*80}")
    print("BENCHMARK COMPARISON")
    print(f"{'='*80}")

    for bm in benchmarks:
        results = bm["results"]
        if not results:
            continue
        times = [r["total_time_s"] for r in results]
        chars = [r["output_chars"] for r in results]

        print(f"\n{bm['variant'].upper()} — {bm['description']}")
        print(f"  Model load:  {bm['load_time_s']:.1f}s")
        print(f"  VRAM peak:   {bm['vram_peak_gb']:.1f} GB")
        print(f"  PDFs:        {len(results)}")
        print(f"  Total time:  {sum(times):.1f}s ({sum(times)/60:.1f} min)")
        print(f"  Avg per PDF: {sum(times)/len(times):.1f}s")
        print(f"  Avg chars:   {sum(chars)/len(chars):.0f}")

    if len(benchmarks) >= 2:
        a, b = benchmarks[0], benchmarks[1]
        a_map = {r["filename"]: r for r in a["results"]}
        b_map = {r["filename"]: r for r in b["results"]}

        an = a["variant"].upper()
        bn = b["variant"].upper()

        print(f"\n{'PDF':<30} {an+' (s)':>12} {bn+' (s)':>12} {'Speedup':>8} {an+' ch':>10} {bn+' ch':>10}")
        print("-" * 84)

        speedups = []
        for fname in a_map:
            if fname in b_map:
                t_a = a_map[fname]["total_time_s"]
                t_b = b_map[fname]["total_time_s"]
                speedup = t_a / t_b if t_b > 0 else 0
                speedups.append(speedup)
                print(
                    f"{fname:<30} {t_a:>11.1f}s {t_b:>11.1f}s {speedup:>7.2f}x "
                    f"{a_map[fname]['output_chars']:>9} {b_map[fname]['output_chars']:>9}"
                )

        if speedups:
            print(f"\nAvg speedup ({bn} vs {an}): {sum(speedups)/len(speedups):.2f}x")

        est_count = 1000
        print(f"\nProjected fallback time (~{est_count} PDFs):")
        for bm in benchmarks:
            if bm["results"]:
                avg = sum(r["total_time_s"] for r in bm["results"]) / len(bm["results"])
                print(f"  {bm['variant']:>15}: {avg * est_count / 3600:.1f} hrs "
                      f"(avg {avg:.1f}s/PDF, VRAM {bm['vram_peak_gb']:.1f} GB)")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Qwen3-VL-8B fp16 vs NF4 4-bit"
    )
    parser.add_argument(
        "--variant", "-v", default=None,
        help="Comma-separated variants: qwen3, qwen3_bnb4 "
             "(default: qwen3,qwen3_bnb4)",
    )
    parser.add_argument("--limit", "-n", type=int, default=None)
    parser.add_argument(
        "--files", "-f", default=None,
        help="Comma-separated PDF filenames (overrides auto-selection)",
    )
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Select PDFs
    if args.files:
        pdf_files = [f.strip() for f in args.files.split(",")]
    else:
        if not os.path.exists(SPOT_CHECK_RESULTS):
            print(f"ERROR: {SPOT_CHECK_RESULTS} not found.")
            return
        with open(SPOT_CHECK_RESULTS) as f:
            results = json.load(f)
        pdf_files = [
            r["filename"] for r in results
            if r["analysis"]["quality"] == "poor"
        ]

    if args.limit:
        pdf_files = pdf_files[:args.limit]

    print(f"PDFs: {len(pdf_files)}")
    for f in pdf_files:
        print(f"  {f}")

    # Variants
    variant_names = (
        [v.strip() for v in args.variant.split(",")]
        if args.variant
        else ["qwen3", "qwen3_bnb4"]
    )
    for v in variant_names:
        if v not in VARIANTS:
            print(f"ERROR: Unknown variant '{v}'. Choose from: {', '.join(VARIANTS)}")
            return

    benchmarks = []
    for vn in variant_names:
        bm = benchmark_variant(vn, pdf_files)
        benchmarks.append(bm)

        # Save results (strip full text for JSON)
        save_results = []
        for r in bm["results"]:
            sr = {k: v for k, v in r.items() if k != "combined_text"}
            sr["text_preview"] = r["combined_text"][:500]
            save_results.append(sr)

        vpath = os.path.join(OUTPUT_DIR, f"_{vn}_results.json")
        with open(vpath, "w") as f:
            json.dump({**bm, "results": save_results}, f, indent=2)
        print(f"\nSaved to {vpath}")

        # Save full markdown outputs
        for r in bm["results"]:
            base = os.path.splitext(r["filename"])[0]
            md_path = os.path.join(OUTPUT_DIR, f"{base}_{vn}.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(r["combined_text"])

    print_comparison(benchmarks)

    # Summary JSON
    summary = {
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "pdf_count": len(pdf_files),
        "pdfs": pdf_files,
        "variants": [],
    }
    for bm in benchmarks:
        vs = {
            "variant": bm["variant"],
            "model_id": bm["model_id"],
            "description": bm["description"],
            "load_time_s": bm["load_time_s"],
            "vram_peak_gb": bm["vram_peak_gb"],
        }
        if bm["results"]:
            vs["total_inference_s"] = round(
                sum(r["total_time_s"] for r in bm["results"]), 1
            )
            vs["avg_per_pdf_s"] = round(
                sum(r["total_time_s"] for r in bm["results"]) / len(bm["results"]), 1
            )
        summary["variants"].append(vs)

    spath = os.path.join(OUTPUT_DIR, "_benchmark_summary.json")
    with open(spath, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary: {spath}")


if __name__ == "__main__":
    main()
