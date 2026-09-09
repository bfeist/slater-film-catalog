// ---------------------------------------------------------------------------
// streamingPipeline.ts — shared ffmpeg streaming used by both the catalog API
// (monolithic mode) and the home gateway. Resolves a DB file_id to an absolute
// path, applies the NARA proxy leader offset, parses timecode, and pipes a
// watermarked MP4 fragment stream to the response.
// ---------------------------------------------------------------------------

import path from "node:path";
import fs from "node:fs";
import { spawn, type ChildProcess } from "node:child_process";
import type { Response } from "express";
import { getDb } from "./db.js";
import { config } from "./config.js";
import { ConsoleLogger, logActivity } from "./logger.js";

// NARA_PROXY_ROOT is compared against fully-resolved lowercase paths.
// On Linux/Docker the O:\ drive maps to config.videoArchiveRoot (/archive).
const NARA_PROXY_ROOT =
  process.platform === "win32"
    ? path.normalize("O:\\MPEG-Proxies\\NARA").toLowerCase()
    : config.videoArchiveRoot + "/mpeg-proxies/nara";
const NARA_LEADER_SECS = 10;

const HEARTBEAT_TIMEOUT_MS = 15_000;

interface ActiveStream {
  ffmpeg: ChildProcess;
  watchdog: ReturnType<typeof setTimeout>;
  identifier: string;
  username: string;
}
const activeStreams = new Map<string, ActiveStream>();

