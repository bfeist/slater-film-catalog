// ---------------------------------------------------------------------------
// esbuild config — bundles src/server/ → .local/express/dist/api.js
// ---------------------------------------------------------------------------

import esbuild from "esbuild";

const watch = process.argv.includes("--watch");

/** @type {import('esbuild').BuildOptions} */
const options = {
  entryPoints: ["src/server/index.ts"],
  bundle: true,
  platform: "node",
  target: "node20",
  format: "esm",
  outfile: ".local/express/dist/api.js",
  sourcemap: true,
  // Native addons and CJS packages that can't be bundled into ESM
  external: ["better-sqlite3", "express"],
  // Let esbuild handle node: built-ins as imports, not require()
  packages: "external",
  logLevel: "info",
};

if (watch) {
  const ctx = await esbuild.context(options);
  await ctx.watch();
  console.log("[esbuild] Watching for changes…");
} else {
  await esbuild.build(options);
}
