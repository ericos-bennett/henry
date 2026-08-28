#!/usr/bin/env bash
#
# Install or remove the weekly-maintenance entry in the current user's crontab.
# The one place the schedule is defined; server-start.sh calls `install`,
# server-stop.sh calls `remove` (which matches the marker block, not the schedule).
#
#   infra/maintenance-cron.sh install
#   infra/maintenance-cron.sh remove
#
# Schedule / log path come from backend/.env (HENRY_MAINTENANCE_CRON,
# HENRY_MAINTENANCE_LOG); see backend/.env.example for defaults.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION="${1:?usage: maintenance-cron.sh install|remove}"

# Overridable so tests can point at a fake crontab.
CRONTAB="${HENRY_CRONTAB_CMD:-crontab}"

BEGIN="# >>> henry-maintenance >>>"
END="# <<< henry-maintenance <<<"

# Current crontab minus any existing henry-maintenance block (crontab -l exits
# non-zero when the user has no crontab yet).
current="$($CRONTAB -l 2>/dev/null || true)"
stripped="$(printf '%s\n' "$current" | sed "\|$BEGIN|,\|$END|d")"

case "$ACTION" in
	remove)
		printf '%s\n' "$stripped" | $CRONTAB -
		echo "henry-maintenance cron entry removed"
		;;
	install)
		set -a
		[ -f "$REPO_ROOT/backend/.env" ] && source "$REPO_ROOT/backend/.env"
		set +a
		schedule="${HENRY_MAINTENANCE_CRON:-0 4 * * 0}"
		log="${HENRY_MAINTENANCE_LOG:-$HOME/henry-maintenance.log}"
		{
			printf '%s\n' "$stripped" "$BEGIN"
			# cron runs with a minimal PATH; carry the deployer's so backup-db.sh
			# finds pg_dump (same approach as the systemd units).
			printf 'PATH=%s\n' "$PATH"
			printf '%s %s/infra/weekly-maintenance.sh >> %s 2>&1\n' \
				"$schedule" "$REPO_ROOT" "$log"
			printf '%s\n' "$END"
		} | $CRONTAB -
		echo "henry-maintenance cron entry installed: $schedule -> $log"
		;;
	*)
		echo "usage: maintenance-cron.sh install|remove" >&2
		exit 2
		;;
esac
