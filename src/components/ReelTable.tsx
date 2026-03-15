import type { JSX } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faHardDrive, faFilePdf } from "@fortawesome/free-solid-svg-icons";
import clsx from "clsx";
import type { FilmReel } from "../types";
import { computeQualityLabel, getBucketKey } from "../utils/qualityBuckets";
import styles from "./ReelTable.module.css";

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
  if (!codec) return <span className={clsx(styles.qualityBadge, styles.qualityBadgeNone)}>—</span>;
  const bucketKey = getBucketKey(codec, width);
  return (
    <span
      className={clsx(styles.qualityBadge, bucketKey && `quality-bucket-${bucketKey}`)}
      title={`${codec} ${width ?? "?"}\xd7${height ?? "?"}`}
    >
      {label}
    </span>
  );
}

interface ReelTableProps {
  rows: FilmReel[];
  onSelectReel: (identifier: string) => void;
  revealed: boolean;
}

export default function ReelTable({ rows, onSelectReel, revealed }: ReelTableProps): JSX.Element {
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          {revealed && <th>Identifier</th>}
          <th>Catalog ID</th>
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
            className={styles.clickableRow}
          >
            {revealed && (
              <td>
                <button className={styles.identifierBtn} type="button">
                  {r.identifier}
                </button>
              </td>
            )}
            <td>{r.slater_number}</td>
            <td className={styles.titleCell}>
              {revealed ? (
                <span className={styles.titleRevealed}>
                  <span title={r.title ?? ""}>
                    {r.title ? (r.title.length > 80 ? r.title.slice(0, 80) + "…" : r.title) : "—"}
                  </span>
                  {r.alternate_title && (
                    <span
                      className={styles.altBadge}
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
            <td className={styles.iconCell}>
              {r.has_transfer_on_disk ? <FontAwesomeIcon icon={faHardDrive} /> : ""}
            </td>
            <td className={styles.iconCell}>
              {r.has_shotlist_pdf ? <FontAwesomeIcon icon={faFilePdf} /> : ""}
            </td>
          </tr>
        ))}
        {rows.length === 0 && (
          <tr>
            <td colSpan={revealed ? 7 : 6} className={styles.empty}>
              No results
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}
