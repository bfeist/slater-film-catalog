#!/usr/bin/env bash
# Push a fresh database/catalog.db snapshot to production.
# Usage: ./scripts/push-db.sh [ssh-key-path]
#
# Environment overrides (optional):
#   PROD_USER, PROD_HOST, PROD_PATH_DB, PROD_SSH_KEY

set -euo pipefail

# Load specific prod-deploy vars from .env (avoids executing unquoted values like NAS_SHARE)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"
if [ -f "$ENV_FILE" ]; then
  for _var in PROD_USER PROD_HOST PROD_PATH_DB PROD_SSH_KEY; do
    _val="$(grep -E "^${_var}=" "$ENV_FILE" | tail -1 | cut -d= -f2-)"
    [ -n "$_val" ] && export "${_var}=${_val}"
  done
  unset _var _val
fi

PROD_USER="${PROD_USER:-bfeist}"
PROD_HOST="${PROD_HOST:-162.246.19.235}"
PROD_PATH_DB="${PROD_PATH_DB:-/home/bfeist/slater-film-catalog-server/db}"
# Expand ~ manually so it works inside double-quoted strings
SSH_KEY="${1:-${PROD_SSH_KEY:-$HOME/.ssh/id_deploy}}"
SSH_KEY="${SSH_KEY/#\~/$HOME}"

# Prefer Windows system OpenSSH (handles modern key formats better than Git Bash's bundled ssh)
if [ -x "/c/Windows/System32/OpenSSH/ssh.exe" ]; then
  SSH_BIN="/c/Windows/System32/OpenSSH/ssh.exe"
  SCP_BIN="/c/Windows/System32/OpenSSH/scp.exe"
else
  SSH_BIN="ssh"
  SCP_BIN="scp"
fi

DB="database/catalog.db"

if [ ! -f "$DB" ]; then
  echo "ERROR: $DB not found. Run this from the repo root." >&2
  exit 1
fi

echo "Uploading $DB ($(du -sh "$DB" | cut -f1)) to $PROD_USER@$PROD_HOST:$PROD_PATH_DB/"

$SCP_BIN -i "$SSH_KEY" "$DB" "$PROD_USER@$PROD_HOST:$PROD_PATH_DB/catalog.db.new"

$SSH_BIN -i "$SSH_KEY" "$PROD_USER@$PROD_HOST" \
  "python3 -c \"import sqlite3, sys; c=sqlite3.connect('$PROD_PATH_DB/catalog.db.new'); r=c.execute('PRAGMA integrity_check').fetchone()[0]; sys.exit(0 if r=='ok' else 1)\" \
    || { echo 'ERROR: integrity_check failed on uploaded DB — aborting mv' >&2; rm -f $PROD_PATH_DB/catalog.db.new; exit 1; } && \
   rm -rf $PROD_PATH_DB/catalog.db && \
   mv $PROD_PATH_DB/catalog.db.new $PROD_PATH_DB/catalog.db && echo 'Done.'"
