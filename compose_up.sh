#!/usr/bin/env bash
# Start the production stack.
# Run from the app root on the production host.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

docker compose -f compose.prod.yml --env-file .env.prod --env-file .env.deploy pull
docker compose -f compose.prod.yml --env-file .env.prod --env-file .env.deploy up -d
sudo systemctl reload nginx || true
