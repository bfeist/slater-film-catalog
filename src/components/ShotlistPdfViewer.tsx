import { useState, useEffect, useRef, useCallback, type JSX } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import * as Dialog from "@radix-ui/react-dialog";
import * as VisuallyHidden from "@radix-ui/react-visually-hidden";
import { requestPdfSession, ApiError } from "../api/client";
import clsx from "clsx";
import styles from "./ShotlistPdfViewer.module.css";

// Configure pdfjs worker — Vite resolves this URL at build time.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString();

/** Read the session auth token from session storage (returns empty string when absent). */
function getAuthToken(): string {
  try {
    return sessionStorage.getItem("authToken") ?? "";
  } catch {
    return "";
  }
}

type PdfStage = "requesting_session" | "loading" | "ready" | "error";

const PDF_STAGE_LABELS: Record<PdfStage, string> = {
  requesting_session: "Requesting PDF session…",
  loading: "Loading PDF…",
  ready: "",
  error: "",
};

interface PdfError {
  title: string;
  detail: string;
}

function describeApiError(err: unknown): PdfError {
  if (err instanceof ApiError) {
    if (err.status === 503) {
      const reasonLabel: Record<string, string> = {
        timeout: "Home gateway did not respond in time.",
        unreachable: "Cannot reach the home gateway from the catalog server.",
        http_error: `Home gateway returned an error${
          err.gatewayStatus ? ` (HTTP ${err.gatewayStatus})` : ""
        }.`,
        unknown: "Home gateway is unavailable.",
      };
      const headline = err.reason
        ? (reasonLabel[err.reason] ?? reasonLabel.unknown)
        : reasonLabel.unknown;
      return {
        title: "PDFs temporarily unavailable",
        detail: err.detail ? `${headline} ${err.detail}` : headline,
      };
    }
    if (err.status === 404) {
      return { title: "PDF not found", detail: err.detail ?? "The requested file is missing." };
    }
    if (err.status === 401 || err.status === 403) {
      return { title: "Not authorized", detail: err.detail ?? "Sign in required to view PDFs." };
    }
    return { title: `Server error (${err.status})`, detail: err.detail ?? err.message };
  }
  const msg = err instanceof Error ? err.message : String(err);
  return { title: "Could not load PDF", detail: msg };
}

interface ShotlistPdfViewerProps {
  identifier: string;
  pdfs: string[];
  onClose: () => void;
}

/**
 * Modal overlay that renders shotlist PDFs via react-pdf (canvas-based).
 * No browser PDF viewer chrome means no built-in download button.
 * Tab labels are shown with real filenames for authenticated users.
 */
