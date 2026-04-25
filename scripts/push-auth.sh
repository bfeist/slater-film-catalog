#!/usr/bin/env bash
# Push auth.config.json to production app root.
# Usage: ./scripts/push-auth.sh [ssh-key-path]
#
# Environment overrides (optional):
#   PROD_USER, PROD_HOST, PROD_PATH_APPROOT, PROD_SSH_KEY

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"
if [ -f "$ENV_FILE" ]; then
  for _var in PROD_USER PROD_HOST PROD_PATH_APPROOT PROD_SSH_KEY; do
    _val="$(grep -E "^${_var}=" "$ENV_FILE" | tail -1 | cut -d= -f2-)"
    [ -n "$_val" ] && export "${_var}=${_val}"
  done
  unset _var _val
fi

PROD_USER="${PROD_USER:-bfeist}"
PROD_HOST="${PROD_HOST:-162.246.19.235}"
PROD_PATH_APPROOT="${PROD_PATH_APPROOT:-/home/bfeist/slater-film-catalog-server/app}"
SSH_KEY="${1:-${PROD_SSH_KEY:-$HOME/.ssh/id_deploy}}"
SSH_KEY="${SSH_KEY/#\~/$HOME}"

if [ -x "/c/Windows/System32/OpenSSH/ssh.exe" ]; then
  SSH_BIN="/c/Windows/System32/OpenSSH/ssh.exe"
  SCP_BIN="/c/Windows/System32/OpenSSH/scp.exe"
else
  SSH_BIN="ssh"
  SCP_BIN="scp"
fi

AUTH="auth.config.json"

if [ ! -f "$AUTH" ]; then
  echo "ERROR: $AUTH not found. Run this from the repo root." >&2
  exit 1
fi

echo "Uploading $AUTH to $PROD_USER@$PROD_HOST:$PROD_PATH_APPROOT/$AUTH"

$SCP_BIN -i "$SSH_KEY" "$AUTH" "$PROD_USER@$PROD_HOST:$PROD_PATH_APPROOT/$AUTH"

echo "Done."
