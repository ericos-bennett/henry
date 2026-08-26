#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

DATA_DIR="backend/data"

count=$(find "$DATA_DIR" -mindepth 3 -maxdepth 3 -path '*/raw/*.html' 2>/dev/null | wc -l | tr -d ' ')

find "$DATA_DIR" -mindepth 3 -maxdepth 3 -path '*/raw/*.html' -delete

echo "Deleted $count snapshot(s) from $DATA_DIR/*/raw/"

find "$DATA_DIR" -mindepth 1 -type d -empty -delete

echo "Removed empty directories under $DATA_DIR"
