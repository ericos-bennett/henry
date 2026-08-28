#!/usr/bin/env bash
#
# Production launcher for the home-server / mini-PC deployment.
#
# Builds the frontend, collects Django static files, then runs the three
# long-lived services in the foreground:
#   - Gunicorn      the Django WSGI app on 127.0.0.1:8000 (not exposed directly)
#   - run_scheduler the hourly scrape scheduler, as its own process
#   - Caddy         local HTTP router: serves the SPA, proxies /api etc to Gunicorn
#
# Public ingress and TLS are handled outside this script by Cloudflare + a
# cloudflared tunnel pointing at Caddy's local port (HENRY_HTTP_PORT). Run
# cloudflared as its own service.
#
# Ctrl-C, SIGTERM, or `systemctl stop` tears all three down together. If any one
# exits on its own, the others are stopped too (so a supervisor restarts a clean
# set).
#
# This is NOT for local development - use ./start-all.sh for that.
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
REPO_ROOT="$(pwd)"

SKIP_BUILD=0
[ "${1:-}" = "--skip-build" ] && SKIP_BUILD=1

# --- tunables (override via env) ---
export HENRY_FRONTEND_DIST="${HENRY_FRONTEND_DIST:-$REPO_ROOT/frontend/dist}"
export HENRY_BACKEND_BIND="${HENRY_BACKEND_BIND:-127.0.0.1:8000}"
# Local HTTP port Caddy serves on. TLS is terminated by Cloudflare; cloudflared
# (its own service) connects the public hostname to this port over the tunnel.
export HENRY_HTTP_PORT="${HENRY_HTTP_PORT:-8080}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-3}"
# Worker request timeout. The scrape endpoints (POST /companies/scrape-all and
# /companies/{id}/scrape) run synchronously in the worker, so this also caps how
# long a scrape triggered from the UI may take before the worker is killed and the
# request 502s. The hourly scheduler runs in its own process and is unaffected.
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-60}"
CADDYFILE="${CADDYFILE:-$REPO_ROOT/Caddyfile}"

command -v uv    >/dev/null || { echo "ERROR: uv not found on PATH" >&2; exit 1; }
command -v caddy >/dev/null || { echo "ERROR: caddy not found on PATH" >&2; exit 1; }
[ -f backend/.env ] || { echo "ERROR: backend/.env is missing" >&2; exit 1; }

# Load backend/.env so this script (and the migration check below) see the same
# config the app will. Gunicorn/manage.py re-load it themselves via python-dotenv.
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
# step (take a pg_dump first) - not something a crash-looping service should do.
if ! ( cd backend && uv run python manage.py migrate --check ) >/dev/null 2>&1; then
	echo "ERROR: unapplied migrations. Back up first, then apply:" >&2
	echo "  pg_dump -Fc \"\$DATABASE_URL\" > henry-\$(date +%F-%H%M).dump" >&2
	echo "  ( cd backend && uv run python manage.py migrate )" >&2
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

echo "==> Gunicorn on $HENRY_BACKEND_BIND ($GUNICORN_WORKERS workers)"
(
	cd backend
	exec uv run gunicorn app.wsgi:application \
		--workers "$GUNICORN_WORKERS" \
		--bind "$HENRY_BACKEND_BIND" \
		--timeout "$GUNICORN_TIMEOUT" \
		--max-requests 1000 --max-requests-jitter 100 \
		--access-logfile - --error-logfile -
) &
pids+=($!)

echo "==> Scrape scheduler"
(
	cd backend
	exec env HENRY_RUN_SCHEDULER=1 uv run python manage.py run_scheduler
) &
pids+=($!)

echo "==> Caddy ($CADDYFILE) on http://127.0.0.1:$HENRY_HTTP_PORT (tunnel origin)"
caddy run --config "$CADDYFILE" --adapter caddyfile &
pids+=($!)

# Exit (and trigger cleanup) as soon as any one service stops.
wait -n
echo "A service exited - shutting the rest down." >&2
