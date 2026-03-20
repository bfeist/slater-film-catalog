"""
Stage 1c: LLM vision OCR — run all shotlist PDFs through Qwen3.5:9b via Ollama.

Processes every PDF in static_assets/shotlist_pdfs/, sending page images to
a local vision LLM for independent transcription.  Outputs are written to
data/01c_llm_ocr/<stem>.json — completely separate from the marker-pdf outputs
in data/01_shotlist_raw/ which are never touched.  The downstream merge step
(1d) reads both directories independently and picks the best text from each.

Output goes to data/01c_llm_ocr/<stem>.json — one file per PDF, separate
from the marker-pdf outputs in data/01_shotlist_raw/.  The downstream merge
step (1d) reads both directories independently.

JSON layout written to data/01c_llm_ocr/:
    {
      "filename": "FR-0187.pdf",
      "llm_text": "<LLM output>",
      "llm": {
        "model": "qwen3.5:9b",
        "timestamp": "...",
        "pages_processed": 1,
        "page_timings": [...],
      }
    }

Anti-hallucination measures:
  - Non-thinking mode (/no_think) — no chain-of-thought drift
  - Temperature 0 — deterministic output
  - Strict prompt: extract content only, never invent, mark illegible as [illegible]

Resumable: skips PDFs that already have a JSON in data/01c_llm_ocr/ (unless --force).

Pipeline: 1a (marker OCR) → 1b (match) → 1c (LLM OCR) → 1d (merge + FTS5)

Usage:
    uv run python scripts/shotlist/1c_llm_ocr.py                    # process all
    uv run python scripts/shotlist/1c_llm_ocr.py --limit 50         # first 50 only
    uv run python scripts/shotlist/1c_llm_ocr.py --force             # re-process all
    uv run python scripts/shotlist/1c_llm_ocr.py --pdf FR-0187.pdf   # one file
    uv run python scripts/shotlist/1c_llm_ocr.py --dry-run           # show plan only
"""

import argparse
import base64
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF (fitz) is required: uv add pymupdf")

ROOT = Path(__file__).resolve().parents[2]
PDF_DIR = ROOT / "static_assets" / "shotlist_pdfs"
LLM_OUT_DIR = ROOT / "static_assets" / "llm_ocr"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3.5:9b"
DPI = 200  # render resolution for PDF pages

SYSTEM_PROMPT = (
    "You are indexing NASA archival film reels for a full-text search engine. "
    "This document is a shotlist, scene log, or camera report describing what was "
    "filmed on one or more reels.\n\n"
    "Extract the FILM CONTENT as plain text — what a researcher needs to find this footage:\n"
    "general subject, title, and category; names of people visible; locations and "
    "facilities; mission or program names (Mercury, Gemini, Apollo, Skylab, STS, etc.); "
    "spacecraft, hardware, equipment, and experiments shown; dates of filming; "
    "scene descriptions — what is visible or happens in each shot.\n\n"
    "Ignore anything that belongs to the DOCUMENT FORM rather than the film: "
    "page headers and page numbers, form IDs and order numbers, administrative codes, "
    "blank fields, lab or print-ordering information, film quality ratings "
    "(ftg. good/fair/poor), footage frame counters, edge or reel codes, "
    "and boilerplate facility headers that repeat on every page of the form.\n\n"
    "Rules:\n"
    "- Output plain text only — no bullet symbols, no bold, no markdown formatting\n"
    "- Copy all names and terms exactly as they appear; do not verify, correct, "
    "or reason about them\n"
    "- Do not add reasoning, commentary, or explanations — only the film content\n"
    "- If text is illegible, write [illegible]\n"
    "- Output only the extracted film content, nothing else"
)

# Loop-detection tuning
_LOOP_WINDOW = 600       # chars of tail to inspect
_LOOP_MIN_PAT = 3        # minimum repeated unit length
_LOOP_THRESHOLD = 10     # consecutive repeats → loop
_LOOP_CHECK_EVERY = 80   # check after accumulating this many new chars


# ---------------------------------------------------------------------------
# Loop detection
# ---------------------------------------------------------------------------

