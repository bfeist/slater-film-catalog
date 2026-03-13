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
import { isRevealed } from "../slater.js";

const router = Router();

// ---------------------------------------------------------------------------
// Stream registry — tracks active ffmpeg processes by client-supplied streamId.
// Clients must send periodic heartbeats; if none arrive within the timeout the
// process is killed so it cannot hang indefinitely.
// ---------------------------------------------------------------------------

const HEARTBEAT_TIMEOUT_MS = 15_000; // kill if silent for 15 s

interface ActiveStream {
  ffmpeg: ChildProcess;
  watchdog: ReturnType<typeof setTimeout>;
}

const activeStreams = new Map<string, ActiveStream>();

function deregisterStream(streamId: string, reason: string): void {
  const s = activeStreams.get(streamId);
  if (!s) return;
  clearTimeout(s.watchdog);
  activeStreams.delete(streamId);
  console.log(`[video-stream] Killing stream ${streamId}: ${reason}`);
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

  const fullPath = path.join(file.folder_root, file.rel_path);
  if (!fs.existsSync(fullPath)) {
    res.status(404).send("File not found on disk");
    return;
  }

  const probe = d.prepare("SELECT * FROM ffprobe_metadata WHERE file_id = ?").get(fileId) as
    | {
        video_codec?: string;
      }
    | undefined;

  const startSecs = parseFloat((req.query.start as string) ?? "0") || 0;
  const streamId = (req.query.streamId as string | undefined) ?? "";

  const codec = probe?.video_codec ?? "unknown";
  console.log(
    `[video-stream] Transcoding ${fullPath} (${codec}) → mp4/h264 + watermark, start=${startSecs}s, streamId=${streamId || "(none)"}`
  );

  res.writeHead(200, {
    "Content-Type": "video/mp4",
    "Transfer-Encoding": "chunked",
    "Cache-Control": "no-cache",
  });

  // Escape colons for ffmpeg drawtext filter
  const fontEscaped = config.watermarkFontPath.replace(/:/g, "\\:");

  const watermark =
    `scale=1280:-2:force_original_aspect_ratio=decrease,format=yuv420p,` +
    `drawtext=fontfile='${fontEscaped}'` +
    ":text='%{pts\\:hms}'" +
    ":fontsize=h/10" +
    ":fontcolor=white@0.3" +
    ":x=(w-text_w)/2" +
    ":y=(h-text_h)/1.5";

  const ffmpegArgs: string[] = [];
  if (startSecs > 0) {
    ffmpegArgs.push("-ss", String(startSecs));
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
    "h264_nvenc",
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
    activeStreams.set(streamId, { ffmpeg, watchdog });
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
      console.log(`[ffmpeg] ${line.slice(0, 300)}`);
    }
  });
  ffmpeg.on("error", (err: Error) => {
    console.error("[ffmpeg] spawn error:", err.message);
    if (!res.headersSent) {
      res.status(500).send("ffmpeg not available");
    }
    cleanup("ffmpeg error");
  });
  ffmpeg.on("close", () => {
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
