# Production Host + Home Video Gateway Architecture Plan

_Drafted April 24, 2026._

## Summary

The application should be split into two runtime domains:

1. **Production catalog host** for the React app, catalog/search API, SQLite replica, and uploaded PDFs.
2. **Home video gateway** for the video archive mount and all proxy/transcode streaming.

This keeps the 80 TB archive at home while moving the browse/search experience onto a public production host.

This plan intentionally uses **Home Video Gateway** instead of "service worker" because a browser Service Worker is the wrong primitive here. The required component is a long-running server process or container on the home network that accepts signed stream requests and reads local video files.

The home gateway is also the recommended host for the shotlist PDF library so that thousands of PDF files do not have to be uploaded to production. When the home gateway is down, PDFs degrade in the same way video does, with a clear unavailable message in the UI.

Local development continues to run as a single Express process plus Vite, with no separate gateway container needed. The split between production catalog and home gateway is a deployment-time concern, not a developer-loop concern.

## Goals

- Move most of the application to a public production host.
- Keep the NASA video archive, ffmpeg streaming, and shotlist PDF library close to the home storage.
- Keep the main website up even when the home gateway is offline.
- Let public users browse metadata from production.
- Let approved users fetch PDFs and stream video directly from the home gateway, without mirroring the archive or PDF corpus to production.
- Deploy frontend, API image, and database snapshot through GitHub-based CI/CD.
- Reuse the existing production host Nginx instance that already serves other sites.
- Make local development work without any second container.

## Non-Goals

- No attempt to upload or mirror the 80 TB video corpus to production.
- No attempt to bulk-upload the shotlist PDF library to production. PDFs live where the source archive lives, at home.
- No attempt to make the production host proxy the full video byte stream by default.
- No attempt to make the home gateway a full copy of the current API surface.
- No attempt to require running two containers locally during development.

## Target Topology

```mermaid
flowchart LR
    U[User Browser]
    N[Nginx on Production Host]
    W[Built SPA Static Files]
    A[Catalog API Container]
    D[(SQLite Release Snapshot)]
    G[Home Video Gateway]
    O[/o/ Video Archive]
    P[Shotlist PDFs]

    U --> N
    N --> W
    N -->|/api/* metadata| A
    A --> D
    A -->|playback-start token + gateway URL| U
    A -->|pdf-access token + gateway URL| U
    U -->|direct HTTPS video stream| G
    U -->|direct HTTPS PDF fetch| G
    G --> O
    G --> P
    G -->|lookup against same release manifest or DB snapshot| D
```

## Proposed Runtime Split

### 1. Production catalog host

The production host becomes the public system of record for **metadata presentation**, not for video storage.

Responsibilities:

- Serve the built React SPA as static files through the host's existing Nginx.
- Run one backend Docker container for the catalog API.
- Mount a deployed copy of `catalog.db` read-only into the API container.
- Handle auth, search, reel detail, stats, and shotlist text requests.
- Request short-lived playback-start tokens from the home gateway.
- Request short-lived PDF-access tokens from the home gateway.
- Log user activity and stream session creation.

The production host should **not** mount `/o/`, should **not** run ffmpeg, and should **not** carry the bulk PDF corpus.

It should also be able to remain fully functional when the home gateway is unavailable. In that condition, the production host should continue serving search, metadata, and auth while marking video playback and PDF access as temporarily unavailable.

### 2. Home video gateway

The home gateway is a separate service running near the archive storage. It owns video streaming and the shotlist PDF library.

Responsibilities:

- Read the local video archive share read-only.
- Read the local shotlist PDF directory read-only.
- Accept only a narrow video- and PDF-oriented API surface.
- Validate short-lived playback-start tokens created via production.
- Validate short-lived PDF-access tokens created via production.
- Resolve a file from a release manifest or synced DB snapshot.
- Spawn ffmpeg for watermarked/transcoded streaming.
- Enforce playback-start expiry, heartbeat, and connection cleanup.
- Emit local stream logs.

Recommended surface:

- `GET /healthz`
- `GET /stream/:streamToken`
- `POST /internal/sessions`
- `POST /internal/sessions/:sessionId/renew`
- `POST /stream/heartbeat`
- `POST /stream/stop`
- `GET /pdf/:pdfToken`
- `POST /internal/pdf-tokens`

