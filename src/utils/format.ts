// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

/** Format bytes to human-readable string */
export function formatBytes(bytes: number | null): string {
  if (bytes == null) return "—";
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const val = bytes / Math.pow(1024, i);
  return `${val.toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
}

/** Format seconds to HH:MM:SS */
export function formatDuration(secs: number | null): string {
  if (secs == null) return "—";
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = Math.floor(secs % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** Format a frame rate fraction like "30000/1001" to "29.97" */
export function formatFrameRate(fr: string | null): string {
  if (!fr) return "—";
  const parts = fr.split("/");
  if (parts.length === 2) {
    const val = parseInt(parts[0], 10) / parseInt(parts[1], 10);
    return `${val.toFixed(2)} fps`;
  }
  return `${fr} fps`;
}

/** Format resolution like "1920×1080" */
export function formatResolution(w: number | null, h: number | null): string {
  if (w == null || h == null) return "—";
  return `${w}×${h}`;
}

/** Format bitrate to human-readable */
export function formatBitrate(bps: number | null): string {
  if (bps == null) return "—";
  if (bps > 1_000_000_000) return `${(bps / 1_000_000_000).toFixed(1)} Gbps`;
  if (bps > 1_000_000) return `${(bps / 1_000_000).toFixed(1)} Mbps`;
  if (bps > 1_000) return `${(bps / 1_000).toFixed(0)} kbps`;
  return `${bps} bps`;
}
