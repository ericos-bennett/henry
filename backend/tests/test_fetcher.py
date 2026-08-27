"""Hermetic tests for fetch_company, using data: URLs (no network). The
pagination fixtures embed inline <script> — Chromium runs JS in a top-level
data: URL, so a "Load more" button / numbered pager / infinite scroll can be
exercised without a live site."""

from __future__ import annotations

import unittest
from urllib.parse import quote

from app.config import PlaywrightSettings
from app.fetcher import collapse_whitespace, fetch_company
from app.models import Company

SETTINGS = PlaywrightSettings(headless=True, timeout_ms=10_000, max_pages=10)


def _company(html: str) -> Company:
    return Company(name="Acme", url=f"data:text/html,{quote(html)}", frequency="0 * * * *")


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

# "Load more" appends rows to the same list until all 6 are shown, then removes
# itself — the accumulating-DOM pattern.
LOAD_MORE = """
<html><body>
<div id="list">
  <div class="job"><a href="https://acme.example/jobs/1">Job 1</a></div>
  <div class="job"><a href="https://acme.example/jobs/2">Job 2</a></div>
</div>
<button id="more">Load more</button>
<script>
  document.getElementById('more').addEventListener('click', () => {
    const list = document.getElementById('list');
    const n = list.children.length;
    const d = document.createElement('div');
    d.className = 'job';
    d.innerHTML = '<a href="https://acme.example/jobs/' + (n + 1) + '">Job ' + (n + 1) + '</a>';
    list.appendChild(d);
    if (list.children.length >= 6) document.getElementById('more').remove();
  });
</script>
</body></html>
"""

# Numbered pager: "Next" (in a <nav>, i.e. inside stripped noise) swaps in a
# fresh 3-item slice and disables itself on the last page — the replacing-DOM
# pattern.
NUMBERED = """
<html><body>
<div id="list"></div>
<nav class="pagination"><a id="next" aria-label="Next page" href="#">Next</a></nav>
<script>
  let page = 1; const per = 3, total = 7;
  const render = () => {
    const list = document.getElementById('list');
    list.innerHTML = '';
    for (let i = (page - 1) * per; i < Math.min(page * per, total); i++) {
      const d = document.createElement('div');
      d.innerHTML = '<a href="https://acme.example/jobs/' + (i + 1) + '">Role ' + (i + 1) + '</a>';
      list.appendChild(d);
    }
    document.getElementById('next').setAttribute('aria-disabled', page * per >= total ? 'true' : 'false');
  };
  document.getElementById('next').addEventListener('click', (e) => {
    e.preventDefault();
    if (page * per < total) { page++; render(); }
  });
  render();
</script>
</body></html>
"""

# The only pagination signal is the anchor's own text ("Next") — and it has an
# href, so text capture annotates it with " (url)". The annotation must not stick
# around and break the :text-is("Next") match on the next iteration.
NEXT_BY_TEXT_ONLY = """
<html><body>
<div id="list"></div>
<a id="next" href="#page">Next</a>
<script>
  let page = 1; const per = 2, total = 5;
  const render = () => {
    const list = document.getElementById('list');
    list.innerHTML = '';
    for (let i = (page - 1) * per; i < Math.min(page * per, total); i++) {
      const d = document.createElement('div');
      d.innerHTML = '<a href="https://acme.example/jobs/' + (i + 1) + '">Gig ' + (i + 1) + '</a>';
      list.appendChild(d);
    }
    document.getElementById('next').style.display = page * per >= total ? 'none' : '';
  };
  document.getElementById('next').addEventListener('click', (e) => {
    e.preventDefault();
    if (page * per < total) { page++; render(); }
  });
  render();
</script>
</body></html>
"""

# No pagination control; more rows append each time the page is scrolled to the
# bottom, up to 8.
INFINITE_SCROLL = """
<html><body>
<div id="list"></div>
<div style="height: 1500px"></div>
<script>
  let loaded = 0; const total = 8;
  const add = () => {
    for (let k = 0; k < 2 && loaded < total; k++) {
      loaded++;
      const d = document.createElement('div');
      d.innerHTML = '<a href="https://acme.example/jobs/' + loaded + '">Gig ' + loaded + '</a>';
      document.getElementById('list').appendChild(d);
    }
  };
  add();
  window.addEventListener('scroll', () => {
    if (window.scrollY + window.innerHeight >= document.body.offsetHeight - 5) add();
  });
</script>
</body></html>
"""

