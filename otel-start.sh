#!/usr/bin/env bash
set -euo pipefail

docker run -d --name otel-lgtm --restart unless-stopped \
  -p 3000:3000 -p 4317:4317 -p 4318:4318 \
  grafana/otel-lgtm

echo "Grafana: http://localhost:3000 (default login admin/admin, change on first login)"
echo "OTLP endpoints: localhost:4317 (gRPC), localhost:4318 (HTTP)"
