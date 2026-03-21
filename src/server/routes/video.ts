// ---------------------------------------------------------------------------
// /api/video/:file_id/* — video info + transcoded stream with watermark
// ---------------------------------------------------------------------------

import { Router } from "express";
import path from "node:path";
import fs from "node:fs";
import { spawn, type ChildProcess } from "node:child_process";
import { getDb } from "../db.js";
import { config } from "../config.js";
import { redactFileOnDiskEntry } from "../redaction.js";
import { isRevealed, getRequestUser } from "../slater.js";
import { ConsoleLogger, logActivity } from "../logger.js";

const router = Router();

// ---------------------------------------------------------------------------
// NARA proxy leader — the first 10 seconds of every NARA proxy is a leader
// (slate/countdown) that should be hidden from viewers.  Any file whose path
// sits under NARA_PROXY_ROOT is automatically seeked past the leader so that
// logical second 0 corresponds to physical second 10 in the file.
// ---------------------------------------------------------------------------

// NARA_PROXY_ROOT is compared against fully-resolved lowercase paths.
// On Linux/Docker the O:\ drive maps to config.videoArchiveRoot (/archive).
const NARA_PROXY_ROOT =
  process.platform === "win32"
    ? path.normalize("O:\\MPEG-Proxies\\NARA").toLowerCase()
    : config.videoArchiveRoot + "/mpeg-proxies/nara";
const NARA_LEADER_SECS = 10;

/**
 * Resolve a DB folder_root + rel_path to an absolute file path.
 * On Linux/Docker, Windows-style drive letter prefixes (e.g. O:\, O:/) are
 * remapped to the configured archive mount root so containers can find files
 * whose paths were recorded on the Windows host.
 */
function resolveFilePath(folderRoot: string, relPath: string): string {
  if (process.platform === "win32") {
    return path.join(folderRoot, relPath);
  }
  // Replace leading drive letter + colon (e.g. "O:/" or "O:\\") with the
  // archive root, then normalise remaining backslashes to forward slashes.
  const remapped = folderRoot
    .replace(/^[A-Za-z]:[/\\]/, config.videoArchiveRoot + "/")
    .replace(/\\/g, "/");
  return path.join(remapped, relPath);
}

// ---------------------------------------------------------------------------
// Timecode helpers — used for watermark burn-in when the source has a TC track
// ---------------------------------------------------------------------------

interface ParsedTC {
  hours: number;
  minutes: number;
  seconds: number;
  frames: number;
  dropFrame: boolean;
}

/** Parse a SMPTE timecode string such as "01:23:45:12" (NDF) or "01:23:45;12" (DF). */
function parseTimecodeStr(tc: string): ParsedTC | null {
  const m = tc.trim().match(/^(\d{1,2}):(\d{2}):(\d{2})([;:])(\d{2})$/);
  if (!m) return null;
  return {
    hours: parseInt(m[1], 10),
    minutes: parseInt(m[2], 10),
    seconds: parseInt(m[3], 10),
    dropFrame: m[4] === ";",
    frames: parseInt(m[5], 10),
  };
}

/** Convert a parsed TC to an absolute frame count. */
function tcToFrameCount(tc: ParsedTC, nominalFps: number): number {
  const fps = Math.round(nominalFps);
  const raw = (tc.hours * 3600 + tc.minutes * 60 + tc.seconds) * fps + tc.frames;
  if (!tc.dropFrame || fps !== 30) return raw;
  // SMPTE 29.97 drop-frame: 2 frames dropped per non-10th minute
  const totalMins = 60 * tc.hours + tc.minutes;
  return raw - 2 * (totalMins - Math.floor(totalMins / 10));
}

/** Convert an absolute frame count back to a SMPTE TC string. */
function frameCountToTc(n: number, nominalFps: number, dropFrame: boolean): string {
  n = Math.max(0, n);
  const fps = Math.round(nominalFps);
  let hh: number, mm: number, ss: number, ff: number;
  if (dropFrame && fps === 30) {
    // SMPTE 29.97 drop-frame reverse conversion
    const framesPerMin = 30 * 60 - 2; // 1798
    const framesPer10Min = 30 * 600 - 2 * 9; // 17982
    const tenGroups = Math.floor(n / framesPer10Min);
    const rem = n % framesPer10Min;
    const adjMins = rem < 30 * 60 ? 0 : 1 + Math.floor((rem - 30 * 60) / framesPerMin);
    const v = rem + 2 * adjMins; // virtual index treating dropped frames as real
    ff = v % 30;
    ss = Math.floor(v / 30) % 60;
    const mmIn10 = Math.floor(v / 1800);
    hh = Math.floor(tenGroups / 6);
    mm = (tenGroups % 6) * 10 + mmIn10;
  } else {
    ff = n % fps;
    ss = Math.floor(n / fps) % 60;
    mm = Math.floor(n / (fps * 60)) % 60;
    hh = Math.floor(n / (fps * 3600));
  }
  const sep = dropFrame ? ";" : ":";
  return (
    [String(hh).padStart(2, "0"), String(mm).padStart(2, "0"), String(ss).padStart(2, "0")].join(
      ":"
    ) +
    sep +
    String(ff).padStart(2, "0")
  );
}

