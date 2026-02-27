import { useState, useEffect, useCallback, type JSX } from "react";
import { shotlistPdfUrl } from "../api/client";

interface ShotlistPdfViewerProps {
  identifier: string;
  pdfs: string[];
  onClose: () => void;
}

/**
 * Modal overlay that renders shotlist PDFs using the browser's native PDF viewer.
 * If multiple PDFs exist for a reel (e.g. date-suffixed variants), shows a tab bar.
 */
export default function ShotlistPdfViewer({
  identifier,
  pdfs,
  onClose,
}: ShotlistPdfViewerProps): JSX.Element {
  const [activePdf, setActivePdf] = useState<string>(pdfs[0] ?? "");

  // Close on Escape key
  const onKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose]
  );

  useEffect(() => {
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onKeyDown]);

  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
    <div className="pdf-viewer-overlay" onClick={onClose}>
      {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions */}
      <div className="pdf-viewer-container" onClick={(e) => e.stopPropagation()}>
        <div className="pdf-viewer-header">
          <span className="pdf-viewer-title">Shot List — {identifier}</span>
          <button className="pdf-viewer-close" onClick={onClose}>
            ✕
          </button>
        </div>

        {/* Tab bar for multiple PDFs */}
        {pdfs.length > 1 && (
          <div className="pdf-viewer-tabs">
            {pdfs.map((filename) => (
              <button
                key={filename}
                className={`pdf-viewer-tab${activePdf === filename ? " pdf-viewer-tab-active" : ""}`}
                onClick={() => setActivePdf(filename)}
              >
                {filename.replace(".pdf", "")}
              </button>
            ))}
          </div>
        )}

        <div className="pdf-viewer-body">
          {pdfs.length === 0 && (
            <div className="muted" style={{ padding: "2rem", textAlign: "center" }}>
              No shotlist PDFs found for {identifier}.
            </div>
          )}
          {activePdf && (
            <iframe
              className="pdf-viewer-iframe"
              src={shotlistPdfUrl(activePdf)}
              title={`Shotlist PDF: ${activePdf}`}
            />
          )}
        </div>
      </div>
    </div>
  );
}
