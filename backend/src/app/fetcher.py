from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.config import PlaywrightSettings
from app.models import Company

logger = logging.getLogger(__name__)

# Generic layout chrome that isn't job content on any career page — safe to strip
# unconditionally since there's no per-company selector config to fall back on.
NOISE_SELECTORS = (
    "nav, header, footer, "
    '[aria-hidden="true"], [role="navigation"], [role="banner"], [role="contentinfo"]'
)

# Some sites (chat widgets, analytics beacons) poll continuously and never go
# fully network-idle, so idleness is only ever waited for on a best-effort basis
# after the page has already loaded — never as the condition goto() itself
# blocks on, which would otherwise time out the whole fetch outright.
NETWORK_IDLE_GRACE_MS = 10_000

# Playwright's default headless Chrome UA/viewport reads as a bot to some sites'
# WAFs (e.g. Cloudflare); a realistic desktop Chrome fingerprint alone is enough
# to get past that on non-adversarial career pages, without doing anything to
# actively defeat CAPTCHA/challenge pages.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1440, "height": 900}

# navigator.webdriver is the one signal Playwright sets that a real Chrome
# install never does; clearing it removes the single most common automated
# fingerprint check without touching anything else about the page.
_HIDE_WEBDRIVER_SCRIPT = "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"


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
            context = browser.new_context(user_agent=USER_AGENT, viewport=VIEWPORT, locale="en-US")
            context.add_init_script(_HIDE_WEBDRIVER_SCRIPT)
            page = context.new_page()
            page.goto(company.url, wait_until="load", timeout=settings.timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=min(settings.timeout_ms, NETWORK_IDLE_GRACE_MS))
            except PlaywrightTimeoutError:
                logger.warning("networkidle not reached for %s, proceeding with loaded content", company.url)
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
