import type { JSX } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faHardDrive, faFilePdf } from "@fortawesome/free-solid-svg-icons";
import type { FilmReel } from "../types";
import { computeQualityLabel, getBucketKey } from "../utils/qualityBuckets";

function QualityBadge({
  codec,
  width,
  height,
}: {
  codec: string | null | undefined;
  width: number | null | undefined;
  height: number | null | undefined;
}): JSX.Element {
  const label = computeQualityLabel(codec, width, height);
  if (!codec) return <span className="quality-badge quality-badge-none">—</span>;
  const bucketKey = getBucketKey(codec, width);
  return (
    <span
      className={`quality-badge${bucketKey ? ` quality-bucket-${bucketKey}` : ""}`}
      title={`${codec} ${width ?? "?"}\xd7${height ?? "?"}`}
    >
      {label}
    </span>
  );
}

interface ReelTableProps {
  rows: FilmReel[];
  total: number;
  onSelectReel: (identifier: string) => void;
  revealed: boolean;
}

export default function ReelTable({
  rows,
  total,
  onSelectReel,
  revealed,
}: ReelTableProps): JSX.Element {
  return (
    <div className="reel-table-container">
      <div className="reel-table-info">
        Showing {rows.length.toLocaleString()} of {total.toLocaleString()} results
      </div>

      <table className="reel-table">
        <thead>
          <tr>
            {revealed && <th>Identifier</th>}
            <th>Slater #</th>
            <th>Title</th>
            <th>Date</th>
            <th>Quality</th>
            <th>Disk</th>
            <th>PDF</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.identifier}
              onClick={() => onSelectReel(r.identifier)}
              className="reel-table-clickable"
            >
              {revealed && (
                <td>
                  <button className="reel-link-btn" type="button">
                    {r.identifier}
                  </button>
                </td>
              )}
              <td>{r.slater_number}</td>
              <td className="reel-title-cell">
                {revealed ? (
                  <span className="reel-title-revealed">
                    <span title={r.title ?? ""}>
                      {r.title
                        ? r.title.length > 80
                          ? r.title.slice(0, 80) + "…"
                          : r.title
                        : "—"}
                    </span>
                    {r.alternate_title && (
                      <span
                        className="reel-alt-title-btn"
                        title={`Alt: ${r.alternate_title}`}
                        aria-label="Alternate title"
                      >
                        alt
                      </span>
                    )}
                  </span>
                ) : (
                  <span title={r.alternate_title ?? r.title ?? ""}>
                    {(() => {
                      const t = r.alternate_title ?? r.title;
                      return t ? (t.length > 80 ? t.slice(0, 80) + "…" : t) : "—";
                    })()}
                  </span>
                )}
              </td>
              <td>{r.date || "—"}</td>
              <td>
                <QualityBadge
                  codec={r.best_quality_codec}
                  width={r.best_quality_width}
                  height={r.best_quality_height}
                />
              </td>
              <td>{r.has_transfer_on_disk ? <FontAwesomeIcon icon={faHardDrive} /> : ""}</td>
              <td>{r.has_shotlist_pdf ? <FontAwesomeIcon icon={faFilePdf} /> : ""}</td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={revealed ? 7 : 6} className="reel-table-empty">
                No results
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
