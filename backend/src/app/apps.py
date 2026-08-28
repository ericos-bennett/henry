from __future__ import annotations

import os
import sys
from pathlib import Path

from django.apps import AppConfig


class CareerScraperAppConfig(AppConfig):
    name = "app"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        if not _should_start_scheduler():
            return
        from app.scheduler import start

        start()


def _should_start_scheduler() -> bool:
    argv = sys.argv
    is_manage_py = bool(argv) and Path(argv[0]).name == "manage.py"

    if is_manage_py:
        # Only start for `runserver`; skip migrate/makemigrations/shell/test/etc.
        if len(argv) < 2 or argv[1] != "runserver":
            return False
        # The dev-server autoreloader re-execs itself as a child process with
        # RUN_MAIN=true; ready() also fires in the parent bootstrap process
        # (RUN_MAIN unset), so only start there to avoid a duplicate thread.
        # Known limitation: `runserver --noreload` never sets RUN_MAIN, so the
        # scheduler won't start in that mode.
        return os.environ.get("RUN_MAIN") == "true"

    # Not invoked via manage.py (e.g. Gunicorn importing app.wsgi:application).
    # Do NOT start unconditionally here: every Gunicorn worker would spawn its own
    # scheduler thread, so each company would be scraped once per worker per tick
    # (Nx the LLM spend and load on target sites). In production the scheduler runs
    # as its own single process via `manage.py run_scheduler`; this env gate is a
    # deliberate opt-in for any other WSGI-style entrypoint that wants it.
    return os.environ.get("HENRY_RUN_SCHEDULER") == "1"
