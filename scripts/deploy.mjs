#!/usr/bin/env node
// =============================================================================
// scripts/deploy.mjs — local production deploy pipeline
//
// Usage:  npm run deploy
//         npm run deploy -- --fresh     rebuild from scratch (no cache)
//         npm run deploy -- --verbose   full docker build output
//
// Steps:
//   1. Verify .env.docker exists (copies from .env.docker.example if absent)
//   2. Load VIDEO_ARCHIVE_HOST_PATH from .env.docker for compose interpolation
//   3. Build Docker images (multi-stage, --no-cache optional via --fresh flag)
//   4. Start containers detached
// =============================================================================

import { spawnSync, spawn } from "node:child_process";
import readline from "node:readline";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const FRESH = process.argv.includes("--fresh");
const VERBOSE = process.argv.includes("--verbose");

// Simple synchronous runner — used for non-build commands (up, down, etc.)
function run(cmd, extraEnv = {}) {
  console.log(`\n  > ${cmd}\n`);
  const result = spawnSync(cmd, {
    shell: true,
    stdio: "inherit",
    cwd: ROOT,
    env: { ...process.env, ...extraEnv },
  });
  if (result.status !== 0) {
    console.error(`\n  [deploy] Command failed (exit ${result.status}): ${cmd}`);
    process.exit(result.status ?? 1);
  }
}

// BuildKit output filter — suppress the noisy timestamped step-internal lines
// (#N X.XXX ...) while keeping stage headers, completions, and the final summary.
function isBuildKitNoise(line) {
  if (!line.match(/^#\d+/)) return false; // not a BuildKit line — keep
  if (line.match(/^#\d+ \[/)) return false; // stage header — keep
  if (line.match(/^#\d+ (DONE|CACHED|ERROR)\b/)) return false; // completion — keep
  return true; // everything else — suppress
}

// Streaming runner for `docker compose build` with filtered output.
// Falls back to full unfiltered output with --verbose flag.
async function runBuild(cmd, extraEnv = {}) {
  console.log(`\n  > ${cmd}\n`);

  if (VERBOSE) {
    run(cmd, extraEnv);
    return;
  }

  await new Promise((resolve) => {
    const child = spawn(cmd, {
      shell: true,
      stdio: ["ignore", "pipe", "pipe"],
      cwd: ROOT,
      env: { ...process.env, ...extraEnv },
    });

    function handleLine(line) {
      if (!isBuildKitNoise(line)) {
        const trimmed = line.trimEnd();
        if (trimmed) console.log("  " + trimmed);
      }
    }

    readline.createInterface({ input: child.stdout, crlfDelay: Infinity }).on("line", handleLine);
    readline.createInterface({ input: child.stderr, crlfDelay: Infinity }).on("line", handleLine);

    child.on("close", (code) => {
      if (code !== 0) {
        console.error(
          `\n  [deploy] Build failed (exit ${code}). Re-run with --verbose for full output.`
        );
        process.exit(code ?? 1);
      }
      resolve();
    });
  });
}

async function main() {
  // ---------------------------------------------------------------------------
  // 1. Ensure .env.docker exists
  // ---------------------------------------------------------------------------
  const envDockerPath = path.join(ROOT, ".env.docker");
  const envDockerExample = path.join(ROOT, ".env.docker.example");

  if (!fs.existsSync(envDockerPath)) {
    if (fs.existsSync(envDockerExample)) {
      fs.copyFileSync(envDockerExample, envDockerPath);
      console.log(`\n  [deploy] Created .env.docker from .env.docker.example`);
      console.log(`           Review it and adjust SLATER_SECRET before continuing.\n`);
    } else {
      console.error(`\n  [deploy] .env.docker not found. Create it from .env.docker.example.\n`);
      process.exit(1);
    }
  }

  // ---------------------------------------------------------------------------
  // 2. Parse .env.docker to extract vars needed for docker compose interpolation
  //    (docker compose reads shell env for ${VAR} substitution in the YAML file,
  //     not the env_file section — so we forward them explicitly)
  // ---------------------------------------------------------------------------
  const envVars = {};
  const envDockerContents = fs.readFileSync(envDockerPath, "utf8");
  for (const line of envDockerContents.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    envVars[trimmed.slice(0, eq).trim()] = trimmed.slice(eq + 1).trim();
  }

  const composeEnv = {};
  if (envVars.VIDEO_ARCHIVE_HOST_PATH) {
    composeEnv.VIDEO_ARCHIVE_HOST_PATH = envVars.VIDEO_ARCHIVE_HOST_PATH;
  }

  // ---------------------------------------------------------------------------
  // 3. Build images
  // ---------------------------------------------------------------------------
  console.log("\n  [deploy] Building Docker images…");

  const buildArgs = FRESH ? "--no-cache" : "";
  await runBuild(`docker compose build ${buildArgs}`, composeEnv);

  // ---------------------------------------------------------------------------
  // 4. Start containers (detached)
  // ---------------------------------------------------------------------------
  console.log("\n  [deploy] Starting containers…");
  run("docker compose up -d", composeEnv);

  // ---------------------------------------------------------------------------
  // Done
  // ---------------------------------------------------------------------------
  console.log(`
  [deploy] Containers started.

  Production app  →  http://localhost:9310
  API (debug)     →  http://localhost:9311/api/stats

  docker compose logs -f          tail all logs
  docker compose logs -f api      tail API logs only
  docker compose down             stop everything
  npm run deploy -- --fresh       rebuild from scratch (no cache)
  npm run deploy -- --verbose     full docker build output
`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
