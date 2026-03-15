import { useCallback, useEffect, useRef, useState, type JSX } from "react";
import { videoStreamUrl, videoHeartbeat, videoStop } from "../api/client";
import { formatDuration } from "../utils/format";
import styles from "./VideoPlayer.module.css";

interface VideoPlayerProps {
  fileId: number;
  filename: string;
  durationSecs: number | null;
  onClose: () => void;
}

// Each seek generates a fresh StreamKey so the server gets a new registration
// and the heartbeat loop restarts cleanly around the new ffmpeg process.
interface StreamKey {
  offset: number;
  id: string;
}

export default function VideoPlayer({
  fileId,
  filename,
  durationSecs,
  onClose,
}: VideoPlayerProps): JSX.Element {
  const videoRef = useRef<HTMLVideoElement>(null);
  const scrubberRef = useRef<HTMLDivElement>(null);

  // Atomic seek-offset + stream-id so both update in one setState call
  const [streamKey, setStreamKey] = useState<StreamKey>(() => ({
    offset: 0,
    id: crypto.randomUUID(),
  }));
  // Elapsed time reported by the <video> element (since current seek offset)
  const [videoTime, setVideoTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  // While dragging, show the preview time; null means not dragging
  const [dragTime, setDragTime] = useState<number | null>(null);

  // Tracks a deferred videoStop call so it can be cancelled on Strict Mode / HMR
  // remounts where the same streamId is re-registered immediately after cleanup.
  const pendingStopRef = useRef<{ id: string; timer: ReturnType<typeof setTimeout> } | null>(null);

  const duration = durationSecs ?? 0;
  const currentTime = streamKey.offset + videoTime;

  // Build the stream URL with the current seek offset and stream id
  const streamUrl = videoStreamUrl(fileId, streamKey.id, streamKey.offset);

  // Update videoTime from the <video> element's timeupdate event
  useEffect(() => {
    const vid = videoRef.current;
    if (!vid) return;
    const onTimeUpdate = () => setVideoTime(vid.currentTime);
    vid.addEventListener("timeupdate", onTimeUpdate);
    return () => vid.removeEventListener("timeupdate", onTimeUpdate);
  }, []);

  // When the stream key changes (seek or initial mount), reset videoTime and reload.
  // Cleanup sends an explicit stop so the previous ffmpeg is killed immediately
  // rather than waiting for the heartbeat timeout.
  useEffect(() => {
    setVideoTime(0);
    const vid = videoRef.current;
    if (vid) {
      vid.load();
      if (isPlaying) vid.play().catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [streamKey]);

  // Heartbeat — keeps the server-side watchdog alive while the player is open.
  // Sends an immediate ping, then one every 5 s.
  // Cleanup fires on seek (new streamKey) and on unmount, sending an explicit
  // stop so the server kills ffmpeg right away instead of waiting for timeout.
  //
  // The stop is deferred by one tick so that React Strict Mode's immediate
  // cleanup→remount cycle (which reuses the same streamId) can cancel it.
  // On a real seek the new streamKey has a different id, so the old stop is
  // NOT cancelled and still fires correctly.
  useEffect(() => {
    const { id } = streamKey;

    // Cancel a pending stop for this same stream id (Strict Mode / HMR remount).
    if (pendingStopRef.current?.id === id) {
      clearTimeout(pendingStopRef.current.timer);
      pendingStopRef.current = null;
    }

    videoHeartbeat(id).catch(() => {});
    const interval = setInterval(() => videoHeartbeat(id).catch(() => {}), 5_000);
    return () => {
      clearInterval(interval);
      const timer = setTimeout(() => {
        if (pendingStopRef.current?.id === id) pendingStopRef.current = null;
        videoStop(id).catch(() => {});
      }, 0);
      pendingStopRef.current = { id, timer };
    };
  }, [streamKey]);

  const togglePlay = useCallback(() => {
    const vid = videoRef.current;
    if (!vid) return;
    if (vid.paused) {
      vid.play().catch(() => {});
      setIsPlaying(true);
    } else {
      vid.pause();
      setIsPlaying(false);
    }
  }, []);

  // --- Scrubber interaction ---
  const getScrubTime = useCallback(
    (clientX: number): number => {
      const bar = scrubberRef.current;
      if (!bar || duration <= 0) return 0;
      const rect = bar.getBoundingClientRect();
      const fraction = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      return fraction * duration;
    },
    [duration]
  );

  // Commit a seek: generate a new stream key so both offset and streamId update
  // atomically, giving the new ffmpeg process a fresh registration on the server.
  const commitSeek = useCallback(
    (time: number) => {
      setDragTime(null);
      const clamped = Math.max(0, Math.min(duration, time));
      setStreamKey({ offset: clamped, id: crypto.randomUUID() });
    },
    [duration]
  );

  const onScrubPointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      const bar = scrubberRef.current;
      if (!bar) return;
      bar.setPointerCapture(e.pointerId);
      const t = getScrubTime(e.clientX);
      setDragTime(t);

      const onMove = (ev: PointerEvent) => {
        setDragTime(getScrubTime(ev.clientX));
      };
      const onUp = (ev: PointerEvent) => {
        bar.removeEventListener("pointermove", onMove);
        bar.removeEventListener("pointerup", onUp);
        bar.releasePointerCapture(ev.pointerId);
        commitSeek(getScrubTime(ev.clientX));
      };
      bar.addEventListener("pointermove", onMove);
      bar.addEventListener("pointerup", onUp);
    },
    [getScrubTime, commitSeek]
  );

  // Progress fraction for the filled bar
  const displayTime = dragTime !== null ? dragTime : currentTime;
  const progressFraction = duration > 0 ? Math.min(1, displayTime / duration) : 0;

  return (
    <div className={styles.overlay}>
      <div className={styles.container}>
        <div className={styles.header}>
          <span>{filename}</span>
          <button onClick={onClose}>✕ Close</button>
        </div>

        <div className={styles.videoWrapper}>
          <video
            ref={videoRef}
            autoPlay
            className={styles.videoElement}
            src={streamUrl}
            onClick={togglePlay}
          >
            <track kind="captions" />
          </video>
        </div>

        {/* Custom controls bar */}
        <div className={styles.controls}>
          <button className={styles.playBtn} onClick={togglePlay}>
            {isPlaying ? "❚❚" : "▶"}
          </button>

          {/* Scrubber track */}
          <div className={styles.scrubber} ref={scrubberRef} onPointerDown={onScrubPointerDown}>
            <div className={styles.scrubberFill} style={{ width: `${progressFraction * 100}%` }} />
            <div className={styles.scrubberThumb} style={{ left: `${progressFraction * 100}%` }} />
            {/* Tooltip showing time while dragging */}
            {dragTime !== null && (
              <div
                className={styles.scrubberTooltip}
                style={{ left: `${progressFraction * 100}%` }}
              >
                {formatDuration(dragTime)}
              </div>
            )}
          </div>

          <span className={styles.time}>
            {formatDuration(displayTime)} / {formatDuration(duration || null)}
          </span>
        </div>

        <div className={styles.info}>
          Streaming file #{fileId}. Seek restarts the transcode from the selected position.
        </div>
      </div>
    </div>
  );
}
