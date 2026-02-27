import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ---------------------------------------------------------------------------
// In development, Vite proxies /api/* requests to the Express server running
// on port 3001.  In production, Express serves the built SPA directly — no
// Vite process is involved.
// ---------------------------------------------------------------------------

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: ".local/vite/dist",
  },
  server: {
    host: "0.0.0.0",
    port: 9300,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:3001",
        changeOrigin: true,
      },
    },
    allowedHosts: ["localhost", "nasaslatercatalog.benfeist.com"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
