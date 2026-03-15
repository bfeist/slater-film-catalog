import { useState, useEffect, type JSX } from "react";
import { Link } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import * as VisuallyHidden from "@radix-ui/react-visually-hidden";
import { fetchReelDetail } from "../api/client";
import type { ReelDetailResponse } from "../types";
import ReelDetailContent from "./ReelDetailContent";
import styles from "./ReelDetailModal.module.css";

interface ReelDetailModalProps {
  identifier: string;
  onClose: () => void;
}

export default function ReelDetailModal({
  identifier,
  onClose,
}: ReelDetailModalProps): JSX.Element {
  const [data, setData] = useState<ReelDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchReelDetail(identifier)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [identifier]);

  let content: JSX.Element;

  if (loading) {
    content = <div className={styles.loading}>Loading…</div>;
  } else if (error) {
    content = <div className={styles.errorMsg}>Error: {error}</div>;
  } else if (!data) {
    content = <div className={styles.errorMsg}>No data</div>;
  } else {
    content = <ReelDetailContent data={data} />;
  }

  return (
    <Dialog.Root open onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className={styles.overlay} />
        <Dialog.Content className={styles.content} aria-describedby={undefined}>
          <VisuallyHidden.Root>
            <Dialog.Description>Detail view for reel {identifier}</Dialog.Description>
          </VisuallyHidden.Root>
          <div className={styles.header}>
            <Dialog.Title className={styles.title}>
              {identifier}{" "}
              <Link
                to={`/reel/${encodeURIComponent(identifier)}`}
                className={styles.permalinkLink}
                title="Open full page"
                onClick={onClose}
              >
                🔗
              </Link>
            </Dialog.Title>
            <Dialog.Close asChild>
              <button className={styles.closeBtn}>✕</button>
            </Dialog.Close>
          </div>
          <div className={styles.body}>{content}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