This service should not expose reel search, admin, or general catalog endpoints. The `/internal/*` endpoints must be reachable only from the production catalog API and gated by a shared secret.

## Route Ownership Map

The current `/api/video/*` and `/api/shotlist-pdf/*` surface splits like this:

| Endpoint                             | Owner            | Notes                                             |
| ------------------------------------ | ---------------- | ------------------------------------------------- |
| `GET  /api/video/:file_id/info`      | production       | DB lookup only; no file access required           |
| `POST /api/video/sessions`           | production (new) | Mints playback-start tokens via home gateway      |
| `POST /api/video/sessions/:id/renew` | production (new) | Refreshes playback-start tokens for seek/scrub    |
| `GET  /api/video/:file_id/stream`    | home (moves)     | ffmpeg + filesystem; replaced by `GET /stream/:t` |
| `GET  /api/video/heartbeat`          | home (moves)     | Keeps active stream alive                         |
| `POST /api/video/stop`               | home (moves)     | Explicit teardown                                 |
| `POST /api/pdf/sessions`             | production (new) | Mints PDF-access tokens via home gateway          |
| `GET  /api/shotlist-pdf/:filename`   | home (moves)     | Filesystem read; replaced by `GET /pdf/:t`        |
| `GET  /api/stats`                    | production       | DB-only                                           |
| `GET  /api/reels[...]`               | production       | DB-only                                           |
| `POST /api/auth/*`                   | production       | Auth authority                                    |

The SPA always calls production-side endpoints. Production returns short-lived tokens plus the home gateway base URL when actual file bytes are needed. The browser then makes a direct HTTPS request to the home gateway for those bytes.

## Request Flow

### Metadata and PDFs

1. Browser loads the SPA from production Nginx.
2. SPA calls the production catalog API for search, reel detail, stats, shotlist text, and PDF metadata.
3. Production API reads the deployed SQLite snapshot and local PDF directory.
4. Browser receives all non-video responses from production only.

### Video streaming

1. User opens a reel and chooses a transfer.
2. SPA calls a production endpoint such as `POST /api/video/sessions` with the selected file ID and desired start time.
3. Production API authenticates the user, verifies they are allowed to stream, and checks whether the home gateway is currently reachable.
4. If the home gateway is unavailable, production returns a clean `streaming_unavailable` response and the SPA shows that video streaming is temporarily offline while the rest of the site remains usable.
5. If the home gateway is available, production calls a home-gateway session endpoint over HTTPS using a shared secret between the two services.
6. Home gateway creates a short-lived playback-start token, valid for about 5 minutes to begin playback, and returns a session token or signed session URL.
7. Production returns that stream session payload and the home gateway base URL to the browser.
8. Browser loads the video directly from the home gateway over HTTPS.
9. Home gateway validates the token at playback start, resolves the file locally, and begins streaming the video.
10. Once playback has started, the stream may continue longer than 5 minutes; the 5-minute limit applies to session start, not total watch duration.
11. Browser heartbeat and stop events go to the home gateway, not to production.
12. When the user seeks, scrubs, or restarts playback after the start token has aged out, the SPA requests a renewed playback token from production and retries with the new session payload.
13. Home gateway may optionally post lightweight session-complete logs back to production, but that is not required for initial rollout.

The important design decision is that the browser should connect **directly** to the home gateway for the video bytes. If production proxies the stream, production becomes the bandwidth bottleneck and defeats the point of the split.

### PDFs

1. SPA requests PDF metadata from production (`/api/reels/:identifier/shotlist-pdfs`).
2. To open a PDF the SPA calls `POST /api/pdf/sessions` with the requested filename.
3. Production authenticates the user, verifies the filename is in the catalog, and checks home gateway health.
4. If the home gateway is unavailable, production returns `pdfs_unavailable` and the SPA disables PDF opens with a clear message.
5. Otherwise production calls home `POST /internal/pdf-tokens` over HTTPS with the shared secret.
6. Home returns a short-lived PDF-access token (similar lifetime to playback-start tokens, e.g. 5 minutes).
7. SPA loads the PDF directly from `https://<home-gateway>/pdf/:pdfToken`.
8. Home validates the token, returns the file with `Content-Type: application/pdf`, and applies the same `Content-Disposition: inline` and `Cache-Control: no-store` headers used today.

