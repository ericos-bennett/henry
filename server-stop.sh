#!/usr/bin/env bash
#
# Stop Henry on the home server and remove its systemd units.
#
# Takes a final pg_dump snapshot (infra/backup-db.sh), removes the
# weekly-maintenance cron entry, then stops and disables henry-web /
# henry-scheduler / henry-caddy, deletes their unit files, and reloads systemd.
# Re-run server-start.sh to bring it all back.
#
# Does NOT touch: cloudflared, Postgres, the checked-out repo, or the database
# contents (the snapshot is read-only).
#
# Run as the normal app user (it calls sudo where needed).
#
# Usage:
#   ./server-stop.sh          prompt, then stop + remove units
#   ./server-stop.sh --yes    no prompt

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
REPO_ROOT="$(pwd)"

if [ "$EUID" -eq 0 ]; then
	echo "ERROR: run this as your normal user, not root/sudo." >&2
	exit 1
fi

ASSUME_YES=0
[ "${1:-}" = "--yes" ] && ASSUME_YES=1

SERVICES=(henry-web henry-scheduler henry-caddy)

if [ "$ASSUME_YES" -eq 0 ]; then
	read -rp "Stop ${SERVICES[*]} and remove their systemd units? [y/N] " ans
	[ "$ans" = "y" ] || [ "$ans" = "Y" ] || { echo "aborted"; exit 0; }
fi

# Final snapshot. Don't let a backup failure block the teardown.
"$REPO_ROOT/infra/backup-db.sh" teardown || echo "WARNING: backup failed - continuing with teardown" >&2

echo "==> Removing weekly-maintenance cron entry"
"$REPO_ROOT/infra/maintenance-cron.sh" remove

for svc in "${SERVICES[@]}"; do
	echo "==> Stopping/disabling $svc"
	sudo systemctl disable --now "$svc.service" 2>/dev/null || true
	sudo rm -f "/etc/systemd/system/$svc.service"
done

echo "==> Reloading systemd"
sudo systemctl daemon-reload
sudo systemctl reset-failed "${SERVICES[@]/%/.service}" 2>/dev/null || true

echo
echo "Henry services stopped and removed; weekly-maintenance cron entry removed."
echo "Still running (unchanged): cloudflared, postgresql."
echo "DB snapshot saved (see the backup path printed above)."
echo "Bring Henry back with: ./server-start.sh"
