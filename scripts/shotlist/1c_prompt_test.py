"""
Prompt comparison test for 1c_llm_ocr.py.

Runs 10 representative PDFs through two candidate prompts and writes
side-by-side results to data/01c_prompt_test/.

For each PDF we output:
  <stem>_A.txt  — current (exclusion-list) prompt
  <stem>_B.txt  — new (role-based) prompt
  <stem>_marker.txt — marker OCR output from 01_shotlist_raw/<stem>.md

Usage:
    uv run python scripts/shotlist/1c_prompt_test.py
    uv run python scripts/shotlist/1c_prompt_test.py --prompt B   # B only (faster)
    uv run python scripts/shotlist/1c_prompt_test.py --pdf 255-PV-44.pdf
"""

import argparse
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

try:
    import fitz
except ImportError:
    sys.exit("PyMuPDF (fitz) required: uv add pymupdf")

ROOT = Path(__file__).resolve().parents[2]
PDF_DIR = ROOT / "static_assets" / "shotlist_pdfs"
MARKER_DIR = ROOT / "data" / "01_shotlist_raw"
OLD_LLM_DIR = ROOT / "static_assets" / "llm_ocr"
OUT_DIR = ROOT / "data" / "01c_prompt_test"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3.5:9b"
DPI = 200

# ------------------------------------------------------------------
# PROMPT A — current exclusion-list prompt (from 1c_llm_ocr.py)
# ------------------------------------------------------------------
PROMPT_A = (
    "Extract searchable content from this NASA film reel shotlist document. "
    "These are typewritten catalog sheets describing scenes on 16mm or 35mm film reels.\n\n"
    "KEEP: Scene descriptions; category, subject, and title text; mission/program names "
    "(Mercury, Gemini, Apollo, Skylab, etc.); filming locations and dates; "
    "people's names; spacecraft, equipment, and experiment names; any text describing "
    "what is visible in the footage.\n\n"
    "OMIT entirely — do not transcribe:\n"
    "\u2022 Column headers: FOOTAGE START, CAMERA ANGLE, SCENE NO., EDGE NUMBER, PL NUMBER, "
    "KSC NUMBER, ROLL, SCENE, DESCRIPTION (the label itself)\n"
    "\u2022 Administrative fields with their values: CLASSIFICATION, MATERIAL, DATE RECD., "
    "FILE ROLL NO., Ref No., PL NO., REMARKS, PRODUCTION NUMBER, RUN TIME, LENGTH, "
    "FILM TYPE, MAILING SYMBOL, EDITOR'S NAME, REQUESTED BY, page-header lines (Page N of N)\n"
    "\u2022 Form identifiers: MSC Form 981, KSC FORM, VISRecord, COR FORM, "
    "MOTION PICTURE SUBJECT LOG, SCENE LOG BREAKDOWN\n"
    "\u2022 Facility boilerplate: KENNEDY SPACE CENTER FLORIDA 32899, "
    "NASA Manned Spacecraft Center, 65mm Panavision (as a header line)\n"
    "\u2022 Film quality notes: ftg. good, ftg. fair, ftg. poor, OUT stamps\n"
    "\u2022 Standalone camera angle codes without an accompanying description: "
    "MS, LS, CU, MCU, MLS, ELS, MCS, HMS, HA, LA, WS\n"
    "\u2022 Bare footage frame numbers (lone integers) and edge/reel codes (e.g. 3G-082)\n"
    "\u2022 Repetitive filler: SAME AS ABOVE, Same as previous scene, THRU, "
    "END OF ROLL, ditto symbols\n\n"
    "Do not invent anything not visible in the document. "
    "If text is illegible, write [illegible]. "
    "Output only the extracted content, nothing else."
)