PDF-access tokens are simpler than video tokens because there is no heartbeat, no ffmpeg, and no seek behavior. Renewal is unnecessary; if a token expires the SPA just asks for a new one.

## Availability and Failure Mode

The system should treat video streaming as an optional subsystem, not as a requirement for basic site availability.

Required behavior:

- production search, reel detail, auth, and PDF access remain available even if the home gateway is down
- the UI shows a clear non-fatal message such as "Video streaming is currently unavailable"
- production should expose a small gateway-status signal so the SPA can disable or soften playback affordances before the user clicks play
- failed stream-session creation should not break the reel detail page or broader API responses
- expired playback-start tokens during seek or scrub should trigger silent token renewal, not a broken player state

Recommended production-side availability approach:

- keep a cached health state for the home gateway with a short TTL, such as 15 to 60 seconds
- check the home gateway `healthz` endpoint out-of-band instead of synchronously probing it on every page load
- still treat session-creation failures as authoritative even if the last cached health check was green

This gives the main site stable uptime even when the home machine reboots, loses internet, or the local streaming container crashes.

## Data Distribution Model

### Production-hosted data

Ship these artifacts to production on every release:

- Built SPA assets from Vite
- Backend Docker image
- `database/catalog.db`
- Optional release manifest with streamable file metadata

Production does **not** receive the PDF corpus or any video files.

### Home-hosted data

Keep these at home:

- `/o/` archive storage
- `static_assets/shotlist_pdfs/`
- ffmpeg runtime
- optional local copy of the same release manifest or DB snapshot used by production

### Recommended release bundle

Each deploy should create one logical release version containing:

- Git commit SHA (`RELEASE_VERSION`)
- built frontend assets
- catalog API image tag
- home gateway image tag
- SQLite snapshot
- stream manifest version

That version should be deployed to production and made available to the home gateway as the same release identifier. This avoids production issuing stream or PDF tokens for file IDs the home gateway cannot resolve.

## Local Development Mode

Local development should not require running both services as separate containers. The current `npm run dev` workflow (Vite on `:9300` + Express on `:9301`) should keep working unchanged.

How that is achieved:

- The Express server already implements every endpoint that will eventually be split.
- A single env var, `HOME_GATEWAY_BASE_URL`, controls whether the catalog API delegates to a remote gateway or serves video and PDFs itself.
- When `HOME_GATEWAY_BASE_URL` is unset, the catalog API runs in **monolithic mode**: `POST /api/video/sessions` skips the home call and the SPA gets a same-origin stream URL pointing at the local Express, exactly like today. PDFs work the same way.
- When `HOME_GATEWAY_BASE_URL` is set (production), the catalog API runs in **split mode** and goes through the home gateway for byte delivery.

This means:

| Mode                | How developer runs it                           | Where bytes come from                |
| ------------------- | ----------------------------------------------- | ------------------------------------ |
| Local dev           | `npm run dev`                                   | Local Express + local `/o/` mount    |
| Local dev with home | `npm run dev` + set `HOME_GATEWAY_BASE_URL=...` | Local home gateway container         |
| Production          | Production catalog container only               | Remote home gateway over HTTPS       |
| Home only           | `docker compose -f compose.home.yml up`         | Local files; serves prod and browser |

There should never be a case where running `npm run dev` requires you to also start a Docker container. If the gateway env var is missing, video and PDFs continue to work locally through Express.

### Compose layout

Recommend three compose files in the repo:

- `docker-compose.yml` — current local-first deployment, kept for backward compatibility during transition.
- `compose.prod.yml` — production-only stack: catalog API container, no archive mount, no PDFs, no `web` container.
- `compose.home.yml` — home gateway stack: video-gateway container with archive + PDFs mounted read-only.

## Environment Variable Matrix

The same codebase needs to behave differently in three environments. Here is the full matrix the implementation must support.

### Local dev (single Express process)

