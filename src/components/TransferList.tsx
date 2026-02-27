import type { JSX } from "react";
import type { Transfer } from "../types";

interface TransferListProps {
  transfers: Transfer[];
}

export default function TransferList({ transfers }: TransferListProps): JSX.Element {
  if (transfers.length === 0) {
    return <p className="muted">No transfers recorded.</p>;
  }

  return (
    <div className="transfer-list">
      <h3>Transfers ({transfers.length})</h3>
      <table className="detail-table">
        <thead>
          <tr>
            <th>Type</th>
            <th>Source Tab</th>
            <th>LTO #</th>
            <th>Tape #</th>
            <th>Filename</th>
            <th>File Path</th>
            <th>Description</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {transfers.map((t) => (
            <tr key={t.id}>
              <td>
                <code>{t.transfer_type}</code>
              </td>
              <td>{t.source_tab || "—"}</td>
              <td>{t.lto_number || "—"}</td>
              <td>{t.tape_number || "—"}</td>
              <td className="mono-cell">{t.filename || "—"}</td>
              <td className="path-cell" title={t.file_path ?? ""}>
                {t.file_path || "—"}
              </td>
              <td>{t.file_description || "—"}</td>
              <td>{t.transfer_status || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
