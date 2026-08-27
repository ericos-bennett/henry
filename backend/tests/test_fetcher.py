"""Hermetic test for fetch_company's link-annotation, using a data: URL (no network)."""

from __future__ import annotations

import unittest
from urllib.parse import quote

from app.config import PlaywrightSettings
from app.fetcher import collapse_whitespace, fetch_company
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

HTML_WITH_NOISE = """
<html><body>
<nav>Home | Careers | About</nav>
<header>Acme Corp</header>
<div aria-hidden="true">decorative icon text</div>
<footer>Copyright 2026 Acme Corp. All rights reserved.</footer>
<div class="job">
  <a href="https://acme.example/jobs/1">Senior Engineer</a>
  <div>Location: Tokyo, Japan</div>
</div>
</body></html>
"""


class FetchCompanyTest(unittest.TestCase):
    def test_appends_absolute_link_urls_to_visible_text(self):
        company = Company(name="Acme", url=f"data:text/html,{quote(HTML)}", frequency="0 * * * *")

        result = fetch_company(company, PlaywrightSettings(headless=True, timeout_ms=10_000))

        self.assertIn("https://acme.example/jobs/1", result.text)
        self.assertIn("https://acme.example/jobs/2", result.text)
        # Nested structure inside a whole-card anchor is preserved, not flattened.
        self.assertIn("Senior Engineer", result.text)
        self.assertIn("Location: Tokyo, Japan", result.text)
        self.assertIn("Location: London, UK", result.text)

    def test_strips_boilerplate_noise(self):
        company = Company(
            name="Acme", url=f"data:text/html,{quote(HTML_WITH_NOISE)}", frequency="0 * * * *"
        )

        result = fetch_company(company, PlaywrightSettings(headless=True, timeout_ms=10_000))

        self.assertNotIn("Home | Careers | About", result.text)
        self.assertNotIn("Acme Corp", result.text)
        self.assertNotIn("decorative icon text", result.text)
        self.assertNotIn("Copyright 2026", result.text)
        self.assertIn("Senior Engineer", result.text)
        self.assertIn("https://acme.example/jobs/1", result.text)
        self.assertIn("Location: Tokyo, Japan", result.text)


class CollapseWhitespaceTest(unittest.TestCase):
    def test_collapses_long_runs_of_blank_lines(self):
        self.assertEqual(collapse_whitespace("a\n\n\n\n\nb"), "a\n\nb")

    def test_strips_trailing_line_whitespace(self):
        self.assertEqual(collapse_whitespace("a   \nb\t\n"), "a\nb")

    def test_strips_leading_and_trailing_overall_whitespace(self):
        self.assertEqual(collapse_whitespace("\n\n  a\nb  \n\n"), "a\nb")
