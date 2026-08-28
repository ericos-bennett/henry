#!/usr/bin/env bash
#
# Stop Henry on the home server and remove its systemd units.
#
# Stops and disables henry-web / henry-scheduler / henry-caddy, deletes their
# unit files, and reloads systemd. Re-run server-deploy.sh to bring it all back.
#
# Does NOT touch: cloudflared, Postgres, the checked-out repo, or the database.
#
# Run as the normal app user (it calls sudo where needed).
#
# Usage:
#   ./server-teardown.sh          prompt, then stop + remove units
#   ./server-teardown.sh --yes    no prompt

set -euo pipefail

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

for svc in "${SERVICES[@]}"; do
	echo "==> Stopping/disabling $svc"
	sudo systemctl disable --now "$svc.service" 2>/dev/null || true
	sudo rm -f "/etc/systemd/system/$svc.service"
done

echo "==> Reloading systemd"
sudo systemctl daemon-reload
sudo systemctl reset-failed "${SERVICES[@]/%/.service}" 2>/dev/null || true

echo
echo "Henry services stopped and removed."
echo "Still running (unchanged): cloudflared, postgresql."
echo "Bring Henry back with: ./server-deploy.sh"
