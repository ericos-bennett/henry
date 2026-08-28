#!/usr/bin/env bash
#
# Foreground launcher for the home-server deployment WITHOUT systemd - handy for
# first bring-up and debugging. For the real always-on setup use ./server-deploy.sh
# (installs systemd units) and ./server-teardown.sh.
#
# Builds the frontend + static files, then runs the three long-lived services in
# the foreground via the same deploy/run-*.sh launchers the systemd units use:
#   - Gunicorn      the Django WSGI app (not exposed directly)
#   - run_scheduler the hourly scrape scheduler, as its own process
#   - Caddy         local HTTP router: serves the SPA, proxies /api etc to Gunicorn
#
# Public ingress and TLS are handled outside this script by Cloudflare + a
# cloudflared tunnel pointing at Caddy's local port (HENRY_HTTP_PORT).
#
# Ctrl-C / SIGTERM tears all three down; if any one exits on its own the others
# are stopped too.
#
# NOT for local development - use ./start-all.sh for that.
#
# Requirements on the box: uv, node/npm, caddy, cloudflared, a running Postgres,
# and a backend/.env with production values (DJANGO_DEBUG unset, DJANGO_SECRET_KEY
# set, DJANGO_ALLOWED_HOSTS + DJANGO_CSRF_TRUSTED_ORIGINS including the public
# hostname, DJANGO_SECURE_SSL=true).
#
# Usage:
#   ./server-start.sh                 full build + run
#   ./server-start.sh --skip-build    run only (deps/frontend/static unchanged)

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

SKIP_BUILD=0
[ "${1:-}" = "--skip-build" ] && SKIP_BUILD=1

command -v uv    >/dev/null || { echo "ERROR: uv not found on PATH" >&2; exit 1; }
command -v caddy >/dev/null || { echo "ERROR: caddy not found on PATH" >&2; exit 1; }
[ -f backend/.env ] || { echo "ERROR: backend/.env is missing" >&2; exit 1; }

set -a
source backend/.env
set +a

if [ "${DJANGO_DEBUG:-}" = "true" ]; then
	echo "ERROR: DJANGO_DEBUG=true in backend/.env - refusing to start in production." >&2
	exit 1
fi

if [ "$SKIP_BUILD" -eq 0 ]; then
	echo "==> Syncing backend dependencies"
	( cd backend && uv sync )

	# Browser binary only (no --with-deps: that needs root). Install the system
	# libraries once with:  sudo $(cd backend && uv run which playwright) install-deps chromium
	echo "==> Installing Playwright browser"
	( cd backend && uv run playwright install chromium )

	echo "==> Building frontend"
	npm --prefix frontend ci
	npm --prefix frontend run build

	echo "==> Collecting static files"
	( cd backend && uv run python manage.py collectstatic --noinput )
fi

# Refuse to start with unapplied migrations. Applying them is a deliberate deploy
# step (server-deploy.sh, which pg_dumps first) - not something to do on every start.
if ! ( cd backend && uv run python manage.py migrate --check ) >/dev/null 2>&1; then
	echo "ERROR: unapplied migrations. Run ./server-deploy.sh (it backs up, then migrates)." >&2
	exit 1
fi

pids=()
cleanup() {
	trap - EXIT INT TERM
	echo
	echo "==> Stopping services"
	kill "${pids[@]}" 2>/dev/null || true
	wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Same per-service launchers the systemd units use, so behaviour can't drift.
echo "==> Gunicorn"
deploy/run-web.sh & pids+=($!)

echo "==> Scrape scheduler"
deploy/run-scheduler.sh & pids+=($!)

echo "==> Caddy"
deploy/run-caddy.sh & pids+=($!)

# Exit (and trigger cleanup) as soon as any one service stops.
wait -n
echo "A service exited - shutting the rest down." >&2
