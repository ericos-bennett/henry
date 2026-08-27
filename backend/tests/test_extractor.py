"""Hermetic tests for AnthropicExtractor, using a stubbed anthropic client (no network)."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.extractor import AnthropicExtractor, _ExtractedJobList, to_job_postings
from app.models import Company
from app.schema import ExtractedJob


class AnthropicExtractorTest(unittest.TestCase):
    def test_extract_returns_parsed_jobs(self):
        extractor = AnthropicExtractor(api_key="test-key", model="claude-haiku-4-5")

        parsed = _ExtractedJobList(jobs=[ExtractedJob(title="Software Engineer", location="Remote")])
        mock_response = MagicMock(parsed_output=parsed)
        extractor._client = MagicMock()
        extractor._client.messages.parse.return_value = mock_response

        jobs = extractor.extract("some career page text")

        self.assertEqual(jobs, parsed.jobs)
        _, kwargs = extractor._client.messages.parse.call_args
        self.assertEqual(kwargs["model"], "claude-haiku-4-5")
        self.assertEqual(kwargs["output_format"], _ExtractedJobList)
        self.assertIn("some career page text", kwargs["messages"][0]["content"])

    def test_extract_returns_empty_list_when_no_jobs(self):
        extractor = AnthropicExtractor(api_key="test-key", model="claude-haiku-4-5")

        parsed = _ExtractedJobList(jobs=[])
        extractor._client = MagicMock()
        extractor._client.messages.parse.return_value = MagicMock(parsed_output=parsed)

        self.assertEqual(extractor.extract("no jobs here"), [])


class ToJobPostingsTest(unittest.TestCase):
    def test_dedupes_jobs_that_hash_to_the_same_job_key(self):
        # Two ExtractedJobs with the same url (or same title when url is missing)
        # hash to the same job_key via _make_job_key — e.g. a job double-listed under
        # two categories on the career page. Without dedup, save_job_postings()
        # would try to treat both as the same continuing/new lifetime within one batch.
        company = Company(name="Acme", url="https://acme.example/jobs", frequency="0 * * * *")
        scraped_at = datetime(2026, 8, 24, tzinfo=timezone.utc)
        jobs = [
            ExtractedJob(title="Software Engineer", url="https://acme.example/jobs/1"),
            ExtractedJob(title="Software Engineer (Backend)", url="https://acme.example/jobs/1"),
            ExtractedJob(title="Designer", url="https://acme.example/jobs/2"),
        ]

        postings = to_job_postings(jobs, company=company, scraped_at=scraped_at)

        self.assertEqual([p.title for p in postings], ["Software Engineer", "Designer"])
        self.assertEqual(len({p.job_key for p in postings}), len(postings))

    def test_keeps_same_title_jobs_in_different_locations(self):
        # e.g. Kraken listing "Client Delivery Lead" separately for Tokyo and
        # Melbourne, with no url to distinguish them — these are two real postings,
        # not a duplicate, so both must survive with distinct job_keys.
        company = Company(name="Kraken", url="https://jobs.ashbyhq.com/krakentech", frequency="0 * * * *")
        scraped_at = datetime(2026, 8, 24, tzinfo=timezone.utc)
        jobs = [
            ExtractedJob(title="Client Delivery Lead", location="Tokyo, Japan"),
            ExtractedJob(title="Client Delivery Lead", location="Melbourne, Australia"),
        ]

        postings = to_job_postings(jobs, company=company, scraped_at=scraped_at)

        self.assertEqual(len(postings), 2)
        self.assertEqual(len({p.job_key for p in postings}), 2)

    def test_strips_trailing_apply_segment_from_job_url(self):
        # Lever links straight to the application form via a trailing '/apply'
        # rather than the job's description page — normalize it away.
        company = Company(name="Voltus", url="https://www.voltus.co/jobs", frequency="0 * * * *")
        scraped_at = datetime(2026, 8, 24, tzinfo=timezone.utc)
        jobs = [ExtractedJob(title="Software Engineer", url="https://jobs.lever.co/voltus/abc123/apply")]

        postings = to_job_postings(jobs, company=company, scraped_at=scraped_at)

        self.assertEqual(postings[0].url, "https://jobs.lever.co/voltus/abc123")

    def test_strips_trailing_apply_segment_with_trailing_slash(self):
        company = Company(name="Voltus", url="https://www.voltus.co/jobs", frequency="0 * * * *")
        scraped_at = datetime(2026, 8, 24, tzinfo=timezone.utc)
        jobs = [ExtractedJob(title="Software Engineer", url="https://jobs.lever.co/voltus/abc123/apply/")]

        postings = to_job_postings(jobs, company=company, scraped_at=scraped_at)

        self.assertEqual(postings[0].url, "https://jobs.lever.co/voltus/abc123")

    def test_leaves_non_apply_urls_unchanged(self):
        company = Company(name="Voltus", url="https://www.voltus.co/jobs", frequency="0 * * * *")
        scraped_at = datetime(2026, 8, 24, tzinfo=timezone.utc)
        jobs = [ExtractedJob(title="Software Engineer", url="https://jobs.lever.co/voltus/abc123")]

        postings = to_job_postings(jobs, company=company, scraped_at=scraped_at)

        self.assertEqual(postings[0].url, "https://jobs.lever.co/voltus/abc123")

    def test_does_not_strip_apply_when_it_is_the_entire_path(self):
        # Stripping would leave a bare domain with no job identifier — keep the
        # original url rather than destroy the only distinguishing path segment.
        company = Company(name="Acme", url="https://acme.example/jobs", frequency="0 * * * *")
        scraped_at = datetime(2026, 8, 24, tzinfo=timezone.utc)
        jobs = [ExtractedJob(title="Software Engineer", url="https://acme.example/apply")]

        postings = to_job_postings(jobs, company=company, scraped_at=scraped_at)

        self.assertEqual(postings[0].url, "https://acme.example/apply")
