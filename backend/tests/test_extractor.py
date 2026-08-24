"""Hermetic tests for AnthropicExtractor, using a stubbed anthropic client (no network)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.extractor import AnthropicExtractor, _ExtractedJobList
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
