# Home Gateway — Local Test & Deployment Runbook

Companion to [docs/production-home-gateway-architecture-plan.md](production-home-gateway-architecture-plan.md). Use this when you need to actually run the split (catalog API + home gateway) topology.

---

## Mode model

The same codebase runs in three modes, picked from environment at startup:

| Mode         | How it's selected                                          | Purpose                                                                          |
| ------------ | ---------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `monolithic` | `HOME_GATEWAY_BASE_URL` unset                              | Default. `npm run dev` works exactly like before.                                |
| `catalog`    | `HOME_GATEWAY_BASE_URL` + `HOME_GATEWAY_SHARED_SECRET` set | API mints session tokens and forwards video/PDF requests to the home gateway.    |
| `home`       | `HOME_GATEWAY_ROLE=home`                                   | Runs [src/gateway/index.ts](../src/gateway/index.ts) instead of the catalog API. |

---

## A. Continue developing locally (zero-effort)

**Do nothing.** `npm run dev` still works as before. Existing `.env` already has the local DB, archive, and PDF paths, and because `HOME_GATEWAY_BASE_URL` is unset the API stays in `monolithic` mode. `<VideoPlayer>` / `<ShotlistPdfViewer>` now request a session first, but in monolithic mode the session immediately returns the same same-origin URLs as before.

---

## B. Local split-mode test (Docker for the gateway, same image as prod)

The gateway always runs in Docker — locally and in production — from the single [compose.home.yml](../compose.home.yml) file. The archive is mounted via CIFS in both environments; locally that means pointing `NAS_*` at your NAS the same way prod does.

### One-time setup

```bash
cp .env.home.example .env.home
```

Edit [.env.home](../.env.home.example) and set:

- `HOME_GATEWAY_SHARED_SECRET` — any random value; must match the catalog's value below.
- `SLATER_SECRET` — same value as your main `.env` so DB HMACs validate.
- `PUBLIC_ORIGIN=http://localhost:9300` — Vite's origin (the only origin the browser sees).
- `NAS_HOST` — NAS address used for the read-only NFS archive mount.
- `NFS_EXPORT_PATH` — exported NFS path (defaults to `/mnt/user/NASA Archive`).

Add the matching catalog-side env to your main `.env`:

```bash
HOME_GATEWAY_BASE_URL=http://localhost:9302
HOME_GATEWAY_SHARED_SECRET=<same value as .env.home>
RELEASE_VERSION=dev
```

### Run

Terminal 1 — catalog API + Vite (catalog mode, no `/stream`, no `/api/shotlist-pdf`):

```bash
npm run dev
```

Terminal 2 — home gateway in Docker (same image as prod):

```bash
npm run gateway:up      # builds slater-home-gateway:local, starts container
npm run gateway:logs    # tail logs
# ...
npm run gateway:down
```

### Verify

```bash
curl http://localhost:9302/healthz
curl http://localhost:9301/api/gateway/status        # { available: true }
```

In the UI:

- Click a reel → video plays, proxied through `:9302/stream/<token>`.
- Open a shotlist → PDF loads from `:9302/pdf/<token>`.
- Stop the gateway (`npm run gateway:down`) → video/PDF show "temporarily unavailable", catalog still browses.

---

## C. First production deploy

### 1. Generate a real shared secret

```bash
openssl rand -base64 48
```

Use the same value in both `.env.prod` (production catalog) and `.env.home` (home gateway).

### 2. Production host setup

- Copy [.env.prod.example](../.env.prod.example) → `.env.prod`. Fill in `HOME_GATEWAY_BASE_URL` (your home's public URL), `HOME_GATEWAY_SHARED_SECRET`, `SLATER_SECRET`, `RELEASE_VERSION`.
- Make sure `database/catalog.db` exists (Workflow B will populate it).
- Configure host Nginx: serve `web/` as the SPA; proxy `/api/*` → `127.0.0.1:9311`.
- First boot:
  ```bash
  docker compose -f compose.prod.yml --env-file .env.prod up -d
  ```

### 3. Home host setup

- Copy [.env.home.example](../.env.home.example) → `.env.home`. Fill in:
  - `HOME_GATEWAY_SHARED_SECRET` — same as prod.
  - `SLATER_SECRET` — same as prod.
  - `PUBLIC_ORIGIN` — production site URL (e.g. `https://slaterfilmcatalog.benfeist.com`).
  - `NAS_HOST` and optional `NFS_EXPORT_PATH` are read by [compose.home.yml](../compose.home.yml) to mount the archive read-only over NFS.
- Make sure `database/catalog.db` and `static_assets/shotlist_pdfs/` are present.
- First boot:
  ```bash
  docker compose -f compose.home.yml --env-file .env.home up -d
  ```
- Configure Nginx Proxy Manager: forward your public hostname → `<home-host>:9302`.
  - **Allow** `/healthz`, `/stream/*`, `/pdf/*`.
  - **Block** `/internal/*` (it's secret-guarded but defence-in-depth).

### 4. GitHub repo settings

Add secrets: `PROD_HOST`, `PROD_USER`, `PROD_PATH`, `PROD_SSH_KEY`. Register a self-hosted runner at home labelled `home` (used by Workflows B and D).

### 5. First release flow

1. Push to `main` → Workflow A builds images + SPA artifact.
2. Run Workflow B (manual) → ships current `database/catalog.db` to prod.
3. Run Workflow C with the release version → swaps SPA + restarts catalog API.
4. Run Workflow D with the same release version → restarts home gateway.

---

## D. Pre-flight checklist

- [ ] Both `HOME_GATEWAY_SHARED_SECRET` values match exactly (no trailing newline).
- [ ] `PUBLIC_ORIGIN` on the gateway is the **frontend** origin, not the API origin.
- [ ] Production host can reach `HOME_GATEWAY_BASE_URL` over HTTPS — `curl https://<home>/healthz`.
- [ ] DB on home and prod are the **same release**. Workflow D warns if `.last-shipped-release` doesn't match.

---

## E. File reference

| Concern                    | File                                                                  |
| -------------------------- | --------------------------------------------------------------------- |
| Mode + env config          | [src/server/config.ts](../src/server/config.ts)                       |
| Shared ffmpeg pipeline     | [src/server/streamingPipeline.ts](../src/server/streamingPipeline.ts) |
| Catalog → home HTTP client | [src/server/gatewayClient.ts](../src/server/gatewayClient.ts)         |
| Session mint routes        | [src/server/routes/sessions.ts](../src/server/routes/sessions.ts)     |
| Gateway entry              | [src/gateway/index.ts](../src/gateway/index.ts)                       |
| Gateway routes             | [src/gateway/routes.ts](../src/gateway/routes.ts)                     |
| Gateway token store        | [src/gateway/tokens.ts](../src/gateway/tokens.ts)                     |
| Frontend session API       | [src/api/client.ts](../src/api/client.ts)                             |
| Production catalog stack   | [compose.prod.yml](../compose.prod.yml)                               |
| Home gateway stack         | [compose.home.yml](../compose.home.yml)                               |
| Gateway image              | [docker/home-gateway/Dockerfile](../docker/home-gateway/Dockerfile)   |
| CI workflows               | [.github/workflows/](../.github/workflows/)                           |