/**
 * Extract a timecode string from raw ffprobe JSON, checking (in priority order):
 *   1. First video stream tags.timecode
 *   2. Any data stream with codec_name "tmcd" → tags.timecode
 *   3. format.tags.timecode
 * Returns null if no timecode track is found.
 */
function extractTimecodeFromProbeJson(probeJsonStr: string | null | undefined): string | null {
  if (!probeJsonStr) return null;
  let probe: unknown;
  try {
    probe = JSON.parse(probeJsonStr);
  } catch {
    return null;
  }
  if (typeof probe !== "object" || probe === null) return null;
  const p = probe as Record<string, unknown>;
  const streams = Array.isArray(p["streams"]) ? (p["streams"] as unknown[]) : [];

  // 1. Video stream tags
  for (const s of streams) {
    if (typeof s !== "object" || s === null) continue;
    const st = s as Record<string, unknown>;
    if (st["codec_type"] === "video") {
      const tc = (st["tags"] as Record<string, unknown> | undefined)?.["timecode"];
      if (typeof tc === "string" && tc.trim()) return tc.trim();
    }
  }
  // 2. TMCD data stream
  for (const s of streams) {
    if (typeof s !== "object" || s === null) continue;
    const st = s as Record<string, unknown>;
    if (st["codec_type"] === "data" && st["codec_name"] === "tmcd") {
      const tc = (st["tags"] as Record<string, unknown> | undefined)?.["timecode"];
      if (typeof tc === "string" && tc.trim()) return tc.trim();
    }
  }
  // 3. Format tags
  const format = p["format"] as Record<string, unknown> | undefined;
  if (format) {
    const tc = (format["tags"] as Record<string, unknown> | undefined)?.["timecode"];
    if (typeof tc === "string" && tc.trim()) return tc.trim();
  }
  return null;
}

// ---------------------------------------------------------------------------
// Stream registry — tracks active ffmpeg processes by client-supplied streamId.
// Clients must send periodic heartbeats; if none arrive within the timeout the
// process is killed so it cannot hang indefinitely.
// ---------------------------------------------------------------------------

const HEARTBEAT_TIMEOUT_MS = 15_000; // kill if silent for 15 s

interface ActiveStream {
  ffmpeg: ChildProcess;
  watchdog: ReturnType<typeof setTimeout>;
  identifier: string;
  username: string;
}

const activeStreams = new Map<string, ActiveStream>();

function deregisterStream(streamId: string, reason: string): void {
  const s = activeStreams.get(streamId);
  if (!s) return;
  clearTimeout(s.watchdog);
  activeStreams.delete(streamId);
  ConsoleLogger.info(`[video-stream] Killing stream ${streamId}: ${reason}`);
  logActivity({
    action: "stop_video",
    identifier: s.identifier,
    username: s.username,
    details: `reason=${reason}`,
  });
  try {
    s.ffmpeg.kill("SIGTERM");
  } catch {
    // already dead
  }
}

function resetWatchdog(streamId: string): void {
  const s = activeStreams.get(streamId);
  if (!s) return;
  clearTimeout(s.watchdog);
  s.watchdog = setTimeout(
    () => deregisterStream(streamId, "heartbeat timeout"),
    HEARTBEAT_TIMEOUT_MS
  );
}

// ---- GET /api/video/heartbeat?streamId=... ----
router.get("/heartbeat", (req, res) => {
  const streamId = req.query.streamId as string | undefined;
  if (!streamId || !activeStreams.has(streamId)) {
    res.status(404).json({ error: "Unknown streamId" });
    return;
  }
  resetWatchdog(streamId);
  res.json({ ok: true });
});

// ---- POST /api/video/stop?streamId=... ----
router.post("/stop", (req, res) => {
  const streamId = req.query.streamId as string | undefined;
  if (streamId) {
    deregisterStream(streamId, "client stop");
  }
  res.json({ ok: true });
});