export default function ShotlistPdfViewer({
  identifier,
  pdfs,
  onClose,
}: ShotlistPdfViewerProps): JSX.Element {
  const [activePdf, setActivePdf] = useState<string>(pdfs[0] ?? "");
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState<number>(1);
  const bodyRef = useRef<HTMLDivElement>(null);
  const [pageWidth, setPageWidth] = useState<number>(800);

  const authToken = getAuthToken();
  const isAuthed = authToken !== "";

  // Measure the body container on mount so the Page fills the available width.
  useEffect(() => {
    if (bodyRef.current) {
      setPageWidth(Math.max(200, bodyRef.current.clientWidth - 32));
    }
  }, []);

  const tabLabel = (filename: string, index: number): string =>
    isAuthed ? filename.replace(".pdf", "") : `Document ${index + 1}`;

  // Resolve a session URL each time the active PDF changes. In monolithic
  // mode this is a same-origin /api/shotlist-pdf/... URL; in split mode it
  // is an absolute home-gateway URL.
  const [pdfFile, setPdfFile] = useState<{
    url: string;
    httpHeaders: Record<string, string>;
  } | null>(null);
  const [pdfStage, setPdfStage] = useState<PdfStage>("requesting_session");
  const [pdfError, setPdfError] = useState<PdfError | null>(null);

  // retryKey increments to force re-requesting the same activePdf.
  const [retryKey, setRetryKey] = useState(0);
  const retry = useCallback(() => setRetryKey((k) => k + 1), []);

  useEffect(() => {
    if (!activePdf) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPdfFile(null);
      return;
    }
    let cancelled = false;
    setPdfFile(null);
    setPdfStage("requesting_session");
    setPdfError(null);
    requestPdfSession(activePdf)
      .then((session) => {
        if (cancelled) return;
        setPdfFile({
          url: session.pdfUrl,
          // Auth header only useful for same-origin (gateway URLs are token-bearing).
          httpHeaders:
            session.mode === "monolithic" && isAuthed
              ? { Authorization: `Bearer ${authToken}` }
              : {},
        });
        setPdfStage("loading");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setPdfStage("error");
        setPdfError(describeApiError(err));
      });
    return () => {
      cancelled = true;
    };
  }, [activePdf, isAuthed, authToken, retryKey]);

  return (
    <Dialog.Root open onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className={styles.overlay} />
        <Dialog.Content className={styles.container} aria-describedby={undefined}>
          <VisuallyHidden.Root>
            <Dialog.Description>Shot list PDF viewer for {identifier}</Dialog.Description>
          </VisuallyHidden.Root>
          <div className={styles.header}>
            <Dialog.Title className={styles.title}>Shot List — {identifier}</Dialog.Title>
            <Dialog.Close asChild>
              <button className={styles.closeBtn}>✕</button>
            </Dialog.Close>
          </div>

          {/* Tab bar — labels are generic for unauthenticated users */}
          {pdfs.length > 1 && (
            <div className={styles.tabs}>
              {pdfs.map((filename, i) => (
                <button
                  key={filename}
                  className={clsx(styles.tab, activePdf === filename && styles.tabActive)}
                  onClick={() => {
                    setActivePdf(filename);
                    setPageNumber(1);
                  }}
                >
                  {tabLabel(filename, i)}
                </button>
              ))}
            </div>
          )}

          <div className={styles.body} ref={bodyRef}>
            {pdfs.length === 0 && (
              <div className="muted" style={{ padding: "2rem", textAlign: "center" }}>
                No shotlist PDFs found for {identifier}.
              </div>
            )}
            {(pdfStage === "requesting_session" || pdfStage === "loading") && (
              <div className={styles.pdfStatus} role="status" aria-live="polite">
                <div className={styles.pdfSpinner} aria-hidden="true" />
                <div className={styles.pdfStatusText}>{PDF_STAGE_LABELS[pdfStage]}</div>
              </div>
            )}
            {pdfStage === "error" && pdfError && (
              <div className={styles.pdfStatus} role="alert">
                <div className={styles.pdfErrorTitle}>{pdfError.title}</div>
                <div className={styles.pdfErrorDetail}>{pdfError.detail}</div>
                <button className={styles.pdfRetryBtn} onClick={retry}>
                  Retry
                </button>
              </div>
            )}
            {pdfStage !== "error" && pdfFile && (
              <Document
                file={pdfFile}
                className={styles.document}
                onLoadSuccess={({ numPages: n }) => {
                  setNumPages(n);
                  setPageNumber(1);
                  setPdfStage("ready");
                }}
                onLoadError={(err) => {
                  setPdfStage("error");
                  setPdfError({
                    title: "Failed to render PDF",
                    detail: err.message || "pdf.js could not parse the document.",
                  });
                }}
              >
                <Page
                  pageNumber={pageNumber}
                  width={pageWidth}
                  renderAnnotationLayer
                  renderTextLayer
                />
              </Document>
            )}
          </div>

          {numPages > 1 && (
            <div className={clsx(styles.tabs, styles.pageTabs)}>
              <span className={styles.pageLabel}>Page</span>
              {Array.from({ length: numPages }, (_, i) => i + 1).map((n) => (
                <button
                  key={n}
                  className={clsx(styles.tab, pageNumber === n && styles.tabActive)}
                  onClick={() => setPageNumber(n)}
                >
                  {n}
                </button>
              ))}
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
