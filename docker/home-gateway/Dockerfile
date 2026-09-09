# =============================================================================
# docker/home-gateway/Dockerfile — Home Video Gateway container
#
# Same multi-stage layout as the catalog API image, but the runtime entrypoint
# is dist/gateway.js instead of dist/api.js. Includes ffmpeg + DejaVu fonts
# for the watermark burn-in pipeline.
# =============================================================================

# ---- Stage 1: Build --------------------------------------------------------
# Use Debian (trixie-slim) so better-sqlite3's native addon links against
# glibc — matching the runtime stage below.
FROM node:22-trixie-slim AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 make g++ \
  && rm -rf /var/lib/apt/lists/*

COPY package*.json ./
RUN npm ci

COPY . .

# Builds both api.js and gateway.js into .local/express/dist/
RUN npm run api:build

# ---- Stage 2: Runtime (Debian trixie-slim) ----------------------------------
# Debian's ffmpeg package includes h264_nvenc / hevc_nvenc via FFnvcodec
# (dlopen-based; libnvidia-encode.so.1 is injected at runtime by the NVIDIA
# Container Toolkit). better-sqlite3 was compiled above against glibc so it
# runs correctly here.
FROM node:22-trixie-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    fontconfig \
  && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.local/express/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY package.json ./

ENV NODE_ENV=production
ENV PORT=9302
ENV HOME_GATEWAY_ROLE=home

EXPOSE 9302

CMD ["node", "dist/gateway.js"]
