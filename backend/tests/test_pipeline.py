"""Hermetic tests for run_scrape's unchanged-content skip, using Django's own test
database and mocked fetch_company/extractor (no live browser, no live LLM calls)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest import mock

from django.test import TestCase

from django.utils import timezone as django_timezone

from app.fetcher import FetchResult
from app.models import Company, JobPosting
from app.pipeline import run_scrape, run_scrapes_concurrently
from app.schema import ExtractedJob
from app.schemas import ScrapeResult


def fake_fetch(text: str, fetched_at: datetime) -> FetchResult:
    return FetchResult(
        company_id=1, url="https://acme.example/jobs", fetched_at=fetched_at, html="<html/>", text=text, title="Acme"
    )


class RunScrapeSkipTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Acme", url="https://acme.example/jobs", frequency="0 * * * *"
        )
        self.t1 = datetime(2026, 8, 1, tzinfo=timezone.utc)
        self.t2 = self.t1.replace(day=2)

    @mock.patch("app.pipeline.notify_new_recommended_jobs")
    @mock.patch("app.pipeline.extractor")
    @mock.patch("app.pipeline.fetch_company")
    @mock.patch("app.pipeline.write_raw_html")
    def test_first_scrape_always_extracts_and_sets_hash(
        self, _mock_write, mock_fetch, mock_extractor, mock_notify
    ):
        mock_fetch.return_value = fake_fetch("Senior Engineer (https://acme.example/jobs/1)", self.t1)
        mock_extractor.extract.return_value = [ExtractedJob(title="Senior Engineer", url="https://acme.example/jobs/1")]

        result = run_scrape(self.company)

        mock_extractor.extract.assert_called_once()
        self.assertFalse(result.skipped)
        self.assertEqual(result.jobs_found, 1)
        self.company.refresh_from_db()
        self.assertIsNotNone(self.company.last_content_hash)
        # First scrape never notifies, regardless of content.
        mock_notify.assert_not_called()

    @mock.patch("app.pipeline.notify_new_recommended_jobs")
    @mock.patch("app.pipeline.extractor")
    @mock.patch("app.pipeline.fetch_company")
    @mock.patch("app.pipeline.write_raw_html")
    def test_unchanged_content_skips_extraction_and_notify(
        self, _mock_write, mock_fetch, mock_extractor, mock_notify
    ):
        text = "Senior Engineer (https://acme.example/jobs/1)"
        mock_fetch.return_value = fake_fetch(text, self.t1)
        mock_extractor.extract.return_value = [ExtractedJob(title="Senior Engineer", url="https://acme.example/jobs/1")]
        run_scrape(self.company)  # first scrape: extracts, sets last_content_hash
        mock_extractor.extract.reset_mock()
        mock_notify.reset_mock()

        mock_fetch.return_value = fake_fetch(text, self.t2)
        result = run_scrape(self.company)

        mock_extractor.extract.assert_not_called()
        mock_notify.assert_not_called()
        self.assertTrue(result.skipped)
        self.assertEqual(result.jobs_found, 1)  # current active job count, not re-extracted
        self.assertEqual(JobPosting.objects.filter(company=self.company).count(), 1)  # no new row written

    @mock.patch("app.pipeline.notify_new_recommended_jobs")
    @mock.patch("app.pipeline.extractor")
    @mock.patch("app.pipeline.fetch_company")
    @mock.patch("app.pipeline.write_raw_html")
    def test_changed_content_re_extracts_and_updates_hash(
        self, _mock_write, mock_fetch, mock_extractor, mock_notify
    ):
        mock_fetch.return_value = fake_fetch("Senior Engineer (https://acme.example/jobs/1)", self.t1)
        mock_extractor.extract.return_value = [ExtractedJob(title="Senior Engineer", url="https://acme.example/jobs/1")]
        run_scrape(self.company)
        first_hash = Company.objects.get(pk=self.company.pk).last_content_hash
        mock_extractor.extract.reset_mock()

        mock_fetch.return_value = fake_fetch(
            "Senior Engineer (https://acme.example/jobs/1)\nProduct Designer (https://acme.example/jobs/2)", self.t2
        )
        mock_extractor.extract.return_value = [
            ExtractedJob(title="Senior Engineer", url="https://acme.example/jobs/1"),
            ExtractedJob(title="Product Designer", url="https://acme.example/jobs/2"),
        ]

        result = run_scrape(self.company)

        mock_extractor.extract.assert_called_once()
        self.assertFalse(result.skipped)
        self.assertEqual(result.jobs_found, 2)
        second_hash = Company.objects.get(pk=self.company.pk).last_content_hash
        self.assertNotEqual(first_hash, second_hash)

    @mock.patch("app.pipeline.notify_new_recommended_jobs")
    @mock.patch("app.pipeline.extractor")
    @mock.patch("app.pipeline.fetch_company")
    @mock.patch("app.pipeline.write_raw_html")
    def test_raw_html_is_written_even_when_skipped(self, mock_write_raw, mock_fetch, mock_extractor, mock_notify):
        text = "Senior Engineer (https://acme.example/jobs/1)"
        mock_fetch.return_value = fake_fetch(text, self.t1)
        mock_extractor.extract.return_value = [ExtractedJob(title="Senior Engineer", url="https://acme.example/jobs/1")]
        run_scrape(self.company)
        mock_write_raw.reset_mock()

        mock_fetch.return_value = fake_fetch(text, self.t2)
        run_scrape(self.company)

        mock_write_raw.assert_called_once()


class RunScrapesConcurrentlyTest(TestCase):
    def setUp(self):
        self.acme = Company.objects.create(
            name="Acme", url="https://acme.example/jobs", frequency="0 * * * *"
        )
        self.globex = Company.objects.create(
            name="Globex", url="https://globex.example/jobs", frequency="0 * * * *"
        )

    @mock.patch("app.pipeline.run_scrape")
    def test_returns_one_outcome_per_company_in_order(self, mock_run_scrape):
        results_by_id = {
            self.acme.id: ScrapeResult(company_id=self.acme.id, jobs_found=3, scraped_at=django_timezone.now()),
            self.globex.id: ScrapeResult(company_id=self.globex.id, jobs_found=5, scraped_at=django_timezone.now()),
        }
        mock_run_scrape.side_effect = lambda company, **kwargs: results_by_id[company.id]

        outcomes = run_scrapes_concurrently([self.acme, self.globex])

        self.assertEqual([company.id for company, _ in outcomes], [self.acme.id, self.globex.id])
        self.assertEqual(outcomes[0][1], results_by_id[self.acme.id])
        self.assertEqual(outcomes[1][1], results_by_id[self.globex.id])

    @mock.patch("app.pipeline.run_scrape")
    def test_one_failure_does_not_prevent_other_results(self, mock_run_scrape):
        def fake(company, **kwargs):
            if company.id == self.acme.id:
                raise RuntimeError("boom")
            return ScrapeResult(company_id=company.id, jobs_found=5, scraped_at=django_timezone.now())

        mock_run_scrape.side_effect = fake

        outcomes = run_scrapes_concurrently([self.acme, self.globex])

        outcomes_by_id = {company.id: outcome for company, outcome in outcomes}
        self.assertIsInstance(outcomes_by_id[self.acme.id], RuntimeError)
        self.assertIsInstance(outcomes_by_id[self.globex.id], ScrapeResult)
        self.assertEqual(outcomes_by_id[self.globex.id].jobs_found, 5)

    @mock.patch("app.pipeline.run_scrape")
    def test_notify_kwarg_passed_through(self, mock_run_scrape):
        mock_run_scrape.return_value = ScrapeResult(
            company_id=self.acme.id, jobs_found=0, scraped_at=django_timezone.now()
        )

        run_scrapes_concurrently([self.acme], notify=False)

        for call in mock_run_scrape.call_args_list:
            self.assertEqual(call.kwargs, {"notify": False})
