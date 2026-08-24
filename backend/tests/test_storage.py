"""Hermetic tests for save_job_postings, using Django's own test database."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from django.test import TestCase

from app.models import Company, JobPosting
from app.storage import save_job_postings


def make_job(company: Company, job_id: str, scraped_at: datetime) -> JobPosting:
    return JobPosting(
        job_id=job_id,
        source_company=company,
        source_url=company.url,
        scraped_at=scraped_at,
        title=f"Job {job_id}",
    )


class SaveJobPostingsTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            id="acme", name="Acme", url="https://acme.example/jobs", frequency="0 * * * *"
        )
        self.first_run = datetime(2026, 8, 1, tzinfo=timezone.utc)
        self.second_run = self.first_run + timedelta(days=1)

    def test_first_scrape_has_no_new_jobs(self):
        jobs = [make_job(self.company, "a", self.first_run), make_job(self.company, "b", self.first_run)]
        saved = save_job_postings(jobs)
        self.assertTrue(all(job.is_new is False for job in saved))

    def test_second_scrape_flags_only_jobs_absent_from_previous_run(self):
        save_job_postings([make_job(self.company, "a", self.first_run), make_job(self.company, "b", self.first_run)])

        second_batch = [
            make_job(self.company, "a", self.second_run),  # present last time
            make_job(self.company, "c", self.second_run),  # new
        ]
        saved = save_job_postings(second_batch)

        is_new_by_job_id = {job.job_id: job.is_new for job in saved}
        self.assertEqual(is_new_by_job_id, {"a": False, "c": True})

    def test_reappearing_job_is_flagged_new_again(self):
        save_job_postings([make_job(self.company, "a", self.first_run)])
        save_job_postings([make_job(self.company, "b", self.second_run)])  # "a" absent this run

        third_run = self.second_run + timedelta(days=1)
        saved = save_job_postings([make_job(self.company, "a", third_run)])

        self.assertTrue(saved[0].is_new)

    def test_previous_run_lookup_is_scoped_per_company(self):
        # Acme has an earlier run containing job "a" (not "z"). Globex's own first-ever
        # run, timestamped after Acme's run, contains "z". If the "find the previous
        # run" lookup weren't scoped to source_company, it would wrongly treat Acme's
        # run as Globex's "previous" run and mark "z" as new (since "z" isn't in
        # Acme's set) instead of correctly falling back to the no-prior-run default.
        other_company = Company.objects.create(
            id="globex", name="Globex", url="https://globex.example/jobs", frequency="0 * * * *"
        )
        save_job_postings([make_job(self.company, "a", self.first_run)])

        saved = save_job_postings([make_job(other_company, "z", self.second_run)])

        self.assertFalse(saved[0].is_new)
