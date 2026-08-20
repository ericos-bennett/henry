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
    return JobPosting.objects.bulk_create(jobs)