// ---- GET /api/video/:file_id/info ----
router.get("/:file_id/info", (req, res) => {
  const d = getDb();
  const fileId = parseInt(req.params.file_id, 10);
  const file = d.prepare("SELECT * FROM files_on_disk WHERE id = ?").get(fileId) as
    | Record<string, unknown>
    | undefined;
  if (!file) {
    res.status(404).json({ error: "File not found" });
    return;
  }
  const probe = d.prepare("SELECT * FROM ffprobe_metadata WHERE file_id = ?").get(fileId);
  res.json({ file: isRevealed(req) ? file : redactFileOnDiskEntry(file), probe });
});

// ---- GET /api/video/:file_id/stream ----
router.get("/:file_id/stream", (req, res) => {
  const d = getDb();
  const fileId = parseInt(req.params.file_id, 10);

  const file = d.prepare("SELECT * FROM files_on_disk WHERE id = ?").get(fileId) as
    | {
        folder_root: string;
        rel_path: string;
      }
    | undefined;
  if (!file) {
    res.status(404).send("File not found");
    return;
  }

  const fullPath = resolveFilePath(file.folder_root, file.rel_path);
  if (!fs.existsSync(fullPath)) {
    ConsoleLogger.error(
      `[video-stream] File not found on disk: ${fullPath} (folder_root=${file.folder_root})`
    );
    res.status(404).send("File not found on disk");
    return;
  }

  const probe = d.prepare("SELECT * FROM ffprobe_metadata WHERE file_id = ?").get(fileId) as
    | {
        video_codec?: string;
        video_frame_rate?: string;
        probe_json?: string;
      }
    | undefined;

  const startSecs = parseFloat((req.query.start as string) ?? "0") || 0;
  const streamId = (req.query.streamId as string | undefined) ?? "";

  // For NARA proxy files the first NARA_LEADER_SECS seconds are a hidden
  // leader. The effective seek position is offset by that amount so that
  // logical time 0 (what the client calls "start=0") maps to physical second
  // NARA_LEADER_SECS inside the file.  frameOffset — which drives the
  // watermark timecode — is intentionally based on startSecs (not
  // effectiveStartSecs) so the overlay always shows logical time starting
  // from 00:00:00:00.
  const isNaraProxy = path.normalize(fullPath).toLowerCase().startsWith(NARA_PROXY_ROOT);
  const effectiveStartSecs = isNaraProxy ? startSecs + NARA_LEADER_SECS : startSecs;

  // Look up the reel identifier for this file so we can log it
  const reelRow = d
    .prepare("SELECT reel_identifier FROM transfer_file_matches WHERE file_id = ? LIMIT 1")
    .get(fileId) as { reel_identifier: string } | undefined;
  const reelIdentifier = reelRow?.reel_identifier ?? "unknown";

  const codec = probe?.video_codec ?? "unknown";
  ConsoleLogger.info(
    `[video-stream] Playing ${reelIdentifier} (file=${fileId}, ${codec}) → mp4/${config.videoEncoder}, start=${startSecs}s${isNaraProxy ? ` (NARA proxy: physical seek=${effectiveStartSecs}s)` : ""}`
  );

  logActivity({
    action: "play_video",
    identifier: reelIdentifier,
    username: getRequestUser(req),
    details: `file_id=${fileId} codec=${codec} start=${startSecs}s`,
  });

  res.writeHead(200, {
    "Content-Type": "video/mp4",
    "Transfer-Encoding": "chunked",
    "Cache-Control": "no-cache",
  });

  // Monospace font for timecode / frame-number readability
  const fontEscaped = config.watermarkMonoFontPath.replace(/:/g, "\\:");

  // Parse the source frame rate (needed for both TC offset and frame-number display).
  let fps = 0;
  if (probe?.video_frame_rate) {
    const parts = probe.video_frame_rate.split("/");
    fps = parseFloat(parts[0]) / (parseFloat(parts[1]) || 1);
  }

  // Calculate the frame number offset for the seek position so the watermark
  // displays values relative to the file start, not the transcode start.
  let frameOffset = 0;
  if (startSecs > 0 && fps > 0) {
    frameOffset = Math.round(startSecs * fps);
  }

  // If the file carries a timecode track, burn it in; otherwise fall back to
  // frame number + PTS display (relative to the start of the file).
  const sourceTimecode = extractTimecodeFromProbeJson(probe?.probe_json);
  let drawtextContent: string;
  if (sourceTimecode && fps > 0) {
    // Advance the source TC by the seek offset so the first rendered frame
    // shows the correct timecode position within the source file.
    let startTc = sourceTimecode;
    if (frameOffset > 0) {
      const parsed = parseTimecodeStr(sourceTimecode);
      if (parsed) {
        const advanced = tcToFrameCount(parsed, fps) + frameOffset;
        startTc = frameCountToTc(advanced, fps, parsed.dropFrame);
      }
    }
    // Escape colons for ffmpeg drawtext filter (semicolons are safe as-is).
    const tcEscaped = startTc.replace(/:/g, "\\:");
    // Use the stored rational frame-rate string directly as timecode_rate.
    const tcRate = probe?.video_frame_rate ?? String(Math.round(fps));
    drawtextContent = `timecode='${tcEscaped}':timecode_rate=${tcRate}`;
  } else {
    // No timecode track: synthesize one starting from 00:00:00:00 (NDF).
    let startTc = "00:00:00:00";
    if (frameOffset > 0 && fps > 0) {
      // Advance the synthetic TC by the seek offset so the first rendered frame
      // shows the correct position within the file.
      startTc = frameCountToTc(frameOffset, fps, false); // false = NDF
    }
    const tcEscaped = startTc.replace(/:/g, "\\:");
    // Use the stored rational frame-rate string directly as timecode_rate.
    const tcRate = probe?.video_frame_rate ?? String(Math.round(fps));
    drawtextContent = `timecode='${tcEscaped}':timecode_rate=${tcRate}`;
  }

  const watermark =
    `scale=1280:-2:force_original_aspect_ratio=decrease,format=yuv420p,` +
    // Full-width semi-transparent bar behind the text.
    // y = (ih - fontsize) / 1.5  →  ih*9/15; h = fontsize + 2*padding
    `drawbox=x=0:y=ih*9/15-10:w=iw:h=ih/10+20:color=black@0.2:t=ih,` +
    `drawtext=fontfile='${fontEscaped}'` +
    `:${drawtextContent}` +
    ":fontsize=h/10" +
    ":fontcolor=white@0.3" +
    ":x=(w-text_w)/2" +
    ":y=(h-text_h)/1.5";

  const ffmpegArgs: string[] = ["-copyts"];
  if (effectiveStartSecs > 0) {
    ffmpegArgs.push("-ss", String(effectiveStartSecs));
  }
  ffmpegArgs.push("-i", fullPath);

  const ffmpeg: ChildProcess = spawn("ffmpeg", [
    ...ffmpegArgs,
    "-map",
    "0:v:0",
    "-map",
    "0:a:0?",
    "-vf",
    watermark,
    "-c:v",
    config.videoEncoder,
    "-preset",
    "fast",
    "-c:a",
    "aac",
    "-ac",
    "2",
    "-b:a",
    "64k",
    "-movflags",
    "frag_keyframe+empty_moov+default_base_moof",
    "-f",
    "mp4",
    "pipe:1",
  ]);

  // Register stream so heartbeats and explicit stops can reach this process.
  // Start watchdog immediately; first heartbeat must arrive within the timeout.
  if (streamId) {
    const watchdog = setTimeout(
      () => deregisterStream(streamId, "heartbeat timeout"),
      HEARTBEAT_TIMEOUT_MS
    );
    activeStreams.set(streamId, {
      ffmpeg,
      watchdog,
      identifier: reelIdentifier,
      username: getRequestUser(req),
    });
  }

  const cleanup = (reason: string) => {
    if (streamId) {
      deregisterStream(streamId, reason);
    } else {
      try {
        ffmpeg.kill("SIGTERM");
      } catch {
        // already dead
      }
    }
  };

  ffmpeg.stdout?.pipe(res);
  ffmpeg.stderr?.on("data", (data: Buffer) => {
    const line = data.toString().trim();
    if (
      line.includes("frame=") ||
      line.includes("error") ||
      line.includes("Error") ||
      line.includes("No such") ||
      line.includes("Invalid") ||
      line.includes("Stream mapping") ||
      line.includes("Output #")
    ) {
      ConsoleLogger.debug(`[ffmpeg] ${line.slice(0, 300)}`);
    }
  });
  ffmpeg.on("error", (err: Error) => {
    ConsoleLogger.error("[ffmpeg] spawn error:", err.message);
    if (!res.headersSent) {
      res.status(500).send("ffmpeg not available");
    }
    cleanup("ffmpeg error");
  });
  ffmpeg.on("close", (code) => {
    if (code !== 0) {
      ConsoleLogger.error(`[ffmpeg] process exited with code ${code} for ${fullPath}`);
    }
    res.end();
    if (streamId) {
      const s = activeStreams.get(streamId);
      if (s) {
        clearTimeout(s.watchdog);
        activeStreams.delete(streamId);
      }
    }
  });

  // Kill ffmpeg if client disconnects (TCP close) — belt-and-suspenders alongside heartbeat
  req.on("close", () => {
    cleanup("client disconnected");
  });
});

export default router;
