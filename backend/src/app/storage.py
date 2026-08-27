from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.models import JobPosting


def timestamp_for_filename(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


def write_raw_html(storage_root: str | Path, company_id: int, fetched_at: datetime, html: str) -> Path:
    raw_dir = Path(storage_root) / str(company_id) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_path = raw_dir / f"{timestamp_for_filename(fetched_at)}.html"
    out_path.write_text(html)
    return out_path


def save_job_postings(jobs: list[JobPosting]) -> list[JobPosting]:
    if not jobs:
        return []

    # jobs is always a homogeneous batch from one scrape: one company, one
    # latest_scrape_timestamp (see to_job_postings in extractor.py). A job whose
    # job_key continues an unbroken streak from the immediately preceding run
    # gets its existing row updated in place, so an unchanged posting doesn't
    # accumulate a fresh row every scrape. Anything else — a job_key never seen
    # before, or one reappearing after a gap — gets a brand new row, so a
    # reappearance reads as a fresh lifetime (is_new compares
    # first_scrape_timestamp to latest_scrape_timestamp) rather than silently
    # extending the old row's streak across the gap.
    company = jobs[0].company
    scraped_at = jobs[0].latest_scrape_timestamp
    previous_run_at = (
        JobPosting.objects.filter(company=company, latest_scrape_timestamp__lt=scraped_at)
        .order_by("-latest_scrape_timestamp")
        .values_list("latest_scrape_timestamp", flat=True)
        .first()
    )

    job_keys = [job.job_key for job in jobs]
    latest_by_key: dict[str, JobPosting] = {}
    for row in JobPosting.objects.filter(company=company, job_key__in=job_keys).order_by(
        "latest_scrape_timestamp"
    ):
        latest_by_key[row.job_key] = row  # last write wins -> most recent lifetime per job_key

    saved = []
    for job in jobs:
        existing = latest_by_key.get(job.job_key)
        if existing is not None and existing.latest_scrape_timestamp == previous_run_at:
            existing.title = job.title
            existing.url = job.url
            existing.location = job.location
            existing.department = job.department
            existing.employment_type = job.employment_type
            existing.posted_date = job.posted_date
            existing.salary_min = job.salary_min
            existing.salary_max = job.salary_max
            existing.salary_currency = job.salary_currency
            existing.latest_scrape_timestamp = scraped_at
            existing.save()
            saved.append(existing)
        else:
            job.save()
            saved.append(job)

    return saved
