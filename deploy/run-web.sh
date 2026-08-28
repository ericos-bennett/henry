#!/usr/bin/env bash
#
# Launches the Django WSGI app under Gunicorn. Used both by the systemd unit
# henry-web.service and by server-start.sh (foreground mode). Reads backend/.env
# for its knobs; server-deploy.sh is responsible for `uv sync`, so this uses
# --no-sync to start fast and not touch the venv.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/backend"

set -a
[ -f .env ] && source .env
set +a

exec uv run --no-sync gunicorn app.wsgi:application \
	--workers "${GUNICORN_WORKERS:-3}" \
	--bind "${HENRY_BACKEND_BIND:-127.0.0.1:8000}" \
	--timeout "${GUNICORN_TIMEOUT:-60}" \
	--max-requests 1000 --max-requests-jitter 100 \
	--access-logfile - --error-logfile -
