import { useState, useEffect, type JSX } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import * as VisuallyHidden from "@radix-ui/react-visually-hidden";
import { fetchShotlistText } from "../api/client";
import styles from "./ShotlistTextViewer.module.css";

interface ShotlistTextViewerProps {
  identifier: string;
  onClose: () => void;
}

export default function ShotlistTextViewer({
  identifier,
  onClose,
}: ShotlistTextViewerProps): JSX.Element {
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchShotlistText(identifier)
      .then((res) => {
        if (!cancelled) {
          setText(res.text);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(String(err));
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [identifier]);

  return (
    <Dialog.Root open onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className={styles.overlay} />
        <Dialog.Content className={styles.container} aria-describedby={undefined}>
          <VisuallyHidden.Root>
            <Dialog.Description>Shot list text for {identifier}</Dialog.Description>
          </VisuallyHidden.Root>
          <div className={styles.header}>
            <Dialog.Title className={styles.title}>Shot List — {identifier}</Dialog.Title>
            <Dialog.Close asChild>
              <button className={styles.closeBtn}>✕</button>
            </Dialog.Close>
          </div>

          <div className={styles.body}>
            {loading && <p className="muted">Loading…</p>}
            {error && <p className={styles.error}>Failed to load shot list text.</p>}
            {!loading && !error && text === null && (
              <p className="muted">No shot list text available for this reel.</p>
            )}
            {!loading && !error && text !== null && <pre className={styles.ocrText}>{text}</pre>}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