# "Load more" that never exhausts — used to check the max_pages safety cap.
ENDLESS = """
<html><body>
<div id="list"><div class="job"><a href="https://acme.example/jobs/1">Job 1</a></div></div>
<button id="more">Load more</button>
<script>
  document.getElementById('more').addEventListener('click', () => {
    const list = document.getElementById('list');
    const n = list.children.length + 1;
    const d = document.createElement('div');
    d.innerHTML = '<a href="https://acme.example/jobs/' + n + '">Job ' + n + '</a>';
    list.appendChild(d);
  });
</script>
</body></html>
"""


class FetchCompanyTest(unittest.TestCase):
    def test_appends_absolute_link_urls_to_visible_text(self):
        result = fetch_company(_company(HTML), SETTINGS)

        self.assertIn("https://acme.example/jobs/1", result.text)
        self.assertIn("https://acme.example/jobs/2", result.text)
        # Nested structure inside a whole-card anchor is preserved, not flattened.
        self.assertIn("Senior Engineer", result.text)
        self.assertIn("Location: Tokyo, Japan", result.text)
        self.assertIn("Location: London, UK", result.text)

    def test_strips_boilerplate_noise(self):
        result = fetch_company(_company(HTML_WITH_NOISE), SETTINGS)

        self.assertNotIn("Home | Careers | About", result.text)
        self.assertNotIn("Acme Corp", result.text)
        self.assertNotIn("decorative icon text", result.text)
        self.assertNotIn("Copyright 2026", result.text)
        self.assertIn("Senior Engineer", result.text)
        self.assertIn("https://acme.example/jobs/1", result.text)
        self.assertIn("Location: Tokyo, Japan", result.text)

    def test_follows_load_more_button(self):
        result = fetch_company(_company(LOAD_MORE), SETTINGS)

        for i in range(1, 7):
            self.assertIn(f"Job {i}", result.text)
            self.assertIn(f"https://acme.example/jobs/{i}", result.text)
        # Accumulating DOM shouldn't produce N copies of the early rows.
        self.assertEqual(result.text.count("Job 1 "), 1)

    def test_follows_numbered_pagination_with_control_in_stripped_noise(self):
        result = fetch_company(_company(NUMBERED), SETTINGS)

        for i in range(1, 8):
            self.assertIn(f"Role {i}", result.text)
            self.assertIn(f"https://acme.example/jobs/{i}", result.text)

    def test_follows_next_control_matched_only_by_its_text(self):
        result = fetch_company(_company(NEXT_BY_TEXT_ONLY), SETTINGS)

        for i in range(1, 6):
            self.assertIn(f"Gig {i}", result.text)

    def test_follows_infinite_scroll(self):
        result = fetch_company(_company(INFINITE_SCROLL), SETTINGS)

        for i in range(1, 9):
            self.assertIn(f"Gig {i}", result.text)

    def test_stops_at_max_pages(self):
        result = fetch_company(_company(ENDLESS), PlaywrightSettings(headless=True, timeout_ms=10_000, max_pages=4))

        # 4 pages: the initial row + one more per click for 3 clicks = 4 rows.
        self.assertIn("Job 4", result.text)
        self.assertNotIn("Job 5", result.text)

    def test_single_page_is_unaffected(self):
        result = fetch_company(_company(HTML), SETTINGS)

        self.assertEqual(result.text.count("Senior Engineer"), 1)
        self.assertEqual(result.text.count("Product Designer"), 1)


class CollapseWhitespaceTest(unittest.TestCase):
    def test_collapses_long_runs_of_blank_lines(self):
        self.assertEqual(collapse_whitespace("a\n\n\n\n\nb"), "a\n\nb")

    def test_strips_trailing_line_whitespace(self):
        self.assertEqual(collapse_whitespace("a   \nb\t\n"), "a\nb")

    def test_strips_leading_and_trailing_overall_whitespace(self):
        self.assertEqual(collapse_whitespace("\n\n  a\nb  \n\n"), "a\nb")