| Variable                     | Required | Example                                             | Notes                           |
| ---------------------------- | -------- | --------------------------------------------------- | ------------------------------- |
| `PORT`                       | yes      | `9301`                                              | Vite proxies `/api/*` here      |
| `DB_PATH`                    | yes      | `F:/_repos/slater-film-catalog/database/catalog.db` |                                 |
| `SHOTLIST_PDF_DIR`           | yes      | `F:/_repos/.../static_assets/shotlist_pdfs`         | Served by Express directly      |
| `LLM_OCR_DIR`                | yes      | `F:/_repos/.../static_assets/llm_ocr`               |                                 |
| `VIDEO_ARCHIVE_ROOT`         | yes      | `O:\\`                                              |                                 |
| `WATERMARK_FONT_PATH`        | yes      | OS default                                          |                                 |
| `WATERMARK_MONO_FONT_PATH`   | yes      | OS default                                          |                                 |
| `SLATER_SECRET`              | yes      | strong random                                       | Existing                        |
| `LOG_DIR`                    | no       | `.local/logs`                                       |                                 |
| `HOME_GATEWAY_BASE_URL`      | **no**   | empty                                               | Leave unset → monolithic mode   |
| `HOME_GATEWAY_SHARED_SECRET` | **no**   | empty                                               | Required only if `BASE_URL` set |

### Production catalog API container

| Variable                       | Required | Example                    | Notes                           |
| ------------------------------ | -------- | -------------------------- | ------------------------------- |
| `NODE_ENV`                     | yes      | `production`               |                                 |
| `PORT`                         | yes      | `9301`                     | Bound to `127.0.0.1` on host    |
| `DB_PATH`                      | yes      | `/app/database/catalog.db` | Read-only mount                 |
| `SLATER_SECRET`                | yes      | shared with prior installs |                                 |
| `AUTH_CONFIG_PATH`             | yes      | `/app/auth.config.json`    |                                 |
| `SERVE_FRONTEND`               | yes      | `false`                    | Host Nginx serves SPA           |
| `LOG_DIR`                      | yes      | `/app/logs`                |                                 |
| `HOME_GATEWAY_BASE_URL`        | **yes**  | `https://home.example.com` | Public URL of home gateway      |
| `HOME_GATEWAY_SHARED_SECRET`   | **yes**  | strong random              | Matches gateway value           |
| `HOME_GATEWAY_HEALTH_TTL_SECS` | no       | `30`                       | Cache window for `/healthz`     |
| `SHOTLIST_PDF_DIR`             | **no**   | unset                      | Production has no local PDFs    |
| `VIDEO_ARCHIVE_ROOT`           | **no**   | unset                      | Production has no local archive |
| `RELEASE_VERSION`              | yes      | git SHA from CI            | Sent to home with each session  |

### Home video gateway container

| Variable                     | Required | Example                                  | Notes                                       |
| ---------------------------- | -------- | ---------------------------------------- | ------------------------------------------- |
| `NODE_ENV`                   | yes      | `production`                             |                                             |
| `PORT`                       | yes      | `9302`                                   | Behind Nginx Proxy Manager                  |
| `DB_PATH`                    | yes      | `/app/database/catalog.db`               | Same snapshot as prod (Option A)            |
| `SHOTLIST_PDF_DIR`           | yes      | `/app/static_assets/shotlist_pdfs`       | Read-only mount                             |
| `VIDEO_ARCHIVE_ROOT`         | yes      | `/archive`                               | Read-only CIFS volume                       |
| `WATERMARK_FONT_PATH`        | yes      | DejaVu                                   |                                             |
| `WATERMARK_MONO_FONT_PATH`   | yes      | DejaVu                                   |                                             |
| `HOME_GATEWAY_SHARED_SECRET` | **yes**  | matches production                       | Authorizes `/internal/*`                    |
| `PUBLIC_ORIGIN`              | **yes**  | `https://slaterfilmcatalog.benfeist.com` | CORS allow-origin                           |
| `SESSION_TTL_SECS`           | no       | `300`                                    | Default playback-start window               |
| `PDF_TOKEN_TTL_SECS`         | no       | `300`                                    | Default PDF-access window                   |
| `RELEASE_VERSION`            | yes      | git SHA from CI                          | Validated against incoming session requests |
| `LOG_DIR`                    | yes      | `/app/logs`                              |                                             |

### Same-secret rule

`HOME_GATEWAY_SHARED_SECRET` must be identical between production and home for any traffic to authenticate. Treat it like a database password: rotate via deploy, never commit.

## Stream Manifest vs Full DB on the Home Gateway

There are two workable options.

### Option A. Home gateway reads a synced DB snapshot

Pros:

- Reuses current lookup logic.
- Lowest engineering effort.
- Lets the gateway resolve file paths from the same schema the API already uses.

Cons:

- Gives the gateway a larger runtime footprint than it needs.
- Couples the gateway to more of the catalog schema.

