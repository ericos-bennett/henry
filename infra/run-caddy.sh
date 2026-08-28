#!/usr/bin/env bash
#
# Launches Caddy as the local HTTP router (ExecStart for henry-caddy.service):
# serves the built SPA and reverse-proxies /api /controls /static to Gunicorn.
# TLS is terminated upstream by Cloudflare; cloudflared connects to HENRY_HTTP_PORT.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

set -a
[ -f "$REPO_ROOT/backend/.env" ] && source "$REPO_ROOT/backend/.env"
set +a

export HENRY_FRONTEND_DIST="${HENRY_FRONTEND_DIST:-$REPO_ROOT/frontend/dist}"
export HENRY_BACKEND_BIND="${HENRY_BACKEND_BIND:-127.0.0.1:8000}"
export HENRY_HTTP_PORT="${HENRY_HTTP_PORT:-8081}"

exec caddy run --config "$REPO_ROOT/Caddyfile" --adapter caddyfile
