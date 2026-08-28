#!/usr/bin/env bash
#
# Launches the hourly scrape scheduler as its own process (henry-scheduler.service
# / server-start.sh). HENRY_RUN_SCHEDULER=1 is belt-and-suspenders: the management
# command runs the loop directly regardless, but the env var also allows
# app.apps._should_start_scheduler() to start it if this were ever run via WSGI.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/backend"

exec env HENRY_RUN_SCHEDULER=1 uv run --no-sync python manage.py run_scheduler