### Option B. Home gateway reads a generated stream manifest

Manifest contents per file should be limited to:

- stable file identifier
- reel identifier
- folder root mapping key
- relative path
- codec/resolution hints
- allowed stream policy fields

Pros:

- Smaller surface area.
- Easier to reason about and secure.
- Easier to version and validate across environments.

Cons:

- Requires a manifest build step.
- Requires a small amount of new logic on both sides.

**Recommendation:** start with **Option A** to shorten the migration, then move to **Option B** once the production/home split is stable.

## Stream Session Creation and Trust Boundary

The production API should remain the authentication authority.

Recommended initial pattern:

- Users authenticate against production exactly once.
- Production calls a home-gateway-only endpoint such as `POST /internal/sessions`.
- That endpoint is protected by a shared secret between production and home.
- The home gateway returns a short-lived playback-start token or pre-signed stream URL.
- The browser presents only that short-lived session to the home gateway.
- The home gateway trusts the session it created, not the browser's production login directly.

Important session semantics:

- the 5-minute expiry is a deadline to start playback, not a cap on stream length
- once playback has started, stream lifetime is governed by active connection state plus heartbeat timeout
- seeks and scrubs may require a renewed playback-start token if they cause the browser to start a fresh stream request after the original token has expired
- token renewal should be cheap and expected during normal player interaction

Recommended request fields from production to home:

- `fileId`
- `streamId`
- `start`
- `username` or user identifier for logging
- `releaseVersion`
- `expiresInSeconds` with an initial value of 300

Recommended renewal flow:

- the SPA calls `POST /api/video/sessions` for the initial stream start
- if playback fails because the start token has expired, or if a seek requires a new stream request, the SPA calls production again for a refreshed token
- production calls `POST /internal/sessions` or `POST /internal/sessions/:sessionId/renew` on the home gateway
- home returns a fresh playback-start token bound to the same file and updated start offset

This is simpler than having production mint a fully standalone cryptographic ticket itself. It also keeps session issuance logic colocated with the service that will actually enforce stream expiry.

Future option if needed:

- production can later mint its own signed tickets if you want the home gateway to remain more stateless
- that is a valid upgrade path, but it is not required for the first implementation

Recommended validation rules on the home gateway:

- reject expired playback-start tokens before stream creation
- reject malformed or unauthorized session-creation requests
- reject unknown or expired session tokens
- reject requests for files not present in the local manifest or DB snapshot
- optionally restrict one active connection per `streamId`
- enforce heartbeat timeout exactly as the current API does once playback is active

## Network and Security Requirements

### 1. The home gateway must be reachable from the public internet

If users are on the public internet, the browser must be able to reach the home gateway directly.

Implications:

- The home gateway needs a public hostname or stable IP path.
- If the ISP changes the IP, use dynamic DNS.
- If the ISP uses CGNAT or blocks inbound ports, use a reverse tunnel or VPN-based ingress.

### 2. The home gateway must use HTTPS

Because the main site will be served over HTTPS, the video endpoint must also be HTTPS to avoid mixed-content failures in browsers.

Recommended:

- use the existing Nginx Proxy Manager plus Let's Encrypt setup at home
- terminate TLS there
- forward only the streaming endpoints to the local gateway container
- keep the internal video-gateway container on the private home network only

### 3. Restrict the exposed surface

Only expose the narrow streaming API from home.

Do not expose:

- admin endpoints
- search endpoints
- raw DB download endpoints
- local filesystem paths

### 4. CORS and headers

If the SPA origin is on production and the video origin is at home, configure:

- `Access-Control-Allow-Origin` for the production site origin only (sourced from `PUBLIC_ORIGIN`)
- `Cross-Origin-Resource-Policy` consistent with video playback needs
- `Cache-Control: private, no-store` for signed stream and PDF endpoints
- These rules apply to both `/stream/*` and `/pdf/*`

This can be configured either:

- in the locally running video-gateway container itself, or
- in the reverse proxy layer in front of it

The cleaner default is to keep CORS policy in the video-gateway app so the rules travel with the service regardless of whether Nginx Proxy Manager is later replaced.

## Production Host Layout

The production host already has Nginx for several sites, so avoid replacing it with the current `web` container.

Recommended production layout:

