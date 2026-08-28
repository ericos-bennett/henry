#!/usr/bin/env bash
#
# Delete raw HTML scrape snapshots under backend/data/<company_id>/raw/ and prune
# any directories left empty.
#
#   ./clear-snapshots.sh        delete every snapshot
#   ./clear-snapshots.sh 7      delete only snapshots older than 7 days
#
# The weekly-maintenance cron job calls this with a retention window; run it with
# no argument for a full wipe.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

DATA_DIR="backend/data"
DAYS="${1:-}"

mtime_args=()
[ -n "$DAYS" ] && mtime_args=(-mtime "+$DAYS")

count=$(find "$DATA_DIR" -mindepth 3 -maxdepth 3 -path '*/raw/*.html' "${mtime_args[@]}" 2>/dev/null | wc -l | tr -d ' ')

find "$DATA_DIR" -mindepth 3 -maxdepth 3 -path '*/raw/*.html' "${mtime_args[@]}" -delete

echo "Deleted $count snapshot(s) from $DATA_DIR/*/raw/${DAYS:+ (older than ${DAYS}d)}"

find "$DATA_DIR" -mindepth 1 -type d -empty -delete

echo "Removed empty directories under $DATA_DIR"
