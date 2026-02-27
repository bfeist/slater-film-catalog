// ---------------------------------------------------------------------------
// /api/shotlist-pdf/:filename — serve scanned shotlist PDFs
// ---------------------------------------------------------------------------

import { Router } from "express";
import path from "node:path";
import fs from "node:fs";
import { config } from "../config.js";

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
  res.setHeader("Content-Type", "application/pdf");
  res.setHeader("Content-Length", stat.size);
  res.setHeader("Content-Disposition", `inline; filename="${filename}"`);
  fs.createReadStream(pdfPath).pipe(res);
});

export default router;