- Host Nginx serves the static SPA directory for this site.
- Host Nginx proxies `/api/*` to the catalog API container bound on localhost.
- The current Docker `web` container is not used in production.
- The catalog API container binds only to `127.0.0.1`, for example `127.0.0.1:9311`.
- SQLite snapshot and PDFs live in host directories mounted read-only into the API container.

Suggested directories:

- `/srv/slater-film-catalog/current/web/`
- `/srv/slater-film-catalog/shared/catalog.db`
- `/srv/slater-film-catalog/shared/shotlist_pdfs/`
- `/srv/slater-film-catalog/shared/env/`
- `/srv/slater-film-catalog/compose/`

## Nginx Integration Plan

For the production host's existing Nginx:

- add a new site root for the SPA build output
- use `try_files` to route SPA paths to `index.html`
- proxy `/api/` to the local Docker API container
- keep all existing sites and virtual hosts unchanged

Conceptual routing:

- `/` -> static files in the release directory
- `/assets/*` -> static Vite assets
- `/api/*` -> `http://127.0.0.1:9311`

The production Nginx should not proxy the home video byte stream unless a temporary relay mode is needed for debugging.

## Docker Plan

### Production

Run one container:

- `catalog-api`

Remove in production:

- `web` container
- archive share mount

Keep:

- read-only DB mount
- read-only PDF mount
- writable log mount

### Home

Run one or two containers:

- `video-gateway`
- rely on the existing Nginx Proxy Manager for TLS termination and public routing

Keep the archive mount read-only and local to home only.

## GitHub CI/CD Plan

## Constraint that must shape the pipeline

GitHub-hosted runners will not have direct access to:

- the home SQLite source snapshot unless you upload it first
- the shotlist PDF directory unless it is packaged somewhere reachable
- the local archive share

Because of that, the deployment plan should use a **hybrid pipeline**.

### Recommended pipeline design

#### Workflow A. Build and publish application artifacts

Trigger:

- push to main
- manual dispatch

Runner:

- GitHub-hosted runner is fine

Steps:

1. run `npm ci`
2. run `npm run test:all`
3. build the SPA with `npm run build:vite`
4. build the catalog API container image and the home gateway container image
5. push both images to GHCR
6. upload the built SPA as a workflow artifact
7. publish a release manifest containing commit SHA, both image tags, and `RELEASE_VERSION`

#### Workflow B. Package data artifacts from home

Trigger:

- workflow dispatch
- or automatic after Workflow A completes

Runner:

- **self-hosted GitHub Actions runner at home**

Reason:

- it can read the local DB snapshot without copying it into GitHub first
- PDFs are no longer shipped to production; they stay on this machine

Steps:

1. check out the repo at the target commit
2. validate the local DB snapshot exists
3. optionally generate a stream manifest from the DB
4. package `catalog.db`
5. push `catalog.db` to production via rsync or upload as a release artifact
6. confirm the same `RELEASE_VERSION` is staged for both the production deploy and the local home gateway

#### Workflow C. Deploy to production host

Trigger:

- after Workflow A and Workflow B succeed

Runner:

- self-hosted runner at home or on the production host

Recommended steps:

1. pull the GHCR API image tag
2. copy the SPA build into the production site root
3. copy `catalog.db` into the production shared data directory
4. update the compose file or image tag reference
5. run `docker compose -f compose.prod.yml pull`
6. run `docker compose -f compose.prod.yml up -d`
7. reload Nginx
8. hit health checks for the static site and API

#### Workflow D. Deploy home gateway

Trigger:

- after Workflow A succeeds, manually or scheduled

Runner:

- self-hosted runner at home

Recommended steps:

1. pull the GHCR home-gateway image tag matching `RELEASE_VERSION`
2. confirm the locally mounted `catalog.db` matches the version pushed to production
3. run `docker compose -f compose.home.yml up -d`
4. hit `/healthz` from the production host to confirm reachability

### Why a self-hosted runner is the practical choice

Without a self-hosted runner or a separate source-side deploy machine, GitHub Actions has no native way to read the home-resident DB and PDF source tree. Since those assets are required for each public release, a self-hosted runner on the home network is the cleanest solution.

## Artifact Transfer Strategy

### Frontend assets

- small enough to publish as GitHub Actions artifacts
- deploy by rsync or SCP to the production host

### Backend container

- publish to GHCR
- pull on the production host during deploy

### SQLite database

