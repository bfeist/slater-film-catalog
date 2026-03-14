import { useState, useEffect, useCallback, type JSX } from "react";
import { Link } from "react-router-dom";
import { fetchReelDetail } from "../api/client";
import type { ReelDetailResponse } from "../types";
import ReelDetailContent from "./ReelDetailContent";

interface ReelDetailModalProps {
  identifier: string;
  onClose: () => void;
}

export default function ReelDetailModal({
  identifier,
  onClose,
}: ReelDetailModalProps): JSX.Element {
  const [data, setData] = useState<ReelDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetchReelDetail(identifier)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [identifier]);

  // Close on Escape key
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    // Prevent background scrolling
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [handleKeyDown]);

  // Close when clicking backdrop
  function handleBackdropClick(e: React.MouseEvent) {
    if (e.target === e.currentTarget) onClose();
  }

  let content: JSX.Element;

  if (loading) {
    content = <div className="loading">Loading…</div>;
  } else if (error) {
    content = <div className="error-msg">Error: {error}</div>;
  } else if (!data) {
    content = <div className="error-msg">No data</div>;
  } else {
    content = <ReelDetailContent data={data} />;
  }

  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
    <div className="reel-modal-overlay" onClick={handleBackdropClick}>
      <div className="reel-modal">
        <div className="reel-modal-header">
          <span className="reel-modal-title">
            {identifier}{" "}
            <Link
              to={`/reel/${encodeURIComponent(identifier)}`}
              className="permalink-link"
              title="Open full page"
              onClick={onClose}
            >
              🔗
            </Link>
          </span>
          <button className="reel-modal-close" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="reel-modal-body">{content}</div>
      </div>
    </div>
  );
}
