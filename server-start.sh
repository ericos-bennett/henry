#!/usr/bin/env bash
#
# Deploy / redeploy Henry on the home server: builds the frontend and backend,
# applies migrations, then installs (or refreshes) the three systemd units and
# restarts them so the current checkout is live:
#
#   henry-web.service        Gunicorn (Django WSGI app)      -> 127.0.0.1:8000
#   henry-scheduler.service  hourly scrape scheduler
#   henry-caddy.service      local HTTP router               -> HENRY_HTTP_PORT
#
# Deploys the working tree as-is - `git pull` yourself first to pick up new code.
#
# A pg_dump snapshot is taken before migrations run (deploy/backup-db.sh, keeps
# the 10 most recent in ~/backups/henry or $HENRY_BACKUP_DIR). A failed backup
# aborts the deploy.
#
# Postgres and cloudflared are managed separately (their own services).
# Run as the normal app user - it calls sudo only for the systemd parts.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
REPO_ROOT="$(pwd)"

[ "$#" -eq 0 ] || { echo "usage: $0  (no arguments)" >&2; exit 2; }

if [ "$EUID" -eq 0 ]; then
	echo "ERROR: run this as your normal user, not root/sudo (it sudo's where needed)." >&2
	exit 1
fi

for cmd in uv caddy npm sudo systemctl pg_dump; do
	command -v "$cmd" >/dev/null || { echo "ERROR: $cmd not found on PATH" >&2; exit 1; }
done
[ -f backend/.env ] || { echo "ERROR: backend/.env is missing" >&2; exit 1; }

UNIT_USER="$(id -un)"
UNIT_GROUP="$(id -gn)"

set -a
source backend/.env
set +a

if [ "${DJANGO_DEBUG:-}" = "true" ]; then
	echo "ERROR: DJANGO_DEBUG=true in backend/.env - refusing to deploy." >&2
	exit 1
fi

# --- 1. build ------------------------------------------------------------------
echo "==> Syncing backend dependencies"
( cd backend && uv sync )

echo "==> Installing Playwright browser"
( cd backend && uv run --no-sync playwright install chromium )

echo "==> Building frontend"
npm --prefix frontend ci
npm --prefix frontend run build

# --- 2. migrate ------------------------------------------------------------------
"$REPO_ROOT/deploy/backup-db.sh" deploy

echo "==> Applying migrations"
( cd backend && uv run --no-sync python manage.py migrate --noinput )

echo "==> Collecting static files"
( cd backend && uv run --no-sync python manage.py collectstatic --noinput )

# --- 3. systemd units --------------------------------------------------------
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

# --- 4. weekly-maintenance cron -------------------------------------------
echo "==> Installing weekly-maintenance cron entry"
"$REPO_ROOT/deploy/maintenance-cron.sh" install

# --- 5. report -------------------------------------------------------------
sleep 2
echo
for svc in henry-web henry-scheduler henry-caddy; do
	printf '%-18s %s\n' "$svc" "$(systemctl is-active "$svc")"
done
echo
echo "Logs:   journalctl -u henry-web -f   (or -scheduler / -caddy)"
echo "Health: curl -s http://localhost:${HENRY_HTTP_PORT:-8081}/api/health"

TZ_NAME="$(timedatectl show -p Timezone --value 2>/dev/null || echo unknown)"
if [ "$TZ_NAME" = "Etc/UTC" ] || [ "$TZ_NAME" = "UTC" ]; then
	echo
	echo "NOTE: system timezone is $TZ_NAME. The scheduler matches cron expressions"
	echo "      against server-local time - set a real zone with:  sudo timedatectl set-timezone <Area/City>"
fi
