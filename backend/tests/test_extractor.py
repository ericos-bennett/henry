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
    def test_dedupes_jobs_that_hash_to_the_same_job_id(self):
        # Two ExtractedJobs with the same url (or same title when url is missing)
        # hash to the same job_id via _make_job_id — e.g. a job double-listed under
        # two categories on the career page. Without dedup this crashes bulk_create
        # on the (job_id, scraped_at) unique constraint.
        company = Company(id="acme", name="Acme", url="https://acme.example/jobs", frequency="0 * * * *")
        scraped_at = datetime(2026, 8, 24, tzinfo=timezone.utc)
        jobs = [
            ExtractedJob(title="Software Engineer", url="https://acme.example/jobs/1"),
            ExtractedJob(title="Software Engineer (Backend)", url="https://acme.example/jobs/1"),
            ExtractedJob(title="Designer", url="https://acme.example/jobs/2"),
        ]

        postings = to_job_postings(jobs, company=company, scraped_at=scraped_at)

        self.assertEqual([p.title for p in postings], ["Software Engineer", "Designer"])
        self.assertEqual(len({p.job_id for p in postings}), len(postings))
