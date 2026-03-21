// ---------------------------------------------------------------------------
// Server entry point — start the Express HTTP server
// ---------------------------------------------------------------------------

import { createApp } from "./app.js";
import { config } from "./config.js";
import { closeDb } from "./db.js";
import { ConsoleLogger } from "./logger.js";

const app = createApp();

const server = app.listen(config.port, "0.0.0.0", () => {
  ConsoleLogger.info(`Slater Film Catalog API`);
  ConsoleLogger.info(`Environment:  ${config.env}`);
  ConsoleLogger.info(`Listening:    http://127.0.0.1:${config.port}`);
  ConsoleLogger.info(`Database:     ${config.dbPath}`);
  ConsoleLogger.info(`Archive root: ${config.videoArchiveRoot}`);
  ConsoleLogger.info(`Log dir:      ${config.logDir}`);
  if (config.isProd) {
    ConsoleLogger.info(`Serving SPA:  ${config.viteDistDir}`);
  }
});

// Graceful shutdown
function shutdown(): void {
  ConsoleLogger.info("Shutting down…");
  server.close(() => {
    closeDb();
    process.exit(0);
  });
  // Force-kill after 5s if connections linger
  setTimeout(() => process.exit(1), 5000);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
