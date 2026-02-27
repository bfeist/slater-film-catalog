// ---------------------------------------------------------------------------
// Server entry point — start the Express HTTP server
// ---------------------------------------------------------------------------

import { createApp } from "./app.js";
import { config } from "./config.js";
import { closeDb } from "./db.js";

const app = createApp();

const server = app.listen(config.port, "0.0.0.0", () => {
  console.log(`\n  NASA Slater Catalog API`);
  console.log(`  Environment:  ${config.env}`);
  console.log(`  Listening:    http://127.0.0.1:${config.port}`);
  console.log(`  Database:     ${config.dbPath}`);
  console.log(`  Archive root: ${config.videoArchiveRoot}`);
  if (config.isProd) {
    console.log(`  Serving SPA:  ${config.viteDistDir}`);
  }
  console.log();
});

// Graceful shutdown
function shutdown(): void {
  console.log("\n[server] Shutting down…");
  server.close(() => {
    closeDb();
    process.exit(0);
  });
  // Force-kill after 5s if connections linger
  setTimeout(() => process.exit(1), 5000);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
