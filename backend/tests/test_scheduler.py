"""Hermetic tests for scheduler.tick's cron-matching and dispatch, using Django's
own test database and a mocked run_scrapes_concurrently (no live scraping)."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone as django_timezone

from app.apps import _should_start_scheduler
from app.models import Company
from app.scheduler import tick
from app.schemas import ScrapeResult


@mock.patch("app.scheduler.close_old_connections")  # a no-op in these tests: it
# assumes CONN_MAX_AGE-based obsolescence handling appropriate for tick()'s real
# usage (a long-lived background thread outside Django's request lifecycle), but
# would prematurely close the connection TestCase's wrapping transaction relies on.
class TickDispatchTest(TestCase):
    def setUp(self):
        # 9am UTC on a Saturday: matches "0 8 * * *" only if server-local time
        # happens to be UTC, so pick frequencies relative to server-local time
        # instead by using the always-due "0 * * * *" vs. a clearly-not-due one.
        self.hourly = Company.objects.create(
            name="Acme", url="https://acme.example/jobs", frequency="0 * * * *", enabled=True
        )
        self.weekly = Company.objects.create(
            name="Globex", url="https://globex.example/jobs", frequency="0 8 * * 0", enabled=True
        )
        self.now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)  # a Wednesday

    @mock.patch("app.scheduler.run_scrapes_concurrently")
    def test_only_dispatches_due_companies(self, mock_run_scrapes, mock_close_old_connections):
        mock_run_scrapes.return_value = []

        tick(self.now)

        mock_run_scrapes.assert_called_once()
        dispatched_ids = {c.id for c in mock_run_scrapes.call_args.args[0]}
        self.assertEqual(dispatched_ids, {self.hourly.id})

    @mock.patch("app.scheduler.run_scrapes_concurrently")
    def test_disabled_companies_never_considered(self, mock_run_scrapes, mock_close_old_connections):
        self.hourly.enabled = False
        self.hourly.save()
        mock_run_scrapes.return_value = []

        tick(self.now)

        dispatched_ids = {c.id for c in mock_run_scrapes.call_args.args[0]}
        self.assertEqual(dispatched_ids, set())

    @mock.patch("app.scheduler.run_scrapes_concurrently")
    def test_one_failure_does_not_stop_others_from_being_logged(self, mock_run_scrapes, mock_close_old_connections):
        other_due = Company.objects.create(
            name="Initech", url="https://initech.example/jobs", frequency="0 * * * *", enabled=True
        )
        mock_run_scrapes.return_value = [
            (self.hourly, RuntimeError("boom")),
            (other_due, ScrapeResult(company_id=other_due.id, jobs_found=2, scraped_at=django_timezone.now())),
        ]

        # Should complete without raising, despite one outcome being an exception.
        tick(self.now)


class ShouldStartSchedulerTest(SimpleTestCase):
    """_should_start_scheduler() decides whether AppConfig.ready() spawns the
    in-process scheduler thread. Under a WSGI server (Gunicorn) it must NOT, or
    every worker runs its own scheduler."""

    def _check(self, argv, env):
        with mock.patch.object(sys, "argv", argv), mock.patch.dict(os.environ, env, clear=True):
            return _should_start_scheduler()

    def test_runserver_bootstrap_starts(self):
        self.assertTrue(self._check(["manage.py", "runserver"], {"RUN_MAIN": "true"}))

    def test_runserver_parent_process_does_not_start(self):
        self.assertFalse(self._check(["manage.py", "runserver"], {}))

    def test_other_manage_commands_do_not_start(self):
        self.assertFalse(self._check(["manage.py", "migrate"], {"RUN_MAIN": "true"}))
        self.assertFalse(self._check(["manage.py", "run_scheduler"], {}))

    def test_wsgi_does_not_start_by_default(self):
        self.assertFalse(self._check(["gunicorn"], {}))

    def test_wsgi_starts_only_with_explicit_env_opt_in(self):
        self.assertTrue(self._check(["gunicorn"], {"HENRY_RUN_SCHEDULER": "1"}))
