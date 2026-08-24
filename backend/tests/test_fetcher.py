"""Hermetic test for fetch_company's link-annotation, using a data: URL (no network)."""

from __future__ import annotations

import unittest
from urllib.parse import quote

from app.config import PlaywrightSettings
from app.fetcher import fetch_company
from app.models import Company

HTML = """
<html><body>
<div class="job">
  <a href="https://acme.example/jobs/1">
    <strong>Senior Engineer</strong>
    <div>Location: Tokyo, Japan</div>
  </a>
</div>
<div class="job">
  <a href="https://acme.example/jobs/2">Product Designer</a>
  <div>Location: London, UK</div>
</div>
</body></html>
"""


class FetchCompanyTest(unittest.TestCase):
    def test_appends_absolute_link_urls_to_visible_text(self):
        company = Company(id="acme", name="Acme", url=f"data:text/html,{quote(HTML)}", frequency="0 * * * *")

        result = fetch_company(company, PlaywrightSettings(headless=True, timeout_ms=10_000))

        self.assertIn("https://acme.example/jobs/1", result.text)
        self.assertIn("https://acme.example/jobs/2", result.text)
        # Nested structure inside a whole-card anchor is preserved, not flattened.
        self.assertIn("Senior Engineer", result.text)
        self.assertIn("Location: Tokyo, Japan", result.text)
        self.assertIn("Location: London, UK", result.text)
