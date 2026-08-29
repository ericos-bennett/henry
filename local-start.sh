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

PASSWORD_FILE="$DATA_DIR/grafana-admin-password"
if [ ! -f "$PASSWORD_FILE" ]; then
  openssl rand -base64 24 > "$PASSWORD_FILE"
  chmod 600 "$PASSWORD_FILE"
fi
GF_ADMIN_PASSWORD="$(cat "$PASSWORD_FILE")"

docker run -d --name otel-lgtm --restart unless-stopped \
  -p 127.0.0.1:3000:3000 -p 127.0.0.1:4317:4317 -p 127.0.0.1:4318:4318 \
  -v "$DATA_DIR/grafana:/data/grafana" \
  -v "$DATA_DIR/prometheus:/data/prometheus" \
  -v "$DATA_DIR/loki:/data/loki" \
  -e GF_PATHS_DATA=/data/grafana \
  -e GF_SECURITY_ADMIN_PASSWORD="$GF_ADMIN_PASSWORD" \
  -e PROMETHEUS_STORAGE_TSDB_PATH=/data/prometheus \
  -e LOKI_STORAGE_PATH=/data/loki \
  grafana/otel-lgtm

echo "Grafana: http://localhost:3000 (login admin / password in $PASSWORD_FILE)"
echo "OTLP endpoints: localhost:4317 (gRPC), localhost:4318 (HTTP) - loopback only"