- copy from home to production as part of deploy
- treat as a versioned release artifact
- use checksum verification after transfer

### PDFs

- not shipped to production
- served from the home gateway via short-lived PDF tokens
- if you ever want a hot-cache for PDFs on production, that is a future optimization, not part of v1

## Release Consistency Rules

To avoid split-brain behavior:

- the production API and home gateway should agree on the same release version
- stream tickets should include a release version claim when practical
- the home gateway should reject tickets for unknown release versions
- production deploy should not switch the site live until DB and PDFs for that release are in place

## Operational Plan

### Phase 1. Production split without changing video yet

- move SPA static hosting to the production host Nginx
- run only the catalog API container on production
- deploy DB snapshot and PDFs to production
- keep local video streaming available only in the home environment during this phase

### Phase 2. Extract the current `/api/video/*` logic into the home gateway

- move ffmpeg spawning and file resolution into the new gateway service
- let production request short-lived playback-start tokens from the home gateway via a shared-secret internal endpoint
- test direct browser playback from production site to home gateway
- add UI handling for `streaming_unavailable` so playback disables cleanly when home is offline
- add token refresh handling for seek, scrub, and replay actions

### Phase 3. Tighten the gateway surface

- replace direct DB lookups with a slimmer stream manifest if desired
- add rate limits, structured logs, and release-version validation
- add alerting for gateway unavailability

## Implementation Notes for This Repo

The current code already has the right initial seam:

- `src/server/routes/video.ts` is the behavior that should move to the home gateway
- `src/server/routes/shotlistPdf.ts` is the behavior that should move to the home gateway
- `src/api/client.ts` currently hardcodes video URLs under `/api/video/...`
- production should eventually change that flow so the client first requests a playback-start token from production, then loads the returned home-gateway URL

The current Docker setup should change like this:

- keep `docker/api/Dockerfile` for the production catalog API
- stop using `docker/web/Dockerfile` in production if host Nginx serves the SPA directly
- add a new `docker/home-gateway/Dockerfile` for the video and PDF gateway
- the home gateway image can reuse the existing API image with a different entrypoint that mounts only the gateway routes, or it can be a slimmer dedicated image

## Concrete Implementation Checklist

The following items, completed in order, are sufficient to implement this plan.

### Server code (catalog API)

1. Add `HOME_GATEWAY_BASE_URL`, `HOME_GATEWAY_SHARED_SECRET`, `HOME_GATEWAY_HEALTH_TTL_SECS`, `RELEASE_VERSION`, `PUBLIC_ORIGIN`, `SESSION_TTL_SECS`, `PDF_TOKEN_TTL_SECS` to `src/server/config.ts` with safe defaults.
2. Add a `gatewayMode` derived flag: `monolithic` when `HOME_GATEWAY_BASE_URL` is unset, `split` otherwise.
3. In monolithic mode, `/api/video/*` and `/api/shotlist-pdf/*` must continue to work exactly as today.
4. In split mode, register new endpoints:
   - `POST /api/video/sessions`
   - `POST /api/video/sessions/:id/renew`
   - `POST /api/pdf/sessions`
   - `GET  /api/gateway/status`
5. In split mode, `/api/video/:file_id/stream`, `/api/video/heartbeat`, `/api/video/stop`, and `/api/shotlist-pdf/:filename` must either be removed from production or return a redirect/error pointing the client at the gateway URL.
6. Implement an `httpGatewayClient` module that calls `POST /internal/sessions`, `POST /internal/sessions/:id/renew`, `POST /internal/pdf-tokens`, and `GET /healthz` with the shared secret in an `Authorization: Bearer ...` header.
7. Implement a small `gatewayHealth` cache with TTL controlled by `HOME_GATEWAY_HEALTH_TTL_SECS`.

### Home gateway service

1. Create `src/gateway/` (or a separate package) that exposes only the home routes from the surface table above.
2. Implement `POST /internal/sessions`, `POST /internal/sessions/:id/renew`, and `POST /internal/pdf-tokens`, all gated by `HOME_GATEWAY_SHARED_SECRET` via an `Authorization: Bearer <secret>` header check.
3. Implement `GET /stream/:streamToken` by reusing the existing ffmpeg pipeline from `src/server/routes/video.ts`.
4. Implement `GET /pdf/:pdfToken` by reusing the existing PDF-serving logic from `src/server/routes/shotlistPdf.ts`.
5. Implement an in-memory token store keyed by random opaque IDs with `expiresAt`, `fileId`/`filename`, `username`, `releaseVersion`, and `oneTimeUseRemaining` semantics.
6. Add `GET /healthz` returning `{ ok: true, releaseVersion }`.
7. Wire CORS to `PUBLIC_ORIGIN` exactly.

