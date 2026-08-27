"""Hermetic tests for save_job_postings, using Django's own test database."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from django.test import TestCase

from app.models import Company, JobPosting
from app.storage import save_job_postings


def make_job(company: Company, job_key: str, scraped_at: datetime, **overrides) -> JobPosting:
    fields = dict(
        job_key=job_key,
        company=company,
        first_scrape_timestamp=scraped_at,
        latest_scrape_timestamp=scraped_at,
        title=f"Job {job_key}",
    )
    fields.update(overrides)
    return JobPosting(**fields)


class SaveJobPostingsTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Acme", url="https://acme.example/jobs", frequency="0 * * * *"
        )
        self.first_run = datetime(2026, 8, 1, tzinfo=timezone.utc)
        self.second_run = self.first_run + timedelta(days=1)

    def test_first_scrape_creates_one_row_per_job_key(self):
        jobs = [make_job(self.company, "a", self.first_run), make_job(self.company, "b", self.first_run)]
        saved = save_job_postings(jobs)

        self.assertEqual({job.job_key for job in saved}, {"a", "b"})
        self.assertTrue(all(job.is_new for job in saved))

    def test_continuing_job_updates_existing_row_in_place(self):
        first_saved = save_job_postings([make_job(self.company, "a", self.first_run, title="Old Title")])
        original_pk = first_saved[0].pk

        saved = save_job_postings([make_job(self.company, "a", self.second_run, title="New Title")])

        self.assertEqual(JobPosting.objects.filter(company=self.company, job_key="a").count(), 1)
        row = saved[0]
        self.assertEqual(row.pk, original_pk)  # same row updated, not a new one inserted
        self.assertEqual(row.title, "New Title")
        self.assertEqual(row.first_scrape_timestamp, self.first_run)
        self.assertEqual(row.latest_scrape_timestamp, self.second_run)
        self.assertFalse(row.is_new)

    def test_second_scrape_only_creates_rows_for_jobs_absent_from_previous_run(self):
        save_job_postings([make_job(self.company, "a", self.first_run), make_job(self.company, "b", self.first_run)])

        second_batch = [
            make_job(self.company, "a", self.second_run),  # present last time -> continuation
            make_job(self.company, "c", self.second_run),  # new
        ]
        saved = save_job_postings(second_batch)

        is_new_by_key = {job.job_key: job.is_new for job in saved}
        self.assertEqual(is_new_by_key, {"a": False, "c": True})

    def test_reappearing_job_gets_a_new_row(self):
        first_saved = save_job_postings([make_job(self.company, "a", self.first_run)])
        original_pk = first_saved[0].pk
        save_job_postings([make_job(self.company, "b", self.second_run)])  # "a" absent this run: a gap

        third_run = self.second_run + timedelta(days=1)
        saved = save_job_postings([make_job(self.company, "a", third_run)])

        new_row = saved[0]
        self.assertEqual(new_row.job_key, "a")
        self.assertNotEqual(new_row.pk, original_pk)  # a new row, not the original lifetime's
        self.assertTrue(new_row.is_new)
        self.assertEqual(new_row.first_scrape_timestamp, third_run)

        # The original row from the first run is untouched, not overwritten.
        self.assertEqual(JobPosting.objects.filter(company=self.company, job_key="a").count(), 2)
        original_row = JobPosting.objects.get(pk=original_pk)
        self.assertEqual(original_row.latest_scrape_timestamp, self.first_run)

    def test_previous_run_lookup_is_scoped_per_company(self):
        # Acme has an earlier run containing job "a" (not "z"). Globex's own first-ever
        # run, timestamped after Acme's run, contains "z". If the "find the previous
        # run" lookup weren't scoped to company, it would wrongly treat Acme's
        # run as Globex's "previous" run and treat "z" as a continuation (or at least
        # not a first-ever lifetime) instead of correctly falling back to the
        # no-prior-run default.
        other_company = Company.objects.create(
            name="Globex", url="https://globex.example/jobs", frequency="0 * * * *"
        )
        save_job_postings([make_job(self.company, "a", self.first_run)])

        saved = save_job_postings([make_job(other_company, "z", self.second_run)])

        self.assertTrue(saved[0].is_new)
