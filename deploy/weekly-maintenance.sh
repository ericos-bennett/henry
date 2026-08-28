#!/usr/bin/env bash
#
# Weekly housekeeping for the home-server deployment: dump the database and prune
# old raw HTML snapshots. Installed into the deploying user's crontab by
# server-start.sh (via deploy/maintenance-cron.sh) and removed by server-stop.sh.
#
# Safe to run by hand any time.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== henry weekly-maintenance $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="

# 1. Database dump. Reuses backup-db.sh: writes henry-<stamp>-weekly.dump into
#    $HENRY_BACKUP_DIR (default ~/backups/henry) and keeps the 10 most recent
#    dumps across all labels.
"$REPO_ROOT/deploy/backup-db.sh" weekly

# 2. Prune raw HTML snapshots older than the retention window.
set -a
[ -f "$REPO_ROOT/backend/.env" ] && source "$REPO_ROOT/backend/.env"
set +a
"$REPO_ROOT/clear-snapshots.sh" "${HENRY_SNAPSHOT_RETENTION_DAYS:-7}"

echo "=== weekly-maintenance done ==="
