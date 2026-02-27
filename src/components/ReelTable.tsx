import type { JSX } from "react";
import type { FilmReel } from "../types";

interface ReelTableProps {
  rows: FilmReel[];
  total: number;
  onSelectReel: (identifier: string) => void;
}

export default function ReelTable({ rows, total, onSelectReel }: ReelTableProps): JSX.Element {
  return (
    <div className="reel-table-container">
      <div className="reel-table-info">
        Showing {rows.length.toLocaleString()} of {total.toLocaleString()} results
      </div>

      <table className="reel-table">
        <thead>
          <tr>
            <th>Identifier</th>
            <th>Prefix</th>
            <th>Title</th>
            <th>Date</th>
            <th>Mission</th>
            <th>Audio</th>
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
              <td>
                <button className="reel-link-btn" type="button">
                  {r.identifier}
                </button>
              </td>
              <td>{r.id_prefix}</td>
              <td className="reel-title-cell" title={r.title ?? ""}>
                {r.title ? (r.title.length > 80 ? r.title.slice(0, 80) + "…" : r.title) : "—"}
              </td>
              <td>{r.date || "—"}</td>
              <td>{r.mission || "—"}</td>
              <td>{r.audio || "—"}</td>
              <td>{r.has_transfer_on_disk ? "✓" : ""}</td>
              <td>{r.has_shotlist_pdf ? "✓" : ""}</td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={8} className="reel-table-empty">
                No results
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
