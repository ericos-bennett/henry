from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import Page, sync_playwright

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

# After a pagination click / scroll, how long to let a client-side re-render settle
# once the network is (best-effort) idle again.
PAGINATION_SETTLE_MS = 600

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

# Ordered most-specific/safest first — the first visible, enabled match wins. rel=next
# / aria-label / title matches are unambiguous; the trailing class/id/text guesses are
# a last resort for sites that expose nothing better. `:has-text()` is case-insensitive
# substring matching; `:text-is()` is exact trimmed text. Disabled states are filtered
# in _find_pagination_control, not here.
_PAGINATION_SELECTORS = (
    'a[rel="next"]',
    'button[rel="next"]',
    '[aria-label="Next" i]',
    '[aria-label="Next page" i]',
    '[aria-label="Go to next page" i]',
    '[aria-label*="next" i][aria-label*="page" i]',
    'a[title="Next" i]',
    'button[title="Next" i]',
    'button:has-text("Load more")',
    'button:has-text("Show more")',
    'button:has-text("View more")',
    'a:has-text("Load more")',
    'a:has-text("Show more")',
    '[class*="pagination" i] a[class*="next" i]',
    '[class*="pagination" i] button[class*="next" i]',
    '[class*="pager" i] a[class*="next" i]',
    'a[class*="next" i][class*="page" i]',
    'button[class*="next" i][class*="page" i]',
    'a[id*="next" i]',
    'button[id*="next" i]',
    'button:text-is("Next")',
    'a:text-is("Next")',
)

# Runs entirely in the page and leaves the DOM as it found it: hides layout chrome
# (so inner_text skips it), appends each link's absolute URL as a trailing text
# node inside the anchor (so the extractor sees hrefs without job-card line breaks
# being flattened), reads the visible text, then removes those nodes and unhides
# the chrome. Non-destructive so it can be re-run across "load more" / numbered
# pages without polluting text or breaking pagination-control text matching.
_CAPTURE_TEXT_JS = """
() => {
    const hidden = [];
    document.querySelectorAll(%(noise)s).forEach((el) => {
        hidden.push([el, el.style.display]);
        el.style.display = 'none';
    });
    const added = [];
    document.querySelectorAll('a[href]').forEach((a) => {
        const node = document.createTextNode(` (${a.href})`);
        a.appendChild(node);
        added.push(node);
    });
    const text = document.body.innerText;
    added.forEach((node) => node.remove());
    hidden.forEach(([el, display]) => { el.style.display = display; });
    return text;
}
""" % {"noise": repr(NOISE_SELECTORS)}


@dataclass
class FetchResult:
    company_id: int
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


def _wait_settled(page: Page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_GRACE_MS)
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(PAGINATION_SETTLE_MS)


def _find_pagination_control(page: Page):
    """First visible, enabled next-page / load-more control, or None."""
    for selector in _PAGINATION_SELECTORS:
        control = page.locator(selector).first
        try:
            if not control.is_visible() or not control.is_enabled():
                continue
            if control.get_attribute("aria-disabled") == "true":
                continue
            if "disabled" in (control.get_attribute("class") or ""):
                continue
            return control
        except PlaywrightError:
            continue
    return None


def _is_accumulating_reread(prev: str, curr: str) -> bool:
    """True when `curr` is `prev` with more rows added to the same DOM — "load
    more" / infinite scroll. One line is allowed to have vanished (the "Load more"
    button removing itself on the final page) once there are enough lines for that
    to be unambiguous."""
    prev_lines = [line for line in prev.splitlines() if line.strip()]
    curr_lines = set(curr.splitlines())
    missing = sum(1 for line in prev_lines if line not in curr_lines)
    if len(prev_lines) <= 2:
        return missing == 0
    return missing <= 1


def _merge_capture(captures: list[str], text: str) -> None:
    """Fold one page's captured text into the running list: replace the last
    capture if this is an accumulating re-read of it (load more / infinite
    scroll), otherwise append it (numbered pagination swaps in a distinct slice)
    and the slices are concatenated at the end."""
    if captures and _is_accumulating_reread(captures[-1], text):
        captures[-1] = text
    else:
        captures.append(text)


def _collect_paginated_text(page: Page, settings: PlaywrightSettings) -> str:
    """Read the job-listing text, following "next page" / "load more" / infinite
    scroll up to settings.max_pages times. Stops as soon as a step yields nothing
    new, so a page with no pagination pays for one extra scroll and nothing more."""
    captures: list[str] = []
    last_text: str | None = None

    for page_num in range(1, settings.max_pages + 1):
        text = page.evaluate(_CAPTURE_TEXT_JS).strip()
        if text == last_text:
            break
        _merge_capture(captures, text)
        last_text = text

        control = _find_pagination_control(page)
        if control is not None:
            try:
                control.scroll_into_view_if_needed(timeout=2_000)
                control.click(timeout=5_000)
            except PlaywrightError:
                logger.warning("pagination click failed for %s at page %d, stopping", page.url, page_num)
                break
            _wait_settled(page)
            continue

        # No control — try one scroll in case results load lazily on scroll. If the
        # page doesn't grow, there's nothing more to get.
        before_height = page.evaluate("() => document.body.scrollHeight")
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        _wait_settled(page)
        if page.evaluate("() => document.body.scrollHeight") == before_height:
            break
    else:
        logger.warning("hit max_pages=%d while paginating %s", settings.max_pages, page.url)

    return collapse_whitespace("\n\n".join(captures))


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
            text = _collect_paginated_text(page, settings)
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
