import { useCallback, useEffect, useRef, useState, type JSX } from "react";
import { ApiError, requestVideoSession, videoHeartbeat, videoStop } from "../api/client";
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

/**
 * Coarse playback lifecycle for the busy/error overlay.
 *  - requesting_session: POST /api/video/sessions in flight
 *  - connecting: session resolved, <video> element loading metadata
 *  - buffering: video stalled / waiting after start (ffmpeg still spinning up)
 *  - ready: media is currently playing or paused with frames available
 *  - error: terminal failure (session mint failed or media element error)
 */
type Stage = "requesting_session" | "connecting" | "buffering" | "ready" | "error";

interface StageError {
  title: string;
  detail: string;
  /** Optional retry handler — when present the overlay shows a Retry button. */
  retry?: () => void;
}

function describeApiError(err: unknown): { title: string; detail: string } {
  if (err instanceof ApiError) {
    if (err.status === 503) {
      const reasonLabel: Record<string, string> = {
        timeout: "Video gateway did not respond in time.",
        unreachable: "Cannot reach the video gateway from the catalog server.",
        http_error: `Video gateway returned an error${err.gatewayStatus ? ` (HTTP ${err.gatewayStatus})` : ""}.`,
        unknown: "Video gateway is unavailable.",
      };
      const headline = err.reason ? reasonLabel[err.reason] : "Video gateway is unavailable.";
      return {
        title: "Video streaming unavailable",
        detail: err.detail ? `${headline} ${err.detail}` : headline,
      };
    }
    if (err.status === 404) {
      return { title: "File not found", detail: err.detail ?? "The requested file is missing." };
    }
    if (err.status === 401 || err.status === 403) {
      return { title: "Not authorized", detail: err.detail ?? "Sign in required for playback." };
    }
    return {
      title: `Server error (${err.status})`,
      detail: err.detail ?? err.message,
    };
  }
  const msg = err instanceof Error ? err.message : String(err);
  return { title: "Could not start playback", detail: msg };
}

function describeMediaError(el: HTMLVideoElement): { title: string; detail: string } {
  const e = el.error;
  if (!e) return { title: "Playback error", detail: "Unknown media error." };
  switch (e.code) {
    case 1:
      return { title: "Playback aborted", detail: "The download was cancelled." };
    case 2:
      return {
        title: "Network error during playback",
        detail:
          "The connection to the video gateway dropped while streaming. Check that the gateway is online.",
      };
    case 3:
      return {
        title: "Decode error",
        detail:
          "The browser could not decode the transcoded stream. The source file may be corrupt or unsupported.",
      };
    case 4:
      return {
        title: "Stream not supported",
        detail:
          e.message ||
          "The video gateway is not serving a playable stream. ffmpeg may have failed on the server.",
      };
    default:
      return { title: "Playback error", detail: e.message || `Media error code ${e.code}` };
  }
}

