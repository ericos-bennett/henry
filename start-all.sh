#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

tmux new -d -s backend  './backend/backend-start.sh'
tmux new -d -s frontend './frontend/frontend-start.sh'

echo "Started tmux sessions: backend, frontend"
echo "Attach with: tmux attach -t backend (or frontend)"

DATA_DIR="$(pwd)/otel-data"
mkdir -p "$DATA_DIR"/{grafana,prometheus,loki}
chmod -R 777 "$DATA_DIR"

docker run -d --name otel-lgtm --restart unless-stopped \
  -p 3000:3000 -p 4317:4317 -p 4318:4318 \
  -v "$DATA_DIR/grafana:/data/grafana" \
  -v "$DATA_DIR/prometheus:/data/prometheus" \
  -v "$DATA_DIR/loki:/data/loki" \
  -e GF_PATHS_DATA=/data/grafana \
  -e PROMETHEUS_STORAGE_TSDB_PATH=/data/prometheus \
  -e LOKI_STORAGE_PATH=/data/loki \
  grafana/otel-lgtm

echo "Grafana: http://localhost:3000 (default login admin/admin, change on first login)"
echo "OTLP endpoints: localhost:4317 (gRPC), localhost:4318 (HTTP)"
