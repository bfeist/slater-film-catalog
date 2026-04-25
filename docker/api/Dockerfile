# =============================================================================
# docker/api/Dockerfile — Express API container
#
# Stage 1 (builder): installs all deps and compiles the esbuild server bundle.
# Stage 2 (runner):  lean Node image that runs api.js.
#
# Build context must be the project root (set in docker-compose.yml):
#   docker build -f docker/api/Dockerfile .
# =============================================================================

# ---- Stage 1: Build --------------------------------------------------------
FROM node:22-alpine AS builder
WORKDIR /app

# Enable native addon compilation (required for better-sqlite3)
RUN apk add --no-cache python3 make g++

# Install all dependencies (including devDeps for the build tools)
COPY package*.json ./
RUN npm ci

# Copy source tree
COPY . .

# Compile: esbuild bundles src/server/ → .local/express/dist/api.js
RUN npm run api:build

# ---- Stage 2: Runtime ------------------------------------------------------
FROM node:22-alpine
WORKDIR /app

# Copy the compiled bundle + native node_modules from builder
COPY --from=builder /app/.local/express/dist ./dist
COPY --from=builder /app/node_modules ./node_modules

# package.json is used by findProjectRoot() in config.ts
COPY package.json ./

ENV NODE_ENV=production
ENV PORT=9301

EXPOSE 9301

CMD ["node", "dist/api.js"]