### Frontend

1. Update `src/api/client.ts` so `videoStreamUrl` is replaced by an async `requestVideoSession(fileId, startSecs)` returning `{ streamUrl, expiresAt }`.
2. Update `src/api/client.ts` so `shotlistPdfUrl` is replaced by an async `requestPdfSession(filename)` returning `{ pdfUrl, expiresAt }`.
3. Update the video player to call session creation on play and on seek, and to renew on `error` events that look like 401/403/expired.
4. Update the PDF viewer to call PDF session creation on open.
5. Add UI handling for `streaming_unavailable` and `pdfs_unavailable` so playback and PDF buttons disable cleanly with a tooltip.
6. In monolithic dev mode, all of the above still works because production endpoints simply return same-origin URLs.

### Docker and ops

1. Add `compose.prod.yml` (catalog API only, bound to `127.0.0.1:9311`).
2. Add `compose.home.yml` (gateway container with archive + PDFs read-only).
3. Add `docker/home-gateway/Dockerfile` (Node + ffmpeg + DejaVu fonts, similar to the current API image).
4. Document Nginx Proxy Manager rules at home: forward `https://<gateway-host>/{stream,pdf,healthz}` to the gateway container; do not expose `/internal/*`.
5. Document host Nginx rules for production: serve SPA from disk, proxy `/api/*` to `127.0.0.1:9311`.

### CI

1. Add Workflow A (build + publish images to GHCR + upload SPA artifact).
2. Add Workflow B (self-hosted at home: rsync `catalog.db` to production).
3. Add Workflow C (production deploy: pull image, swap SPA, restart compose).
4. Add Workflow D (home deploy: pull image, restart compose).
5. All workflows pass the same `RELEASE_VERSION` so version mismatches cause clean failures rather than silent bugs.

### Done criteria

- `npm run dev` works exactly like today with no gateway env vars set.
- Production users can browse, search, and view metadata even when the home gateway is unreachable.
- Video playback in production goes browser → home gateway directly.
- PDF viewing in production goes browser → home gateway directly.
- The home machine going offline does not cause production to return 5xx for any non-video, non-PDF request.
- No PDF or video file is uploaded to production as part of any deploy.

## Risks and Mitigations

### Home uplink bandwidth

Risk:

- multiple users may saturate the home upstream connection

Mitigation:

- limit concurrent streams
- prefer proxy derivatives over mezzanine files
- add bitrate caps in ffmpeg presets

### Home IP instability

Risk:

- dynamic IP changes break playback

Mitigation:

- use dynamic DNS
- optionally front the home gateway with a tunnel or VPS relay only for control-plane stability, not bulk storage

### Home gateway downtime

Risk:

- the home machine may be offline while the production host remains healthy

Mitigation:

- treat streaming as a degradable subsystem
- keep cached gateway health on production
- return an explicit `streaming_unavailable` state from session creation
- keep the main site and PDFs fully functional during gateway outages

### Mixed-version deploys

Risk:

- production issues tickets for content the home gateway cannot resolve

Mitigation:

- version release artifacts together
- validate release ID on stream ticket redemption

### Public exposure of home network service

Risk:

- expanded attack surface

Mitigation:

- expose only the stream gateway
- require signed short-lived tokens
- terminate TLS
- firewall to only required ports
- keep the archive mount read-only

### Token expiry during active viewing

Risk:

- users often pause, scrub, and restart requests after the original playback-start token has expired

Mitigation:

- make the token a short-lived start authorization, not a hard session-duration cap
- keep active playback alive via connection state and heartbeat
- support fast token renewal through production for seek and replay actions

## Recommended Next Deliverables

1. Add a deployment-oriented architecture diagram to `docs/architecture.md` after this plan is approved.
2. Implement a release manifest generator for streamable files.
3. Add a GitHub Actions workflow pair: build-on-GitHub plus deploy-from-home-runner.
4. Extract `src/server/routes/video.ts` into a dedicated home gateway service.
