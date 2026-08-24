from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.models import JobPosting


def timestamp_for_filename(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


def write_raw_html(storage_root: str | Path, company_id: str, fetched_at: datetime, html: str) -> Path:
    raw_dir = Path(storage_root) / company_id / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_path = raw_dir / f"{timestamp_for_filename(fetched_at)}.html"
    out_path.write_text(html)
    return out_path


def save_job_postings(jobs: list[JobPosting]) -> list[JobPosting]:
    if not jobs:
        return []

    # jobs is always a homogeneous batch from one scrape: one company, one scraped_at
    # (see to_job_postings in extractor.py). Diff against the immediately preceding
    # run for that company to flag postings that weren't there last time.
    company = jobs[0].source_company
    scraped_at = jobs[0].scraped_at
    previous_scraped_at = (
        JobPosting.objects.filter(source_company=company, scraped_at__lt=scraped_at)
        .order_by("-scraped_at")
        .values_list("scraped_at", flat=True)
        .first()
    )
    if previous_scraped_at is not None:
        previous_job_ids = set(
            JobPosting.objects.filter(
                source_company=company, scraped_at=previous_scraped_at
            ).values_list("job_id", flat=True)
        )
        for job in jobs:
            job.is_new = job.job_id not in previous_job_ids

    return JobPosting.objects.bulk_create(jobs)
