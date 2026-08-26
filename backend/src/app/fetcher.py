from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

from app.config import PlaywrightSettings
from app.models import Company

# Generic layout chrome that isn't job content on any career page — safe to strip
# unconditionally since there's no per-company selector config to fall back on.
NOISE_SELECTORS = (
    "nav, header, footer, "
    '[aria-hidden="true"], [role="navigation"], [role="banner"], [role="contentinfo"]'
)


@dataclass
class FetchResult:
    company_id: str
    url: str
    fetched_at: datetime
    html: str
    text: str
    title: str


def collapse_whitespace(text: str) -> str:
    """Collapse runs of 3+ newlines (left behind by removed layout chrome and
    inner_text's block-level spacing) down to at most one blank line, and drop
    trailing whitespace on each line."""
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def fetch_company(company: Company, settings: PlaywrightSettings) -> FetchResult:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=settings.headless)
        try:
            page = browser.new_page()
            page.goto(company.url, wait_until="networkidle", timeout=settings.timeout_ms)
            html = page.content()
            # Remove noise nodes before annotating links — no reason to annotate
            # hrefs inside nodes that are about to be deleted.
            page.evaluate(
                f"""() => {{
                    document.querySelectorAll({NOISE_SELECTORS!r}).forEach((el) => el.remove());
                }}"""
            )
            # Append each link's absolute URL as trailing text inside the anchor
            # (not replacing its content) so inner_text still exposes hrefs for the
            # extractor without flattening a job card's internal line breaks.
            page.evaluate(
                """() => {
                    document.querySelectorAll('a[href]').forEach((a) => {
                        a.appendChild(document.createTextNode(` (${a.href})`));
                    });
                }"""
            )
            text = collapse_whitespace(page.inner_text("body"))
            title = page.title()
        finally:
            browser.close()

    return FetchResult(
        company_id=company.id,
        url=company.url,
        fetched_at=datetime.now(timezone.utc),
        html=html,
        text=text,
        title=title,
    )
