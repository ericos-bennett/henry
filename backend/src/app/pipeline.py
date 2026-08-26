from __future__ import annotations

import hashlib
import logging

from app.config import AppConfig, load_config
from app.extractor import ExtractionError, LLMExtractor, get_extractor, to_job_postings
from app.fetcher import fetch_company
from app.models import Company
from app.notifications import notify_new_recommended_jobs
from app.schemas import ScrapeResult
from app.storage import save_job_postings, write_raw_html

logger = logging.getLogger(__name__)

config: AppConfig = load_config()
extractor: LLMExtractor = get_extractor(config.settings.llm)


def run_scrape(company: Company, *, notify: bool = True) -> ScrapeResult:
    """Fetch, extract, and persist job postings for one company.

    Shared by POST /companies/{id}/scrape and the scheduler tick so the
    orchestration logic isn't duplicated. `notify=False` skips the per-company
    is_new-gated notification email — used by the "scrape all" flow, which sends
    one combined digest across all companies instead. The email is also always
    skipped on a company's first-ever scrape, regardless of `notify`.
    """
    result = fetch_company(company, config.settings.playwright)
    write_raw_html(config.settings.storage.root, company.id, result.fetched_at, result.html)

    # Checked before saving: every job on a company's very first scrape has
    # first_scrape_timestamp == latest_scrape_timestamp (is_new=True) by
    # construction, since there's nothing earlier to compare against — without
    # this check that would email the owner about every job the moment a
    # company is added, rather than only genuinely new postings going forward.
    is_first_scrape = not company.job_postings.exists()

    content_hash = hashlib.sha256(result.text.encode()).hexdigest()
    if not is_first_scrape and content_hash == company.last_content_hash:
        # Page text is byte-for-byte unchanged since the last successful scrape
        # (post-trim, per fetch_company) — nothing new to extract or notify about.
        jobs_found = _current_job_count(company)
        logger.info("scraped %s: unchanged, skipped extraction (%d jobs)", company.id, jobs_found)
        return ScrapeResult(
            company_id=company.id, jobs_found=jobs_found, scraped_at=result.fetched_at, skipped=True
        )

    try:
        extracted = extractor.extract(result.text)
    except Exception as e:
        raise ExtractionError(str(e)) from e
    jobs = to_job_postings(extracted, company=company, scraped_at=result.fetched_at)
    saved = save_job_postings(jobs)

    company.last_content_hash = content_hash
    company.save(update_fields=["last_content_hash"])

    if notify and not is_first_scrape:
        try:
            notify_new_recommended_jobs(company, saved)
        except Exception:
            logger.exception("failed to send notification email for %s", company.id)

    logger.info("scraped %s: %d jobs found", company.id, len(saved))
    return ScrapeResult(
        company_id=company.id, jobs_found=len(saved), scraped_at=result.fetched_at, skipped=False
    )


def _current_job_count(company: Company) -> int:
    """Number of jobs from the company's most recent scrape run, i.e. its
    currently active listings — same "latest run" grouping used by
    GET /companies/{id}/jobs?latest_only=true."""
    qs = company.job_postings.all().order_by("-latest_scrape_timestamp")
    latest = qs.first()
    if latest is None:
        return 0
    return qs.filter(latest_scrape_timestamp=latest.latest_scrape_timestamp).count()
