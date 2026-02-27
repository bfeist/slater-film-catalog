import { useState, useEffect, useCallback, type JSX } from "react";
import { Link } from "react-router-dom";
import { fetchReelDetail } from "../api/client";
import type { ReelDetailResponse, FfprobeMetadata } from "../types";
import TransferList from "./TransferList";
import FileInfoCard from "./FileInfoCard";
import DiscoveryEntries from "./DiscoveryEntries";
import VideoPlayer from "./VideoPlayer";
import ShotlistPdfViewer from "./ShotlistPdfViewer";

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
  const [playingFile, setPlayingFile] = useState<{
    id: number;
    name: string;
    duration: number | null;
  } | null>(null);
  const [showShotlist, setShowShotlist] = useState(false);

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
    const { reel, transfers, fileMatches, ffprobeData, discoveryEntries } = data;

    const probeByFile = new Map<number, FfprobeMetadata>();
    for (const p of ffprobeData) {
      probeByFile.set(p.file_id, p);
    }

    content = (
      <>
        {/* ---- Reel header ---- */}
        <section className="reel-header-section">
          <h2>{reel.identifier}</h2>
          {reel.title && <p className="reel-title">{reel.title}</p>}
          {reel.orig_title && reel.orig_title !== reel.title && (
            <p className="muted">Original title: {reel.orig_title}</p>
          )}

          <dl className="reel-meta-dl">
            <dt>Prefix</dt>
            <dd>{reel.id_prefix}</dd>

            <dt>Date</dt>
            <dd>{reel.date || "—"}</dd>

            {reel.mission && (
              <>
                <dt>Mission</dt>
                <dd>{reel.mission}</dd>
              </>
            )}

            <dt>Feet / Minutes</dt>
            <dd>
              {reel.feet || "—"} / {reel.minutes || "—"}
            </dd>

            <dt>Audio</dt>
            <dd>{reel.audio || "—"}</dd>

            <dt>On disk</dt>
            <dd>{reel.has_transfer_on_disk ? "Yes" : "No"}</dd>

            <dt>Shot list PDF</dt>
            <dd>
              {reel.has_shotlist_pdf ? (
                <>
                  Yes{" "}
                  <button className="shotlist-pdf-btn" onClick={() => setShowShotlist(true)}>
                    View PDF
                  </button>
                </>
              ) : (
                "No"
              )}
            </dd>
          </dl>

          {reel.description && (
            <div className="reel-description">
              <h3>Description</h3>
              <p>{reel.description}</p>
            </div>
          )}
        </section>

        {/* ---- Transfers ---- */}
        <section>
          <TransferList transfers={transfers} />
        </section>

        {/* ---- Files on disk ---- */}
        <section className="files-section">
          <h3>Files on Disk ({fileMatches.length})</h3>
          {fileMatches.length === 0 ? (
            <p className="muted">No files matched on disk.</p>
          ) : (
            fileMatches.map((fm) => (
              <FileInfoCard
                key={fm.file_id}
                file={fm}
                probe={probeByFile.get(fm.file_id)}
                onPlay={(id) =>
                  setPlayingFile({
                    id,
                    name: fm.filename,
                    duration: probeByFile.get(fm.file_id)?.duration_secs ?? null,
                  })
                }
              />
            ))
          )}
        </section>

        {/* ---- Discovery shotlist ---- */}
        <section>
          <DiscoveryEntries entries={discoveryEntries} />
        </section>

        {/* ---- Future sections ---- */}
        <section className="future-stub">
          <h3>Scene Detection</h3>
          <p className="muted">Coming soon — will show detected scene boundaries for this reel.</p>
        </section>

        <section className="future-stub">
          <h3>Shot List References</h3>
          <p className="muted">
            Coming soon — will link to specific shots from parsed shot list PDFs.
          </p>
        </section>

        {/* ---- Video player overlay ---- */}
        {playingFile && (
          <VideoPlayer
            fileId={playingFile.id}
            filename={playingFile.name}
            durationSecs={playingFile.duration}
            onClose={() => setPlayingFile(null)}
          />
        )}

        {/* ---- Shotlist PDF viewer overlay ---- */}
        {showShotlist && reel.shotlist_pdfs && (
          <ShotlistPdfViewer
            identifier={reel.identifier}
            pdfs={JSON.parse(reel.shotlist_pdfs) as string[]}
            onClose={() => setShowShotlist(false)}
          />
        )}
      </>
    );
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
