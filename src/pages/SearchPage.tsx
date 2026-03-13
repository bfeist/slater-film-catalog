import { useState, useEffect, useRef, type JSX } from "react";
import { useSearchParams } from "react-router-dom";
import SearchBar from "../components/SearchBar";
import ReelTable from "../components/ReelTable";
import ReelDetailModal from "../components/ReelDetailModal";
import { searchReels } from "../api/client";
import { QUALITY_BUCKETS } from "../utils/qualityBuckets";
import type { FilmReel } from "../types";

const PAGE_SIZE = 50;

function PaginationBar({
  currentPage,
  totalPages,
  onPageChange,
}: {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}): JSX.Element | null {
  if (totalPages <= 1) return null;

  const delta = 2;
  const start = Math.max(1, currentPage - delta);
  const end = Math.min(totalPages, currentPage + delta);
  const pageNums: number[] = [];
  for (let p = start; p <= end; p++) pageNums.push(p);

  return (
    <div className="pagination-bar" role="navigation" aria-label="Pagination">
      <button
        className="pagination-btn"
        disabled={currentPage === 1}
        onClick={() => onPageChange(currentPage - 1)}
      >
        ◄ Prev
      </button>

      {start > 1 && (
        <>
          <button className="pagination-btn" onClick={() => onPageChange(1)}>
            1
          </button>
          {start > 2 && <span className="pagination-ellipsis">…</span>}
        </>
      )}

      {pageNums.map((p) => (
        <button
          key={p}
          className={`pagination-btn${p === currentPage ? " active" : ""}`}
          onClick={() => onPageChange(p)}
          aria-current={p === currentPage ? "page" : undefined}
        >
          {p}
        </button>
      ))}

      {end < totalPages && (
        <>
          {end < totalPages - 1 && <span className="pagination-ellipsis">…</span>}
          <button className="pagination-btn" onClick={() => onPageChange(totalPages)}>
            {totalPages}
          </button>
        </>
      )}

      <button
        className="pagination-btn"
        disabled={currentPage === totalPages}
        onClick={() => onPageChange(currentPage + 1)}
      >
        Next ►
      </button>
    </div>
  );
}

export default function SearchPage(): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();

  const q = searchParams.get("q") || "";
  const hasTransfer = searchParams.get("has_transfer") === "1";
  const qualityBucket = searchParams.get("quality_bucket") || "";

  const [rows, setRows] = useState<FilmReel[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedReel, setSelectedReel] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);

  const toolbarRef = useRef<HTMLDivElement>(null);
  const tableContainerRef = useRef<HTMLDivElement>(null);

  // Measure toolbar height and expose it as a CSS variable so the
  // table container height (and sticky th) track it automatically.
  useEffect(() => {
    const el = toolbarRef.current;
    if (!el) return;
    const obs = new ResizeObserver(() => {
      document.documentElement.style.setProperty("--search-toolbar-height", `${el.offsetHeight}px`);
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const effectiveHasTransfer = !revealed ? true : hasTransfer;
  const totalPages = total > 0 ? Math.ceil(total / PAGE_SIZE) : 0;

  // Fetch whenever filters or page changes
  useEffect(() => {
    let cancelled = false;

    async function fetchPage() {
      setLoading(true);
      setError(null);
      try {
        const result = await searchReels({
          q: q || undefined,
          page: currentPage,
          limit: PAGE_SIZE,
          has_transfer: effectiveHasTransfer || undefined,
          quality_bucket: qualityBucket || undefined,
        });
        if (!cancelled) {
          setRows(result.rows);
          setTotal(result.total);
          setRevealed(result.revealed ?? true);
        }
      } catch (err) {
        if (!cancelled) setError(String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchPage();
    return () => {
      cancelled = true;
    };
  }, [q, effectiveHasTransfer, qualityBucket, currentPage]);

  function handleSearch(newQ: string, newHasTransfer: boolean) {
    const params: Record<string, string> = {};
    if (newQ) params.q = newQ;
    if (newHasTransfer) params.has_transfer = "1";
    if (qualityBucket) params.quality_bucket = qualityBucket;
    setCurrentPage(1);
    setSearchParams(params);
  }

  function handleQualityFilter(bucket: string) {
    const params: Record<string, string> = {};
    if (q) params.q = q;
    if (hasTransfer) params.has_transfer = "1";
    if (bucket) params.quality_bucket = bucket;
    setCurrentPage(1);
    setSearchParams(params);
  }

  const start = total === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const end = Math.min(currentPage * PAGE_SIZE, total);

  return (
    <div className="search-page">
      {/* ---- Sticky toolbar: search bar + quality filters + result count ---- */}
      <div className="search-toolbar-sticky" ref={toolbarRef}>
        <SearchBar
          initialQuery={q}
          initialHasTransfer={effectiveHasTransfer}
          onSearch={handleSearch}
          revealed={revealed}
        />

        <div className="quality-filter-bar">
          <span className="quality-filter-label">Quality:</span>
          <button
            type="button"
            className={`quality-filter-btn${!qualityBucket ? " active" : ""}`}
            onClick={() => handleQualityFilter("")}
          >
            All
          </button>
          {QUALITY_BUCKETS.map((b) => (
            <button
              key={b.key}
              type="button"
              className={[
                "quality-filter-btn",
                `quality-bucket-${b.key}`,
                qualityBucket === b.key ? "active" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={() => handleQualityFilter(qualityBucket === b.key ? "" : b.key)}
            >
              {b.label}
            </button>
          ))}
        </div>

        <div className="toolbar-info">
          {loading
            ? "Loading…"
            : total > 0
              ? `Showing ${start.toLocaleString()}–${end.toLocaleString()} of ${total.toLocaleString()} results`
              : "No results"}
        </div>
      </div>

      {error && <div className="error-msg">Error: {error}</div>}

      <div className="reel-table-container" ref={tableContainerRef}>
        <ReelTable rows={rows} onSelectReel={setSelectedReel} revealed={revealed} />
      </div>

      <PaginationBar
        currentPage={currentPage}
        totalPages={totalPages}
        onPageChange={(p) => {
          setCurrentPage(p);
          tableContainerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
        }}
      />

      {selectedReel && (
        <ReelDetailModal identifier={selectedReel} onClose={() => setSelectedReel(null)} />
      )}
    </div>
  );
}
