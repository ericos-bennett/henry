#!/usr/bin/env bash
#
# Delete raw HTML scrape snapshots under backend/data/<company_id>/raw/ and prune
# any directories left empty.
#
#   infra/clear-snapshots.sh        delete every snapshot
#   infra/clear-snapshots.sh 7      delete only snapshots older than 7 days
#
# infra/weekly-maintenance.sh calls this with a retention window; run it with no
# argument for a full wipe.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DATA_DIR="$REPO_ROOT/backend/data"
DAYS="${1:-}"

mtime_args=()
[ -n "$DAYS" ] && mtime_args=(-mtime "+$DAYS")

count=$(find "$DATA_DIR" -mindepth 3 -maxdepth 3 -path '*/raw/*.html' "${mtime_args[@]}" 2>/dev/null | wc -l | tr -d ' ')

find "$DATA_DIR" -mindepth 3 -maxdepth 3 -path '*/raw/*.html' "${mtime_args[@]}" -delete

echo "Deleted $count snapshot(s) from $DATA_DIR/*/raw/${DAYS:+ (older than ${DAYS}d)}"

find "$DATA_DIR" -mindepth 1 -type d -empty -delete

echo "Removed empty directories under $DATA_DIR"
