import type { JSX } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faHardDrive, faFilePdf } from "@fortawesome/free-solid-svg-icons";
import type { FilmReel } from "../types";

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
              <td className="reel-title-cell" title={r.title ?? ""}>
                {r.title ? (r.title.length > 80 ? r.title.slice(0, 80) + "…" : r.title) : "—"}
              </td>
              <td>{r.date || "—"}</td>
              <td>{r.has_transfer_on_disk ? <FontAwesomeIcon icon={faHardDrive} /> : ""}</td>
              <td>{r.has_shotlist_pdf ? <FontAwesomeIcon icon={faFilePdf} /> : ""}</td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={revealed ? 6 : 5} className="reel-table-empty">
                No results
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
