// ---------------------------------------------------------------------------
// /api/shotlist-pdf/:filename — serve scanned shotlist PDFs
// ---------------------------------------------------------------------------

import { Router } from "express";
import path from "node:path";
import fs from "node:fs";
import { config } from "../config.js";
import { logActivity } from "../logger.js";
import { getRequestUser } from "../slater.js";

const router = Router();

router.get("/:filename", (req, res) => {
  const filename = req.params.filename;

  // Sanitize: only allow .pdf files, no path traversal
  if (
    !filename.endsWith(".pdf") ||
    filename.includes("/") ||
    filename.includes("\\") ||
    filename.includes("..")
  ) {
    res.status(400).json({ error: "Invalid filename" });
    return;
  }

  const pdfPath = path.join(config.shotlistPdfDir, filename);
  if (!fs.existsSync(pdfPath)) {
    res.status(404).json({ error: "PDF not found" });
    return;
  }

  const stat = fs.statSync(pdfPath);
  logActivity({
    action: "generate_shotlist_pdf",
    username: getRequestUser(req),
    details: `file=${filename}`,
  });
  res.setHeader("Content-Type", "application/pdf");
  res.setHeader("Content-Length", stat.size);
  // Serve inline with no filename exposed — prevents the browser or HTTP layer
  // from leaking the real filename to unauthenticated users.
  res.setHeader("Content-Disposition", "inline");
  res.setHeader("Cache-Control", "no-store");
  fs.createReadStream(pdfPath).pipe(res);
});

export default router;
