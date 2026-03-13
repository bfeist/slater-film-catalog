import type { JSX } from "react";
import type { DiscoveryShotlist } from "../types";

interface DiscoveryEntriesProps {
  entries: DiscoveryShotlist[];
  revealed?: boolean;
}

export default function DiscoveryEntries({
  entries,
  revealed = true,
}: DiscoveryEntriesProps): JSX.Element | null {
  if (entries.length === 0) return null;

  return (
    <div className="discovery-entries">
      <h3>Discovery Shot List Entries ({entries.length})</h3>
      {entries.map((e) => (
        <div key={e.rowid} className="discovery-entry">
          <dl className="file-info-dl">
            <dt>Tape #</dt>
            <dd>{e.tape_number}</dd>

            <dt>{revealed ? "Identifier" : "SFR"}</dt>
            <dd>{e.identifier || "—"}</dd>

            <dt>Description</dt>
            <dd>{e.description || "—"}</dd>
          </dl>
          {e.shotlist_raw && (
            <details open>
              <summary>Raw shot list text</summary>
              <pre className="shotlist-raw">{e.shotlist_raw}</pre>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}
