import type { JSX } from "react";
import type { DiscoveryShotlist } from "../types";
import styles from "./DiscoveryEntries.module.css";

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
    <div className={styles.discoveryEntries}>
      <h3>Discovery Shot List Entries ({entries.length})</h3>
      {entries.map((e) => (
        <div key={e.rowid} className={styles.entry}>
          <dl className={styles.dl}>
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
              <pre className={styles.shotlistRaw}>{e.shotlist_raw}</pre>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}