def _detect_loop(text: str) -> tuple[bool, int]:
    """Return (True, trunc_index) when `text` ends in a repetition loop.

    Scans the last _LOOP_WINDOW characters for the shortest pattern of
    length >= _LOOP_MIN_PAT that repeats >= _LOOP_THRESHOLD times
    consecutively.  On detection, returns the index in `text` just before
    the loop starts so callers can truncate cleanly.
    """
    if len(text) < _LOOP_WINDOW:
        return False, -1
    tail = text[-_LOOP_WINDOW:]
    max_plen = _LOOP_WINDOW // _LOOP_THRESHOLD
    for plen in range(_LOOP_MIN_PAT, max_plen + 1):
        pattern = tail[-plen:]
        count = 1
        pos = len(tail) - plen
        while pos >= plen and tail[pos - plen : pos] == pattern:
            count += 1
            pos -= plen
        if count >= _LOOP_THRESHOLD:
            trunc_abs = len(text) - _LOOP_WINDOW + pos
            return True, max(0, trunc_abs)
    return False, -1


# ---------------------------------------------------------------------------
# Ollama API
# ---------------------------------------------------------------------------

def ollama_vision(image_b64: str, *, timeout: int = 180) -> dict:
    """Send a page image to the vision model, streaming tokens to stdout."""
    payload = json.dumps({
        "model": MODEL,
        "prompt": SYSTEM_PROMPT,
        "images": [image_b64],
        "think": False,
        "stream": True,
        "options": {"temperature": 0, "num_predict": 4096},
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    resp = urllib.request.urlopen(req, timeout=timeout)
    chunks: list[str] = []
    eval_duration = 0
    total_duration = 0
    loop_detected = False
    chars_since_check = 0

    for line in resp:
        if not line.strip():
            continue
        chunk = json.loads(line)
        token = chunk.get("response", "")
        if token:
            print(token, end="")
            chunks.append(token)
            chars_since_check += len(token)
            if chars_since_check >= _LOOP_CHECK_EVERY:
                chars_since_check = 0
                full_text = "".join(chunks)
                looped, trunc_at = _detect_loop(full_text)
                if looped:
                    loop_detected = True
                    print("\n  [LOOP DETECTED — aborting]", flush=True)
                    try:
                        resp.close()
                    except Exception:
                        pass
                    chunks = [full_text[:trunc_at]]
                    break
        if chunk.get("done"):
            eval_duration = chunk.get("eval_duration", 0)
            total_duration = chunk.get("total_duration", 0)

    print()  # newline after streamed output

    return {
        "text": "".join(chunks),
        "loop_detected": loop_detected,
        "eval_duration_s": round(eval_duration / 1e9, 2),
        "total_duration_s": round(total_duration / 1e9, 2),
    }


def check_ollama() -> bool:
    """Verify Ollama is running and the required model is available."""
    try:
        resp = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
        data = json.loads(resp.read())
        model_names = [m["name"] for m in data.get("models", [])]
        if MODEL not in model_names:
            print(f"  ERROR: Model '{MODEL}' not found in Ollama.")
            print(f"  Available: {', '.join(model_names)}")
            return False
        return True
    except Exception as e:
        print(f"  ERROR: Cannot connect to Ollama at {OLLAMA_URL}: {e}")
        return False


# ---------------------------------------------------------------------------
# PDF → page images
# ---------------------------------------------------------------------------

def pdf_to_images(pdf_path: Path) -> list[str]:
    """Render each page of a PDF to a base64-encoded PNG."""
    doc = fitz.open(str(pdf_path))
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=DPI)
        images.append(base64.b64encode(pix.tobytes("png")).decode())
    doc.close()
    return images


# ---------------------------------------------------------------------------
# Collect work list
# ---------------------------------------------------------------------------

def collect_work_list(
    *, force: bool = False, single_pdf: str | None = None
) -> list[Path]:
    """Return PDF paths that still need LLM processing."""
    LLM_OUT_DIR.mkdir(parents=True, exist_ok=True)

    if single_pdf:
        pdf_path = PDF_DIR / single_pdf
        if not pdf_path.exists():
            sys.exit(f"PDF not found: {pdf_path}")
        return [pdf_path]

    work = []
    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        out_json = LLM_OUT_DIR / f"{pdf_path.stem}.json"
        if not force and out_json.exists():
            continue
        work.append(pdf_path)

    return work


# ---------------------------------------------------------------------------
# Process one PDF
# ---------------------------------------------------------------------------

def process_pdf(pdf_path: Path) -> dict | None:
    """Run one PDF through LLM vision OCR. Returns output dict."""
    try:
        page_images = pdf_to_images(pdf_path)
    except Exception as e:
        print(f"    ERROR rendering {pdf_path.name}: {e}")
        return None

    page_texts = []
    page_timings = []
    for i, img_b64 in enumerate(page_images):
        try:
            print(f"    --- Page {i + 1}/{len(page_images)} ---", flush=True)
            result = ollama_vision(img_b64)
            page_texts.append(result["text"])
            page_timings.append({
                "page": i + 1,
                "eval_s": result["eval_duration_s"],
                "total_s": result["total_duration_s"],
                "chars": len(result["text"]),
            })
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"    ERROR on page {i+1}: {e}")
            page_texts.append("")
            page_timings.append({"page": i + 1, "error": str(e)})
            continue

        if result.get("loop_detected"):
            page_timings[-1]["loop_detected"] = True
            print(f"    WARNING: loop detected on page {i + 1}, output truncated")

    llm_text = "\n\n".join(t for t in page_texts if t.strip())

    return {
        "filename": pdf_path.name,
        "llm_text": llm_text,
        "llm": {
            "model": MODEL,
            "dpi": DPI,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "pages_processed": len(page_images),
            "page_timings": page_timings,
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM vision OCR for shotlist PDFs (Qwen3.5 via Ollama)"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Process at most N PDFs"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-process PDFs that already have llm_text"
    )
    parser.add_argument(
        "--pdf", type=str, default=None,
        help="Process a single PDF (e.g., FR-0187.pdf)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show work list without processing"
    )
    args = parser.parse_args()

    print(f"Stage 1c: LLM Vision OCR (model: {MODEL})")
    print(f"  PDFs:   {PDF_DIR}")
    print(f"  Output: {LLM_OUT_DIR}")
    print()

    LLM_OUT_DIR.mkdir(parents=True, exist_ok=True)
    work = collect_work_list(force=args.force, single_pdf=args.pdf)

    if args.limit and len(work) > args.limit:
        work = work[:args.limit]

    all_pdfs = list(PDF_DIR.glob("*.pdf"))
    already_done = sum(1 for p in all_pdfs if (LLM_OUT_DIR / f"{p.stem}.json").exists())

    print(f"  Total PDFs:          {len(all_pdfs)}")
    print(f"  Already have LLM:    {already_done}")
    print(f"  To process:          {len(work)}")

    if not work:
        print("  Nothing to process.")
        return

    if args.dry_run:
        for pdf_path in work[:20]:
            print(f"    {pdf_path.name}")
        if len(work) > 20:
            print(f"    ... and {len(work) - 20} more")
        print("\n  --dry-run: stopping here.")
        return

    if not check_ollama():
        sys.exit(1)
    print(f"  Ollama OK\n")

    processed = 0
    failed = 0
    t_start = time.time()

    try:
        for i, pdf_path in enumerate(work, 1):
            t0 = time.time()
            print(f"  [{i}/{len(work)}] {pdf_path.name}", flush=True)
            result = process_pdf(pdf_path)
            elapsed = time.time() - t0

            if result is None:
                failed += 1
                print(f"  [{i}/{len(work)}] FAIL {pdf_path.name} ({elapsed:.1f}s)")
                continue

            llm_alpha = len(re.findall(r"[A-Za-z]", result.get("llm_text", "")))

            out_json = LLM_OUT_DIR / f"{pdf_path.stem}.json"
            out_json.write_text(
                json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            processed += 1
            rate = processed / (time.time() - t_start)
            remaining = (len(work) - i) / rate if rate > 0 else 0
            eta_m = remaining / 60

            print(
                f"  [{i}/{len(work)}] {pdf_path.name}: "
                f"llm={llm_alpha} chars "
                f"({elapsed:.1f}s) "
                f"ETA: {eta_m:.0f}m"
            )
    except KeyboardInterrupt:
        print(f"\n  Interrupted. Processed {processed} so far (resumable — re-run to continue).")
        sys.exit(0)

    total_elapsed = time.time() - t_start
    print(f"\nDone. Processed: {processed}, Failed: {failed} ({total_elapsed:.0f}s)")
    if processed:
        print("  Next: uv run python scripts/shotlist/1d_build_fts_index.py")


if __name__ == "__main__":
    main()