# ------------------------------------------------------------------
# PROMPT B — refined role/semantic framing (final version matching 1c_llm_ocr.py)
# ------------------------------------------------------------------
PROMPT_B = (
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

# ------------------------------------------------------------------
# Test PDF selection — 10 PDFs covering format diversity
# ------------------------------------------------------------------
TEST_PDFS = [
    # Unusual formats / complex multi-page docs
    "255-PV-121.pdf",  # News dope sheet + Technicolor lab orders — hardest case
    "255-PV-44.pdf",   # Standard KSC log, 4 pages, important names
    # FR standard shot cards
    "FR-0001.pdf",
    "FR-0002.pdf",
    "FR-0007.pdf",
    # Skylab / different style
    "-FR-A241.pdf",    # Skylab kinescope with transcript-like content
    # More PV variety
    "255-PV-33.pdf",   # Apollo 8 night shots
    "255-PV-36.pdf",   # Larger LLM output (4689 chars) — good stress test
    "255-PV-68.pdf",   # 2414 chars, mid-size
    "255-PV-28.pdf",   # 1886 chars
]


def pdf_to_images(pdf_path: Path) -> list[str]:
    doc = fitz.open(str(pdf_path))
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=DPI)
        images.append(base64.b64encode(pix.tobytes("png")).decode())
    doc.close()
    return images


def run_prompt(image_b64: str, prompt: str, timeout: int = 300) -> str:
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "images": [image_b64],
        "think": False,
        "stream": True,
        "options": {"temperature": 0, "num_predict": 4096},
    }).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=timeout)
    chunks = []
    for line in resp:
        if not line.strip():
            continue
        chunk = json.loads(line)
        tok = chunk.get("response", "")
        if tok:
            print(tok, end="", flush=True)
            chunks.append(tok)
    print()
    return "".join(chunks)


def process_pdf_with_prompt(pdf_path: Path, prompt: str, label: str) -> str:
    images = pdf_to_images(pdf_path)
    page_texts = []
    for i, img in enumerate(images):
        print(f"    [{label}] page {i+1}/{len(images)}", flush=True)
        text = run_prompt(img, prompt)
        page_texts.append(text)
    return "\n\n".join(t for t in page_texts if t.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", choices=["A", "B", "both"], default="both")
    parser.add_argument("--pdf", default=None)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = [args.pdf] if args.pdf else TEST_PDFS
    run_a = args.prompt in ("A", "both")
    run_b = args.prompt in ("B", "both")

    print(f"Prompt test: {len(pdfs)} PDFs, prompts={'AB' if args.prompt=='both' else args.prompt}")
    print(f"Output: {OUT_DIR}\n")

    for pdf_name in pdfs:
        pdf_path = PDF_DIR / pdf_name
        if not pdf_path.exists():
            print(f"  SKIP {pdf_name} — not found")
            continue

        stem = pdf_path.stem
        print(f"\n{'='*60}")
        print(f"  {pdf_name}")
        print(f"{'='*60}")

        # Write marker text for reference
        marker_md = MARKER_DIR / f"{stem}.md"
        if marker_md.exists():
            marker_text = marker_md.read_text(encoding="utf-8", errors="replace")
            (OUT_DIR / f"{stem}_marker.txt").write_text(marker_text, encoding="utf-8")
            print(f"  marker: {len(marker_text)} chars written")

        # Write old LLM output for reference
        old_llm = OLD_LLM_DIR / f"{stem}.json"
        if old_llm.exists():
            old_data = json.loads(old_llm.read_text(encoding="utf-8"))
            old_text = old_data.get("llm_text", "")
            (OUT_DIR / f"{stem}_old_llm.txt").write_text(old_text, encoding="utf-8")
            print(f"  old LLM: {len(old_text)} chars written")

        # Run Prompt A
        if run_a:
            t0 = time.time()
            text_a = process_pdf_with_prompt(pdf_path, PROMPT_A, "A")
            (OUT_DIR / f"{stem}_A.txt").write_text(text_a, encoding="utf-8")
            print(f"  Prompt A: {len(text_a)} chars ({time.time()-t0:.0f}s)")

        # Run Prompt B
        if run_b:
            t0 = time.time()
            text_b = process_pdf_with_prompt(pdf_path, PROMPT_B, "B")
            (OUT_DIR / f"{stem}_B.txt").write_text(text_b, encoding="utf-8")
            print(f"  Prompt B: {len(text_b)} chars ({time.time()-t0:.0f}s)")

    print(f"\nDone. Results in {OUT_DIR}")
    print("Compare with: ls data/01c_prompt_test/")


if __name__ == "__main__":
    main()
