#!/usr/bin/env bash
#
# Snapshot the Henry Postgres database with pg_dump. Called by server-start.sh
# (before migrations), server-stop.sh, and infra/maintenance.sh. Keeps the 10
# most recent dumps in $HENRY_BACKUP_DIR/db (default ~/backups/henry/db) and
# prunes older ones.
#
# Usage:  infra/backup-db.sh [label]
#   label is an optional filename suffix (e.g. "deploy", "teardown", "weekly").
#
# Exits non-zero if the dump fails - callers decide whether that's fatal.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="${1:-}"

set -a
[ -f "$REPO_ROOT/backend/.env" ] && source "$REPO_ROOT/backend/.env"
set +a

[ -n "${DATABASE_URL:-}" ] || { echo "ERROR: DATABASE_URL not set in backend/.env" >&2; exit 1; }
command -v pg_dump >/dev/null || { echo "ERROR: pg_dump not found on PATH" >&2; exit 1; }

BACKUP_DIR="${HENRY_BACKUP_DIR:-$HOME/backups/henry}/db"
mkdir -p "$BACKUP_DIR"

stamp="$(date +%Y%m%d-%H%M%S)"
dump="$BACKUP_DIR/henry-${stamp}${LABEL:+-$LABEL}.dump"

echo "==> Backing up database -> $dump"
if ! pg_dump "$DATABASE_URL" -Fc -f "$dump"; then
	echo "ERROR: pg_dump failed" >&2
	rm -f "$dump"
	exit 1
fi

# Keep the 10 most recent dumps, prune the rest.
ls -1t "$BACKUP_DIR"/henry-*.dump 2>/dev/null | tail -n +11 | xargs -r rm -f

count="$(ls -1 "$BACKUP_DIR"/henry-*.dump 2>/dev/null | wc -l | tr -d ' ')"
echo "    $count dump(s) in $BACKUP_DIR"