const STAGE_LABELS: Record<Stage, string> = {
  requesting_session: "Requesting playback session…",
  connecting: "Connecting to video gateway…",
  buffering: "Buffering — transcoding from new position…",
  ready: "",
  error: "",
};

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

  // Resolved stream URL for the current streamKey; null while the session is
  // being requested or if it failed (split mode + video gateway down).
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [stage, setStage] = useState<Stage>("requesting_session");
  const [stageError, setStageError] = useState<StageError | null>(null);

  // Force re-fetching a session (used by the Retry button after errors).
  const retrySession = useCallback(() => {
    setStreamKey({ offset: streamKey.offset, id: crypto.randomUUID() });
  }, [streamKey.offset]);

  // Fetch a session URL whenever the streamKey changes (initial mount or seek).
  useEffect(() => {
    let cancelled = false;
    setStreamUrl(null);
    setStage("requesting_session");
    setStageError(null);
    requestVideoSession(fileId, streamKey.offset, streamKey.id)
      .then((session) => {
        if (cancelled) return;
        setStreamUrl(session.streamUrl);
        setStage("connecting");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const { title, detail } = describeApiError(err);
        setStage("error");
        setStageError({ title, detail, retry: retrySession });
      });
    return () => {
      cancelled = true;
    };
  }, [fileId, streamKey, retrySession]);

  // Update videoTime from the <video> element's timeupdate event
  useEffect(() => {
    const vid = videoRef.current;
    if (!vid) return;
    const onTimeUpdate = () => setVideoTime(vid.currentTime);
    vid.addEventListener("timeupdate", onTimeUpdate);
    return () => vid.removeEventListener("timeupdate", onTimeUpdate);
  }, []);

  // Wire up media-element lifecycle events so the overlay reflects buffering /
  // playing / decode failures rather than just a frozen UI.
  useEffect(() => {
    const vid = videoRef.current;
    if (!vid || !streamUrl) return;
    const onWaiting = () => setStage((s) => (s === "error" ? s : "buffering"));
    const onPlaying = () => {
      setStage("ready");
      setIsPlaying(true);
    };
    const onCanPlay = () => setStage((s) => (s === "error" ? s : "ready"));
    const onPause = () => setIsPlaying(false);
    const onPlay = () => setIsPlaying(true);
    const onStalled = () => setStage((s) => (s === "error" ? s : "buffering"));
    const onError = () => {
      const { title, detail } = describeMediaError(vid);
      setStage("error");
      setStageError({ title, detail, retry: retrySession });
    };
    vid.addEventListener("waiting", onWaiting);
    vid.addEventListener("playing", onPlaying);
    vid.addEventListener("canplay", onCanPlay);
    vid.addEventListener("pause", onPause);
    vid.addEventListener("play", onPlay);
    vid.addEventListener("stalled", onStalled);
    vid.addEventListener("error", onError);
    return () => {
      vid.removeEventListener("waiting", onWaiting);
      vid.removeEventListener("playing", onPlaying);
      vid.removeEventListener("canplay", onCanPlay);
      vid.removeEventListener("pause", onPause);
      vid.removeEventListener("play", onPlay);
      vid.removeEventListener("stalled", onStalled);
      vid.removeEventListener("error", onError);
    };
  }, [streamUrl, retrySession]);

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
  // In split mode this hits the video gateway directly; in monolithic mode it
  // hits same-origin Express. Both are derived from streamUrl.
  useEffect(() => {
    const { id } = streamKey;
    if (!streamUrl) return; // wait until session resolves

    if (pendingStopRef.current?.id === id) {
      clearTimeout(pendingStopRef.current.timer);
      pendingStopRef.current = null;
    }

    videoHeartbeat(streamUrl, id).catch(() => {});
    const interval = setInterval(() => videoHeartbeat(streamUrl, id).catch(() => {}), 5_000);
    return () => {
      clearInterval(interval);
      const timer = setTimeout(() => {
        if (pendingStopRef.current?.id === id) pendingStopRef.current = null;
        videoStop(streamUrl, id).catch(() => {});
      }, 0);
      pendingStopRef.current = { id, timer };
    };
  }, [streamKey, streamUrl]);

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

  // Skip forward/backward by a given number of seconds
  const skip = useCallback(
    (delta: number) => {
      const newTime = Math.max(0, Math.min(duration, currentTime + delta));
      commitSeek(newTime);
    },
    [currentTime, duration, commitSeek]
  );

  // Keyboard shortcuts — Space: play/pause, ←/→: ±5s, Shift+←/→: ±10s
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Don't capture if user is typing in an input
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      )
        return;

      switch (e.key) {
        case " ":
          e.preventDefault();
          togglePlay();
          break;
        case "ArrowLeft":
          e.preventDefault();
          skip(e.shiftKey ? -10 : -5);
          break;
        case "ArrowRight":
          e.preventDefault();
          skip(e.shiftKey ? 10 : 5);
          break;
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [togglePlay, skip]);

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

  const showBusy =
    stage === "requesting_session" || stage === "connecting" || stage === "buffering";

  return (
    <div className={styles.overlay}>
      <div className={styles.container}>
        <div className={styles.header}>
          <span>{filename}</span>
          <button onClick={onClose}>✕ Close</button>
        </div>

        <div className={styles.videoWrapper}>
          {streamUrl && (
            <video
              ref={videoRef}
              autoPlay
              className={styles.videoElement}
              src={streamUrl}
              onClick={togglePlay}
            >
              <track kind="captions" />
            </video>
          )}

          {showBusy && (
            <div className={styles.statusOverlay} role="status" aria-live="polite">
              <div className={styles.spinner} aria-hidden="true" />
              <div className={styles.statusText}>{STAGE_LABELS[stage]}</div>
            </div>
          )}

          {stage === "error" && stageError && (
            <div className={styles.statusOverlay} role="alert">
              <div className={styles.errorTitle}>{stageError.title}</div>
              <div className={styles.errorDetail}>{stageError.detail}</div>
              {stageError.retry && (
                <button className={styles.retryBtn} onClick={stageError.retry}>
                  Retry
                </button>
              )}
            </div>
          )}
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

          <span className={styles.keyHints} title="Keyboard shortcuts">
            <kbd>Space</kbd> play/pause &nbsp; <kbd>←</kbd>/<kbd>→</kbd> ±5s &nbsp; <kbd>Shift</kbd>
            +<kbd>←</kbd>/<kbd>→</kbd> ±10s
          </span>
        </div>

        <div className={styles.info}>
          Seeking re-encodes from the new position (may take a moment to buffer). The timecode
          always reflects the absolute position in the source file.
        </div>
      </div>
    </div>
  );
}
