#!/usr/bin/env bash
#
# Deploy / redeploy Henry on the home server.
#
# Pulls the latest code, rebuilds the frontend and backend, applies migrations,
# then installs (or refreshes) the three systemd units and restarts them so the
# new code is live:
#
#   henry-web.service        Gunicorn (Django WSGI app)      -> 127.0.0.1:8000
#   henry-scheduler.service  hourly scrape scheduler
#   henry-caddy.service      local HTTP router               -> HENRY_HTTP_PORT
#
# NOTE: no database backup is taken - `migrate` runs against the live DB with no
# safety net. Take a `pg_dump` by hand before deploying anything with a risky
# migration, until the backup timer (item 5) lands.
#
# Postgres and cloudflared are managed separately (their own services).
# Run as the normal app user - it calls sudo only for the systemd parts.
#
# Usage:
#   ./server-deploy.sh                 pull + build + migrate + (re)install + restart
#   ./server-deploy.sh --skip-pull     don't touch git (deploy the working tree as-is)

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
REPO_ROOT="$(pwd)"

SKIP_PULL=0
for arg in "$@"; do
	case "$arg" in
		--skip-pull) SKIP_PULL=1 ;;
		*) echo "unknown option: $arg" >&2; exit 2 ;;
	esac
done

if [ "$EUID" -eq 0 ]; then
	echo "ERROR: run this as your normal user, not root/sudo (it sudo's where needed)." >&2
	exit 1
fi

for cmd in git uv caddy npm sudo systemctl; do
	command -v "$cmd" >/dev/null || { echo "ERROR: $cmd not found on PATH" >&2; exit 1; }
done
[ -f backend/.env ] || { echo "ERROR: backend/.env is missing" >&2; exit 1; }

UNIT_USER="$(id -un)"
UNIT_GROUP="$(id -gn)"

# --- 1. code ---------------------------------------------------------------
if [ "$SKIP_PULL" -eq 0 ]; then
	echo "==> git pull --ff-only"
	git pull --ff-only
fi

set -a
source backend/.env
set +a

if [ "${DJANGO_DEBUG:-}" = "true" ]; then
	echo "ERROR: DJANGO_DEBUG=true in backend/.env - refusing to deploy." >&2
	exit 1
fi

# --- 2. build ------------------------------------------------------------------
echo "==> Syncing backend dependencies"
( cd backend && uv sync )

echo "==> Installing Playwright browser"
( cd backend && uv run --no-sync playwright install chromium )

echo "==> Building frontend"
npm --prefix frontend ci
npm --prefix frontend run build

# --- 3. migrate ------------------------------------------------------------------
echo "==> Applying migrations"
( cd backend && uv run --no-sync python manage.py migrate --noinput )

echo "==> Collecting static files"
( cd backend && uv run --no-sync python manage.py collectstatic --noinput )

# --- 4. systemd units --------------------------------------------------------
PATH_VALUE="$PATH"

write_unit() {
	local name="$1" desc="$2" exec_path="$3" workdir="$4"
	echo "==> Writing /etc/systemd/system/$name"
	sudo tee "/etc/systemd/system/$name" >/dev/null <<UNIT
[Unit]
Description=$desc
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=simple
User=$UNIT_USER
Group=$UNIT_GROUP
WorkingDirectory=$workdir
Environment=PATH=$PATH_VALUE
ExecStart=$exec_path
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
}

write_unit henry-web.service       "Henry web (Gunicorn)"     "$REPO_ROOT/deploy/run-web.sh"       "$REPO_ROOT/backend"
write_unit henry-scheduler.service "Henry scrape scheduler"   "$REPO_ROOT/deploy/run-scheduler.sh" "$REPO_ROOT/backend"
write_unit henry-caddy.service     "Henry HTTP router (Caddy)" "$REPO_ROOT/deploy/run-caddy.sh"     "$REPO_ROOT"

echo "==> Reloading systemd + (re)starting services"
sudo systemctl daemon-reload
sudo systemctl enable henry-web.service henry-scheduler.service henry-caddy.service
sudo systemctl restart henry-web.service henry-scheduler.service henry-caddy.service

# --- 5. report -------------------------------------------------------------
sleep 2
echo
for svc in henry-web henry-scheduler henry-caddy; do
	printf '%-18s %s\n' "$svc" "$(systemctl is-active "$svc")"
done
echo
echo "Logs:   journalctl -u henry-web -f   (or -scheduler / -caddy)"
echo "Local:  curl -sI http://localhost:${HENRY_HTTP_PORT:-8081}/"

TZ_NAME="$(timedatectl show -p Timezone --value 2>/dev/null || echo unknown)"
if [ "$TZ_NAME" = "Etc/UTC" ] || [ "$TZ_NAME" = "UTC" ]; then
	echo
	echo "NOTE: system timezone is $TZ_NAME. The scheduler matches cron expressions"
	echo "      against server-local time - set a real zone with:  sudo timedatectl set-timezone <Area/City>"
fi
