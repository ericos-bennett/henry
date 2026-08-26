#!/usr/bin/env bash
set -euo pipefail

tmux kill-session -t backend 2>/dev/null || true
tmux kill-session -t frontend 2>/dev/null || true
echo "Stopped tmux sessions: backend, frontend"

docker stop otel-lgtm 2>/dev/null || true
docker rm otel-lgtm 2>/dev/null || true
echo "Stopped and removed otel-lgtm container"
