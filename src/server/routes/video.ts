// ---------------------------------------------------------------------------
// /api/video/:file_id/* — video info + transcoded stream with watermark
// ---------------------------------------------------------------------------

import { Router } from "express";
import path from "node:path";
import fs from "node:fs";
import { spawn, type ChildProcess } from "node:child_process";
import { getDb } from "../db.js";
import { config } from "../config.js";

const router = Router();

// ---- GET /api/video/:file_id/info ----
router.get("/:file_id/info", (req, res) => {
  const d = getDb();
  const fileId = parseInt(req.params.file_id, 10);
  const file = d.prepare("SELECT * FROM files_on_disk WHERE id = ?").get(fileId);
  if (!file) {
    res.status(404).json({ error: "File not found" });
    return;
  }
  const probe = d.prepare("SELECT * FROM ffprobe_metadata WHERE file_id = ?").get(fileId);
  res.json({ file, probe });
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

  const codec = probe?.video_codec ?? "unknown";
  console.log(
    `[video-stream] Transcoding ${fullPath} (${codec}) → mp4/h264 + watermark, start=${startSecs}s`
  );

  res.writeHead(200, {
    "Content-Type": "video/mp4",
    "Transfer-Encoding": "chunked",
    "Cache-Control": "no-cache",
  });

  // Escape colons for ffmpeg drawtext filter
  const fontEscaped = config.watermarkFontPath.replace(/:/g, "\\:");

  const watermark =
    `drawtext=fontfile='${fontEscaped}'` +
    ":text='STEPHEN SLATER PRODUCTIONS'" +
    ":fontsize=h/12" +
    ":fontcolor=white@0.3" +
    ":x=(w-text_w)/2" +
    ":y=(h-text_h)/2";

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
    "libx264",
    "-preset",
    "ultrafast",
    "-crf",
    "23",
    "-c:a",
    "aac",
    "-ac",
    "2",
    "-b:a",
    "128k",
    "-movflags",
    "frag_keyframe+empty_moov+default_base_moof",
    "-f",
    "mp4",
    "pipe:1",
  ]);

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
  });
  ffmpeg.on("close", () => {
    res.end();
  });

  // Kill ffmpeg if client disconnects
  req.on("close", () => {
    ffmpeg.kill("SIGTERM");
  });
});

export default router;
