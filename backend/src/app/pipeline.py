from __future__ import annotations

import logging

from app.config import AppConfig, load_config
from app.extractor import ExtractionError, LLMExtractor, get_extractor, to_job_postings
from app.fetcher import fetch_company
from app.models import Company
from app.schemas import ScrapeResult
from app.storage import save_job_postings, write_raw_html

logger = logging.getLogger(__name__)

config: AppConfig = load_config()
extractor: LLMExtractor = get_extractor(config.settings.llm)


def run_scrape(company: Company) -> ScrapeResult:
    """Fetch, extract, and persist job postings for one company.

    Shared by POST /companies/{id}/scrape and the scheduler tick so the
    orchestration logic isn't duplicated.
    """
    result = fetch_company(company, config.settings.playwright)
    write_raw_html(config.settings.storage.root, company.id, result.fetched_at, result.html)

    try:
        extracted = extractor.extract(result.text)
    except Exception as e:
        raise ExtractionError(str(e)) from e
    jobs = to_job_postings(extracted, company=company, scraped_at=result.fetched_at)
    saved = save_job_postings(jobs)

    logger.info("scraped %s: %d jobs found", company.id, len(saved))
    return ScrapeResult(company_id=company.id, jobs_found=len(saved), scraped_at=result.fetched_at)
