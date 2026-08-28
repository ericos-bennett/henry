from __future__ import annotations

from django.core.management.base import BaseCommand

from app.scheduler import _run_loop


class Command(BaseCommand):
    help = (
        "Run the company-scrape scheduler loop in the foreground. Intended to run as "
        "its own process (systemd unit / server-start.sh), separate from the web "
        "server, so exactly one scheduler is live regardless of Gunicorn worker count."
    )

    def handle(self, *args, **options) -> None:
        self.stdout.write("scheduler: starting loop (Ctrl-C to stop)")
        _run_loop()
