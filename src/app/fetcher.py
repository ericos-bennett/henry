from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

from app.config import PlaywrightSettings
from app.models import Company


@dataclass
class FetchResult:
    company_id: str
    url: str
    fetched_at: datetime
    html: str
    text: str
    title: str


def fetch_company(company: Company, settings: PlaywrightSettings) -> FetchResult:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=settings.headless)
        try:
            page = browser.new_page()
            page.goto(company.url, wait_until="networkidle", timeout=settings.timeout_ms)
            if company.wait_selector:
                page.wait_for_selector(company.wait_selector, timeout=settings.timeout_ms)
            html = page.content()
            text = page.inner_text("body")
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
