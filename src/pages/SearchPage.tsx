import { useState, useEffect, useCallback, useRef, type JSX } from "react";
import { useSearchParams } from "react-router-dom";
import SearchBar from "../components/SearchBar";
import ReelTable from "../components/ReelTable";
import ReelDetailModal from "../components/ReelDetailModal";
import { searchReels } from "../api/client";
import type { FilmReel } from "../types";

const PAGE_SIZE = 50;

export default function SearchPage(): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();

  const q = searchParams.get("q") || "";
  const prefix = searchParams.get("prefix") || "";
  const hasTransfer = searchParams.get("has_transfer") === "1";

  const [rows, setRows] = useState<FilmReel[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedReel, setSelectedReel] = useState<string | null>(null);

  // Track the next page to fetch (1-based). Reset when filters change.
  const nextPageRef = useRef(1);
  const hasMore = rows.length < total;

  // Reset and fetch first page whenever filters change
  useEffect(() => {
    nextPageRef.current = 1;
    setRows([]);
    setTotal(0);

    let cancelled = false;

    async function fetchFirst() {
      setLoading(true);
      setError(null);
      try {
        const result = await searchReels({
          q: q || undefined,
          prefix: prefix || undefined,
          page: 1,
          limit: PAGE_SIZE,
          has_transfer: hasTransfer || undefined,
        });
        if (!cancelled) {
          setRows(result.rows);
          setTotal(result.total);
          nextPageRef.current = 2;
        }
      } catch (err) {
        if (!cancelled) setError(String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchFirst();
    return () => {
      cancelled = true;
    };
  }, [q, prefix, hasTransfer]);

  // Load next page (called by IntersectionObserver sentinel)
  const loadMore = useCallback(async () => {
    if (loading) return;
    setLoading(true);
    try {
      const page = nextPageRef.current;
      const result = await searchReels({
        q: q || undefined,
        prefix: prefix || undefined,
        page,
        limit: PAGE_SIZE,
        has_transfer: hasTransfer || undefined,
      });
      setRows((prev) => [...prev, ...result.rows]);
      setTotal(result.total);
      nextPageRef.current = page + 1;
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [q, prefix, hasTransfer, loading]);

  // Sentinel ref — triggers loadMore when scrolled into view
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const node = sentinelRef.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          loadMore();
        }
      },
      { rootMargin: "200px" }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [loadMore]);

  function handleSearch(newQ: string, newPrefix: string, newHasTransfer: boolean) {
    const params: Record<string, string> = {};
    if (newQ) params.q = newQ;
    if (newPrefix) params.prefix = newPrefix;
    if (newHasTransfer) params.has_transfer = "1";
    setSearchParams(params);
  }

  return (
    <div className="search-page">
      <SearchBar
        initialQuery={q}
        initialPrefix={prefix}
        initialHasTransfer={hasTransfer}
        onSearch={handleSearch}
      />

      {error && <div className="error-msg">Error: {error}</div>}

      <ReelTable rows={rows} total={total} onSelectReel={setSelectedReel} />

      {loading && <div className="loading">Loading…</div>}

      {hasMore && !loading && <div ref={sentinelRef} className="scroll-sentinel" />}

      {selectedReel && (
        <ReelDetailModal identifier={selectedReel} onClose={() => setSelectedReel(null)} />
      )}
    </div>
  );
}