export function deregisterStream(streamId: string, reason: string): void {
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

export function heartbeat(streamId: string): boolean {
  const s = activeStreams.get(streamId);
  if (!s) return false;
  clearTimeout(s.watchdog);
  s.watchdog = setTimeout(
    () => deregisterStream(streamId, "heartbeat timeout"),
    HEARTBEAT_TIMEOUT_MS
  );
  return true;
}

/** Resolve a DB folder_root + rel_path to an absolute file path (Linux-aware). */
export function resolveFilePath(folderRoot: string, relPath: string): string {
  if (process.platform === "win32") {
    return path.join(folderRoot, relPath);
  }
  const remapped = folderRoot
    .replace(/^[A-Za-z]:[/\\]/, config.videoArchiveRoot + "/")
    .replace(/\\/g, "/");
  return path.join(remapped, relPath);
}

interface ParsedTC {
  hours: number;
  minutes: number;
  seconds: number;
  frames: number;
  dropFrame: boolean;
}

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

function tcToFrameCount(tc: ParsedTC, nominalFps: number): number {
  const fps = Math.round(nominalFps);
  const raw = (tc.hours * 3600 + tc.minutes * 60 + tc.seconds) * fps + tc.frames;
  if (!tc.dropFrame || fps !== 30) return raw;
  const totalMins = 60 * tc.hours + tc.minutes;
  return raw - 2 * (totalMins - Math.floor(totalMins / 10));
}

function frameCountToTc(n: number, nominalFps: number, dropFrame: boolean): string {
  n = Math.max(0, n);
  const fps = Math.round(nominalFps);
  let hh: number, mm: number, ss: number, ff: number;
  if (dropFrame && fps === 30) {
    const framesPerMin = 30 * 60 - 2;
    const framesPer10Min = 30 * 600 - 2 * 9;
    const tenGroups = Math.floor(n / framesPer10Min);
    const rem = n % framesPer10Min;
    const adjMins = rem < 30 * 60 ? 0 : 1 + Math.floor((rem - 30 * 60) / framesPerMin);
    const v = rem + 2 * adjMins;
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
  for (const s of streams) {
    if (typeof s !== "object" || s === null) continue;
    const st = s as Record<string, unknown>;
    if (st["codec_type"] === "video") {
      const tc = (st["tags"] as Record<string, unknown> | undefined)?.["timecode"];
      if (typeof tc === "string" && tc.trim()) return tc.trim();
    }
  }
  for (const s of streams) {
    if (typeof s !== "object" || s === null) continue;
    const st = s as Record<string, unknown>;
    if (st["codec_type"] === "data" && st["codec_name"] === "tmcd") {
      const tc = (st["tags"] as Record<string, unknown> | undefined)?.["timecode"];
      if (typeof tc === "string" && tc.trim()) return tc.trim();
    }
  }
  const format = p["format"] as Record<string, unknown> | undefined;
  if (format) {
    const tc = (format["tags"] as Record<string, unknown> | undefined)?.["timecode"];
    if (typeof tc === "string" && tc.trim()) return tc.trim();
  }
  return null;
}

export interface StreamRequest {
  fileId: number;
  startSecs: number;
  streamId: string;
  username: string;
}

export interface StreamFailure {
  status: number;
  message: string;
}

/**
 * Stream a watermarked MP4 fragment for the given DB file_id to `res`.
 * Returns null on success (response is owned by ffmpeg), or a {status,message}
 * descriptor when the request can't even start (file missing, etc).
 */
export function streamFile(
  _req: { on(event: "close", cb: () => void): unknown },
  res: Response,
  opts: StreamRequest
): StreamFailure | null {
  const d = getDb();
  const file = d.prepare("SELECT * FROM files_on_disk WHERE id = ?").get(opts.fileId) as
    { folder_root: string; rel_path: string } | undefined;
  if (!file) {
    return { status: 404, message: "File not found" };
  }
  const fullPath = resolveFilePath(file.folder_root, file.rel_path);
  if (!fs.existsSync(fullPath)) {
    ConsoleLogger.error(
      `[video-stream] File not found on disk: ${fullPath} (folder_root=${file.folder_root})`
    );
    return { status: 404, message: "File not found on disk" };
  }

  const probe = d.prepare("SELECT * FROM ffprobe_metadata WHERE file_id = ?").get(opts.fileId) as
    { video_codec?: string; video_frame_rate?: string; probe_json?: string } | undefined;

  const startSecs = opts.startSecs || 0;
  const isNaraProxy = path.normalize(fullPath).toLowerCase().startsWith(NARA_PROXY_ROOT);
  const effectiveStartSecs = isNaraProxy ? startSecs + NARA_LEADER_SECS : startSecs;

  const reelRow = d
    .prepare("SELECT reel_identifier FROM transfer_file_matches WHERE file_id = ? LIMIT 1")
    .get(opts.fileId) as { reel_identifier: string } | undefined;
  const reelIdentifier = reelRow?.reel_identifier ?? "unknown";

  const codec = probe?.video_codec ?? "unknown";
  ConsoleLogger.info(
    `[video-stream] Playing ${reelIdentifier} (file=${opts.fileId}, ${codec}) → mp4/${config.videoEncoder}, start=${startSecs}s${isNaraProxy ? ` (NARA proxy: physical seek=${effectiveStartSecs}s)` : ""}`
  );
  logActivity({
    action: "play_video",
    identifier: reelIdentifier,
    username: opts.username,
    details: `file_id=${opts.fileId} codec=${codec} start=${startSecs}s`,
  });

  res.writeHead(200, {
    "Content-Type": "video/mp4",
    "Transfer-Encoding": "chunked",
    "Cache-Control": "no-cache",
  });

  // ffmpeg's filter parser treats Windows backslashes as escapes. Normalize
  // to forward slashes before escaping the drive-letter colon.
  const fontEscaped = config.watermarkMonoFontPath.replace(/\\/g, "/").replace(/:/g, "\\:");
  let fps = 0;
  if (probe?.video_frame_rate) {
    const parts = probe.video_frame_rate.split("/");
    fps = parseFloat(parts[0]) / (parseFloat(parts[1]) || 1);
  }
  let frameOffset = 0;
  if (startSecs > 0 && fps > 0) frameOffset = Math.round(startSecs * fps);

  const sourceTimecode = extractTimecodeFromProbeJson(probe?.probe_json);
  let drawtextContent: string;
  if (sourceTimecode && fps > 0) {
    let startTc = sourceTimecode;
    if (frameOffset > 0) {
      const parsed = parseTimecodeStr(sourceTimecode);
      if (parsed) {
        const advanced = tcToFrameCount(parsed, fps) + frameOffset;
        startTc = frameCountToTc(advanced, fps, parsed.dropFrame);
      }
    }
    const tcEscaped = startTc.replace(/:/g, "\\:");
    const tcRate = probe?.video_frame_rate ?? String(Math.round(fps));
    drawtextContent = `timecode='${tcEscaped}':timecode_rate=${tcRate}`;
  } else {
    let startTc = "00:00:00:00";
    if (frameOffset > 0 && fps > 0) startTc = frameCountToTc(frameOffset, fps, false);
    const tcEscaped = startTc.replace(/:/g, "\\:");
    const tcRate = probe?.video_frame_rate ?? String(Math.round(fps));
    drawtextContent = `timecode='${tcEscaped}':timecode_rate=${tcRate}`;
  }

  const watermark =
    `scale=1280:-2:force_original_aspect_ratio=decrease,format=yuv420p,` +
    `drawbox=x=0:y=ih*9/15-10:w=iw:h=ih/10+20:color=black@0.2:t=ih,` +
    `drawtext=fontfile='${fontEscaped}'` +
    `:${drawtextContent}` +
    ":fontsize=h/10" +
    ":fontcolor=white@0.3" +
    ":x=(w-text_w)/2" +
    ":y=(h-text_h)/1.5";

  const ffmpegArgs: string[] = ["-copyts"];
  if (effectiveStartSecs > 0) ffmpegArgs.push("-ss", String(effectiveStartSecs));
  ffmpegArgs.push("-i", fullPath);

  // Fragmented MP4 only flushes a playable fragment at a keyframe. Keep the
  // GOP to roughly one second so expensive sources (for example 4K ProRes
  // decoded well below realtime) do not leave the player waiting for the
  // encoder's much longer default GOP before receiving media bytes.
  const gopSize = Math.max(1, Math.round(fps));

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
    "-g",
    String(gopSize),
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

  if (opts.streamId) {
    const watchdog = setTimeout(
      () => deregisterStream(opts.streamId, "heartbeat timeout"),
      HEARTBEAT_TIMEOUT_MS
    );
    activeStreams.set(opts.streamId, {
      ffmpeg,
      watchdog,
      identifier: reelIdentifier,
      username: opts.username,
    });
  }

  const cleanup = (reason: string) => {
    if (opts.streamId) {
      deregisterStream(opts.streamId, reason);
    } else {
      try {
        ffmpeg.kill("SIGTERM");
      } catch {
        // already dead
      }
    }
  };

  ffmpeg.stdout?.pipe(res);
  const stderrLines: string[] = [];
  ffmpeg.stderr?.on("data", (data: Buffer) => {
    const line = data.toString().trim();
    stderrLines.push(line);
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
    if (!res.headersSent) res.status(500).send("ffmpeg not available");
    cleanup("ffmpeg error");
  });
  ffmpeg.on("close", (code) => {
    if (code !== 0) {
      const tail = stderrLines.slice(-20).join("\n");
      ConsoleLogger.error(`[ffmpeg] process exited with code ${code} for ${fullPath}\n${tail}`);
    }
    res.end();
    if (opts.streamId) {
      const s = activeStreams.get(opts.streamId);
      if (s) {
        clearTimeout(s.watchdog);
        activeStreams.delete(opts.streamId);
      }
    }
  });

  // IncomingMessage "close" means the request side has completed/closed and
  // can fire immediately after a normal GET on Windows. The streamed response
  // is the connection whose premature close means the viewer disconnected.
  res.on("close", () => {
    if (!res.writableEnded) cleanup("client disconnected");
  });
  return null;
}
