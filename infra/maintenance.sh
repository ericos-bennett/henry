#!/usr/bin/env bash
#
# Home-server weekly maintenance: DB dump + raw-HTML snapshot pruning, plus the
# crontab wiring that schedules it.
#
#   infra/maintenance.sh run        do the work now (what cron runs; also the default)
#   infra/maintenance.sh install    add the weekly crontab entry for the current user
#   infra/maintenance.sh remove     strip that crontab entry
#
# server-start.sh calls `install`; server-stop.sh calls `remove` (matching the
# marker block, not the schedule). Schedule / retention / log path come from
# backend/.env — see backend/.env.example (HENRY_MAINTENANCE_CRON,
# HENRY_SNAPSHOT_RETENTION_DAYS, HENRY_MAINTENANCE_LOG).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION="${1:-run}"

CRONTAB="${HENRY_CRONTAB_CMD:-crontab}"   # overridable so tests can use a fake
BEGIN="# >>> henry-maintenance >>>"
END="# <<< henry-maintenance <<<"

load_env() {
	set -a
	[ -f "$REPO_ROOT/backend/.env" ] && source "$REPO_ROOT/backend/.env"
	set +a
}

# Current crontab minus any existing henry-maintenance block (crontab -l exits
# non-zero when the user has no crontab yet). Captured into a variable before any
# `crontab -` write so the read can't race the replace.
crontab_without_block() {
	printf '%s\n' "$($CRONTAB -l 2>/dev/null || true)" | sed "\|$BEGIN|,\|$END|d"
}

case "$ACTION" in
	run)
		echo "=== henry maintenance $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
		# DB dump — writes henry-<stamp>-weekly.dump into $HENRY_BACKUP_DIR
		# (default ~/backups/henry), keeps the 10 most recent across all labels.
		"$REPO_ROOT/infra/backup-db.sh" weekly
		# Prune raw HTML snapshots older than the retention window.
		load_env
		"$REPO_ROOT/infra/clear-snapshots.sh" "${HENRY_SNAPSHOT_RETENTION_DAYS:-7}"
		echo "=== maintenance done ==="
		;;
	remove)
		rest="$(crontab_without_block)"
		if [ -n "$rest" ]; then
			printf '%s\n' "$rest" | $CRONTAB -
		else
			$CRONTAB -r 2>/dev/null || true   # our block was the whole crontab
		fi
		echo "henry-maintenance cron entry removed"
		;;
	install)
		load_env
		schedule="${HENRY_MAINTENANCE_CRON:-0 4 * * 0}"
		log="${HENRY_MAINTENANCE_LOG:-$HOME/henry-maintenance.log}"
		rest="$(crontab_without_block)"
		{
			[ -n "$rest" ] && printf '%s\n' "$rest"
			printf '%s\n' "$BEGIN"
			# cron runs with a minimal PATH; carry the deployer's so backup-db.sh
			# finds pg_dump (same approach as the systemd units).
			printf 'PATH=%s\n' "$PATH"
			printf '%s %s/infra/maintenance.sh run >> %s 2>&1\n' "$schedule" "$REPO_ROOT" "$log"
			printf '%s\n' "$END"
		} | $CRONTAB -
		echo "henry-maintenance cron entry installed: $schedule -> $log"
		;;
	*)
		echo "usage: maintenance.sh run|install|remove" >&2
		exit 2
		;;
esac
