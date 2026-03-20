"""
Stage 1e: Compare 1a (marker-pdf OCR) vs 1c (LLM vision OCR) quality.

Runs detailed quality analysis on both OCR pipelines to determine if
the 1a marker-pdf process adds value over the 1c LLM OCR alone.

Usage:
    uv run python scripts/shotlist/1e_compare_ocr_quality.py
    uv run python scripts/shotlist/1e_compare_ocr_quality.py --detailed  # show per-file
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKER_DIR = ROOT / "data" / "01_shotlist_raw"
LLM_DIR = ROOT / "static_assets" / "llm_ocr"


def alpha_count(text: str) -> int:
    return sum(1 for c in text if c.isalpha())


def tokenize(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[a-zA-Z]{3,}", text)}


def unique_word_count(text: str) -> int:
    return len(tokenize(text))


def meaningful_line_count(text: str) -> int:
    return sum(1 for line in text.split("\n") if len(line.strip()) > 10)


def load_marker(stem: str) -> dict:
    path = MARKER_DIR / f"{stem}.json"
    data = json.loads(path.read_text("utf-8"))
    return {
        "text": data.get("text", ""),
        "quality": data.get("analysis", {}).get("quality", "unknown"),
        "needs_vlm": data.get("analysis", {}).get("needs_vlm_fallback", False),
        "alpha_ratio": data.get("analysis", {}).get("alpha_ratio", 0),
    }


def load_llm(stem: str) -> dict:
    path = LLM_DIR / f"{stem}.json"
    data = json.loads(path.read_text("utf-8"))
    return {
        "text": data.get("llm_text", ""),
        "pages": data.get("llm", {}).get("pages_processed", 0),
        "model": data.get("llm", {}).get("model", "unknown"),
    }


def clean_marker_for_comparison(text: str) -> str:
    """Minimal cleaning to strip table pipes/structure for fair comparison."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)
    lines = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            continue
        if re.match(r"^[\|\-:\s]+$", s):
            continue
        if "|" in s:
            cells = [c.strip() for c in s.split("|") if c.strip()]
            s = " ".join(cells)
        s = re.sub(r"#{1,6}\s*", "", s)
        s = re.sub(r"[_=]{3,}", " ", s)
        s = re.sub(r"\s{2,}", " ", s).strip()
        if len(s) > 3:
            lines.append(s)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Compare 1a vs 1c OCR quality")
    parser.add_argument("--detailed", action="store_true", help="Show per-file table")
    args = parser.parse_args()

    marker_stems = {
        f.stem for f in MARKER_DIR.glob("*.json") if f.name != "_manifest.json"
    }
    llm_stems = {f.stem for f in LLM_DIR.glob("*.json")}

    both = sorted(marker_stems & llm_stems)
    marker_only = marker_stems - llm_stems
    llm_only = llm_stems - marker_stems

    print("=" * 70)
    print("OCR Quality Comparison: 1a (marker-pdf) vs 1c (LLM vision)")
    print("=" * 70)
    print(f"  Marker (1a) outputs:   {len(marker_stems)}")
    print(f"  LLM (1c) outputs:      {len(llm_stems)}")
    print(f"  Both have:             {len(both)}")
    print(f"  Marker-only:           {len(marker_only)}")
    print(f"  LLM-only:              {len(llm_only)}")
    print()

    # -----------------------------------------------------------------------
    # Detailed comparison on overlapping files
    # -----------------------------------------------------------------------
    results = []
    for stem in both:
        m = load_marker(stem)
        l = load_llm(stem)

        m_clean = clean_marker_for_comparison(m["text"])
        m_alpha = alpha_count(m_clean)
        l_alpha = alpha_count(l["text"])

        m_tokens = tokenize(m_clean)
        l_tokens = tokenize(l["text"])

        # Tokens unique to each source (what one captures that the other misses)
        marker_unique = m_tokens - l_tokens
        llm_unique = l_tokens - m_tokens
        shared = m_tokens & l_tokens

        overlap = len(shared) / max(len(l_tokens), 1)

        results.append({
            "stem": stem,
            "marker_alpha": m_alpha,
            "llm_alpha": l_alpha,
            "marker_quality": m["quality"],
            "marker_unique_words": len(marker_unique),
            "llm_unique_words": len(llm_unique),
            "shared_words": len(shared),
            "overlap": overlap,
            "marker_lines": meaningful_line_count(m_clean),
            "llm_lines": meaningful_line_count(l["text"]),
            "llm_better": l_alpha > m_alpha * 1.2,
            "marker_better": m_alpha > l_alpha * 1.2,
            "sample_marker_unique": sorted(marker_unique)[:5],
            "sample_llm_unique": sorted(llm_unique)[:5],
        })

    # -----------------------------------------------------------------------
    # Aggregate stats
    # -----------------------------------------------------------------------
    n = len(results)
    llm_better_count = sum(1 for r in results if r["llm_better"])
    marker_better_count = sum(1 for r in results if r["marker_better"])
    similar_count = n - llm_better_count - marker_better_count

    avg_marker_alpha = sum(r["marker_alpha"] for r in results) / max(n, 1)
    avg_llm_alpha = sum(r["llm_alpha"] for r in results) / max(n, 1)
    avg_overlap = sum(r["overlap"] for r in results) / max(n, 1)
    avg_marker_unique = sum(r["marker_unique_words"] for r in results) / max(n, 1)
    avg_llm_unique = sum(r["llm_unique_words"] for r in results) / max(n, 1)

    print(f"Comparison on {n} overlapping documents:")
    print(f"  Avg alpha chars — marker: {avg_marker_alpha:.0f}  LLM: {avg_llm_alpha:.0f}")
    print(f"  Avg unique words — marker-only: {avg_marker_unique:.1f}  LLM-only: {avg_llm_unique:.1f}")
    print(f"  Avg token overlap: {avg_overlap:.1%}")
    print()
    print(f"  LLM clearly better (>20% more alpha): {llm_better_count} ({llm_better_count/n:.0%})")
    print(f"  Marker clearly better:                {marker_better_count} ({marker_better_count/n:.0%})")
    print(f"  Similar quality:                       {similar_count} ({similar_count/n:.0%})")

    # By marker quality tier
    print()
    print("  Breakdown by marker quality tier:")
    by_quality = {}
    for r in results:
        q = r["marker_quality"]
        by_quality.setdefault(q, []).append(r)
    for q in ["good", "fair", "uncertain", "poor", "empty", "unknown"]:
        if q not in by_quality:
            continue
        items = by_quality[q]
        lb = sum(1 for r in items if r["llm_better"])
        mb = sum(1 for r in items if r["marker_better"])
        sm = len(items) - lb - mb
        print(f"    {q:<12} ({len(items):>4}): LLM-better={lb}  marker-better={mb}  similar={sm}")

    # -----------------------------------------------------------------------
    # Critical question: does marker add unique searchable content?
    # -----------------------------------------------------------------------
    print()
    print("=" * 70)
    print("KEY QUESTION: Does 1a add content that 1c misses?")
    print("=" * 70)

    # Look at files where marker has significant unique words
    marker_adds_value = [r for r in results if r["marker_unique_words"] > 5]
    llm_adds_value = [r for r in results if r["llm_unique_words"] > 5]

    print(f"  Files where marker adds >5 unique words: {len(marker_adds_value)} ({len(marker_adds_value)/n:.0%})")
    print(f"  Files where LLM adds >5 unique words:    {len(llm_adds_value)} ({len(llm_adds_value)/n:.0%})")

    # Show some examples of marker-unique words
    if marker_adds_value:
        print()
        print("  Examples of words ONLY in marker (not in LLM):")
        for r in sorted(marker_adds_value, key=lambda x: -x["marker_unique_words"])[:10]:
            print(f"    {r['stem']:<20} ({r['marker_unique_words']} unique): {r['sample_marker_unique']}")

    if llm_adds_value:
        print()
        print("  Examples of words ONLY in LLM (not in marker):")
        for r in sorted(llm_adds_value, key=lambda x: -x["llm_unique_words"])[:10]:
            print(f"    {r['stem']:<20} ({r['llm_unique_words']} unique): {r['sample_llm_unique']}")

    # -----------------------------------------------------------------------
    # LLM-only coverage analysis
    # -----------------------------------------------------------------------
    print()
    print("=" * 70)
    print("LLM-ONLY FILES (no marker output yet)")
    print("=" * 70)
    print(f"  {len(llm_only)} PDFs have LLM text but no marker text")

    if llm_only:
        llm_only_stats = []
        for stem in sorted(llm_only):
            l = load_llm(stem)
            la = alpha_count(l["text"])
            llm_only_stats.append(la)

        avg_a = sum(llm_only_stats) / len(llm_only_stats)
        empty = sum(1 for a in llm_only_stats if a < 50)
        sparse = sum(1 for a in llm_only_stats if 50 <= a < 200)
        decent = sum(1 for a in llm_only_stats if 200 <= a < 500)
        rich = sum(1 for a in llm_only_stats if a >= 500)

        print(f"  Avg alpha chars: {avg_a:.0f}")
        print(f"  Empty (<50 alpha):   {empty}")
        print(f"  Sparse (50-200):     {sparse}")
        print(f"  Decent (200-500):    {decent}")
        print(f"  Rich (>500):         {rich}")

    # -----------------------------------------------------------------------
    # Final recommendation
    # -----------------------------------------------------------------------
    print()
    print("=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)

    # Calculate what % of unique marker words are just OCR noise
    total_marker_unique = sum(r["marker_unique_words"] for r in results)
    total_llm_unique = sum(r["llm_unique_words"] for r in results)
    total_shared = sum(r["shared_words"] for r in results)

    print(f"  Total unique to marker: {total_marker_unique}")
    print(f"  Total unique to LLM:    {total_llm_unique}")
    print(f"  Total shared:           {total_shared}")
    print()

    if avg_llm_alpha > avg_marker_alpha * 0.8 and len(llm_stems) > len(marker_stems) * 2:
        print("  -> LLM (1c) has MUCH more coverage ({} vs {} files) and competitive quality.".format(
            len(llm_stems), len(marker_stems)))
        print("  -> The marker pipeline (1a) can likely be STOPPED.")
        print("  -> Use LLM as PRIMARY source; keep existing marker outputs as supplementary.")
        print("  -> Modify 1d to read marker from 01_shotlist_raw/ AND LLM from 01c_llm_ocr/")
    else:
        print("  -> Both pipelines produce valuable content. Consider keeping both.")
        print("  -> The dual-source merge (1d) maximizes search recall.")

    if args.detailed:
        print()
        print("=" * 70)
        print("DETAILED PER-FILE COMPARISON")
        print("=" * 70)
        hdr = f"{'PDF':<24} {'1a-α':>6} {'1c-α':>6} {'shared':>7} {'1a-uniq':>8} {'1c-uniq':>8} {'overlap':>8} {'1a-qual':<10}"
        print(hdr)
        print("-" * len(hdr))
        for r in sorted(results, key=lambda x: x["stem"]):
            print(
                f"{r['stem']:<24} {r['marker_alpha']:>6} {r['llm_alpha']:>6} "
                f"{r['shared_words']:>7} {r['marker_unique_words']:>8} "
                f"{r['llm_unique_words']:>8} {r['overlap']:>7.0%} {r['marker_quality']:<10}"
            )


if __name__ == "__main__":
    main()
