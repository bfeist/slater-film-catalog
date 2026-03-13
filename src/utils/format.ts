// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

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
