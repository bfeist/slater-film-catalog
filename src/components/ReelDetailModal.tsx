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
    const {
      reel,
      transfers,
      fileMatches,
      ffprobeData,
      discoveryEntries,
      naraCitations,
      externalRefs,
      revealed,
    } = data;

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
            {revealed && (
              <>
                <dt>Prefix</dt>
                <dd>{reel.id_prefix}</dd>
              </>
            )}

            <dt>Date</dt>
            <dd>{reel.date || "—"}</dd>

            {reel.film_gauge && (
              <>
                <dt>Film Gauge</dt>
                <dd>{reel.film_gauge}</dd>
              </>
            )}

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

            {(reel.nara_catalog_url ?? reel.nara_id) && (
              <>
                <dt>NARA</dt>
                <dd>
                  {reel.nara_catalog_url ? (
                    <a href={reel.nara_catalog_url} target="_blank" rel="noopener noreferrer">
                      {reel.nara_id ?? "View catalog →"}
                    </a>
                  ) : (
                    reel.nara_id
                  )}
                </dd>
              </>
            )}

            {reel.nara_roll_number && (
              <>
                <dt>NARA Roll #</dt>
                <dd>{reel.nara_roll_number}</dd>
              </>
            )}

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

          {reel.notes && (
            <div className="reel-notes">
              <h3>Notes</h3>
              <p>{reel.notes}</p>
            </div>
          )}
        </section>

        {/* ---- Transfers ---- */}
        <section>
          <TransferList transfers={transfers} revealed={revealed} />
        </section>

        {/* ---- Files on disk ---- */}
        <section className="files-section">
          <h3>Files on Disk ({fileMatches.length})</h3>
          {fileMatches.length === 0 ? (
            <p className="muted">No files matched on disk.</p>
          ) : (
            fileMatches.map((fm, i) => {
              const probe = probeByFile.get(fm.file_id);
              const displayFilename = revealed
                ? undefined
                : `${probe?.quality_label?.toLowerCase().replace(/\s+/g, "-") ?? "file"}-${i + 1}`;
              return (
                <FileInfoCard
                  key={fm.file_id}
                  file={fm}
                  probe={probe}
                  showPath={revealed}
                  displayFilename={displayFilename}
                  onPlay={(id) =>
                    setPlayingFile({
                      id,
                      name: displayFilename ?? fm.filename,
                      duration: probe?.duration_secs ?? null,
                    })
                  }
                />
              );
            })
          )}
        </section>

        {/* ---- Discovery shotlist ---- */}
        <section>
          <DiscoveryEntries entries={discoveryEntries} revealed={revealed} />
        </section>

        {/* ---- NARA Citations ---- */}
        {naraCitations.length > 0 && (
          <section className="nara-citations-section">
            <h3>NARA Citations ({naraCitations.length})</h3>
            <ul className="nara-citation-list">
              {naraCitations.map((c) => (
                <li key={c.id}>
                  <code>{c.citation}</code>
                  {c.citation_type && c.citation_type !== "other" && (
                    <span className="citation-type-badge">
                      {c.citation_type.replace(/_/g, " ")}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* ---- External Online Sources ---- */}
        {externalRefs.length > 0 && (
          <section className="ext-refs-section">
            <h3>External Online Sources ({externalRefs.length})</h3>
            <ul className="ext-ref-list">
              {externalRefs.map((ref) => (
                <li key={ref.id}>
                  <span className="ext-ref-type">
                    {(ref.ref_type ?? "file").replace(/_/g, " ")}
                  </span>
                  {" — "}
                  <a href={ref.url} target="_blank" rel="noopener noreferrer">
                    {ref.filename ?? ref.url}
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* ---- Future sections ---- */}
        <section className="future-stub">
          <h3>Scene Detection</h3>
          <p className="muted">Coming soon — will show detected scene boundaries for this reel.</p>
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
