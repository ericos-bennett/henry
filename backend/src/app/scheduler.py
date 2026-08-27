from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from croniter import croniter
from django.db import close_old_connections

from app.models import Company
from app.pipeline import run_scrapes_concurrently

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def tick(now: datetime | None = None) -> None:
    """Check all enabled companies against `now` (default: current UTC time,
    truncated to the top of the hour, converted to server-local time for cron
    matching) and scrape any whose cron expression matches.

    Callable directly (e.g. from `manage.py shell`) for manual verification
    without waiting for the real hourly loop.
    """
    now = (now or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    logger.info("scheduler tick at %s", now.isoformat())
    # Cron expressions (e.g. from the frontend's frequency dropdown) are authored in
    # server-local time, so match against that rather than the UTC `now` above.
    local_now = now.astimezone()

    close_old_connections()
    due_companies = []
    for company in Company.objects.filter(enabled=True):
        try:
            due = croniter.match(company.frequency, local_now)
        except Exception:
            logger.exception("scheduler: invalid cron for %s: %r", company.name, company.frequency)
            continue
        if due:
            logger.info("scheduler: %s is due, scraping", company.name)
            due_companies.append(company)

    for company, outcome in run_scrapes_concurrently(due_companies):
        if isinstance(outcome, Exception):
            logger.exception("scheduler: scrape failed for %s", company.name, exc_info=outcome)
        else:
            logger.info("scheduler: %s scraped, %d jobs found", company.name, outcome.jobs_found)


def _seconds_until_next_hour(now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return (next_hour - now).total_seconds()


def _run_loop() -> None:
    while True:
        time.sleep(_seconds_until_next_hour())
        try:
            tick()
        except Exception:
            logger.exception("scheduler: tick raised unexpectedly")


def start() -> None:
    threading.Thread(target=_run_loop, name="company-scrape-scheduler", daemon=True).start()
    logger.info("scheduler thread started")
