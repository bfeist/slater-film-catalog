// ---------------------------------------------------------------------------
// Shared reel detail body — used by both ReelDetailModal and ReelPage
// ---------------------------------------------------------------------------

import { useState, type JSX } from "react";
import type { ReelDetailResponse, FfprobeMetadata } from "../types";
import { computeQualityLabel } from "../utils/qualityBuckets";
import TransferList from "./TransferList";
import FileInfoCard from "./FileInfoCard";
import DiscoveryEntries from "./DiscoveryEntries";
import VideoPlayer from "./VideoPlayer";
import ShotlistPdfViewer from "./ShotlistPdfViewer";
import ShotlistTextViewer from "./ShotlistTextViewer";
import styles from "./ReelDetailContent.module.css";

interface ReelDetailContentProps {
  data: ReelDetailResponse;
}

export default function ReelDetailContent({ data }: ReelDetailContentProps): JSX.Element {
  const [playingFile, setPlayingFile] = useState<{
    id: number;
    name: string;
    duration: number | null;
  } | null>(null);
  const [showShotlistPdf, setShowShotlistPdf] = useState(false);
  const [showShotlistText, setShowShotlistText] = useState(false);

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

  return (
    <>
      {/* ---- Reel header ---- */}
      <section className={styles.headerSection}>
        <h2>{reel.identifier}</h2>
        {(() => {
          const displayTitle = revealed ? reel.title : (reel.alternate_title ?? reel.title);
          return displayTitle ? <p className={styles.reelTitle}>{displayTitle}</p> : null;
        })()}
        {revealed && reel.orig_title && reel.orig_title !== reel.title && (
          <p className="muted">Original title: {reel.orig_title}</p>
        )}

        <dl className={styles.metaDl}>
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
                {revealed && (
                  <button
                    className={styles.shotlistPdfBtn}
                    onClick={() => setShowShotlistPdf(true)}
                  >
                    View PDF
                  </button>
                )}{" "}
                <button className={styles.shotlistPdfBtn} onClick={() => setShowShotlistText(true)}>
                  View Shot List
                </button>
              </>
            ) : (
              "No"
            )}
          </dd>
        </dl>

        {reel.description && (
          <div className={styles.description}>
            <h3>Description</h3>
            <p>{reel.description}</p>
          </div>
        )}

        {reel.notes && (
          <div className={styles.notes}>
            <h3>Notes</h3>
            <p>{reel.notes}</p>
          </div>
        )}
      </section>

      {/* ---- Transfers ---- */}
      <section className={styles.section}>
        <TransferList transfers={transfers} revealed={revealed} />
      </section>

      {/* ---- Files on disk ---- */}
      <section className={styles.filesSection}>
        <h3>Files on Disk ({fileMatches.length})</h3>
        {fileMatches.length === 0 ? (
          <p className="muted">No files matched on disk.</p>
        ) : (
          fileMatches.map((fm, i) => {
            const probe = probeByFile.get(fm.file_id);
            const displayFilename = revealed
              ? undefined
              : `${computeQualityLabel(probe?.video_codec, probe?.video_width, probe?.video_height)
                  .toLowerCase()
                  .replace(/[^a-z0-9]+/g, "-")
                  .replace(/^-|-$/g, "")}-${i + 1}`;
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
      <section className={styles.section}>
        <DiscoveryEntries entries={discoveryEntries} revealed={revealed} />
      </section>

      {/* ---- NARA Citations (revealed users only) ---- */}
      {revealed && naraCitations.length > 0 && (
        <section className={styles.naraCitationsSection}>
          <h3>NARA Citations ({naraCitations.length})</h3>
          <ul className={styles.citationList}>
            {naraCitations.map((c) => (
              <li key={c.id}>
                <code>{c.citation}</code>
                {c.citation_type && c.citation_type !== "other" && (
                  <span className={styles.citationTypeBadge}>
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
        <section className={styles.extRefsSection}>
          <h3>External Online Sources ({externalRefs.length})</h3>
          <ul className={styles.extRefList}>
            {externalRefs.map((ref) => (
              <li key={ref.id}>
                <span className={styles.extRefType}>
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
      <section className={styles.futureStub}>
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

      {/* ---- Shotlist PDF viewer overlay (revealed users) ---- */}
      {showShotlistPdf && revealed && reel.shotlist_pdfs && (
        <ShotlistPdfViewer
          identifier={reel.identifier}
          pdfs={JSON.parse(reel.shotlist_pdfs) as string[]}
          onClose={() => setShowShotlistPdf(false)}
        />
      )}

      {/* ---- Shotlist text viewer overlay ---- */}
      {showShotlistText && (
        <ShotlistTextViewer
          identifier={reel.identifier}
          onClose={() => setShowShotlistText(false)}
        />
      )}
    </>
  );
}
