from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.schema import JobPosting


def timestamp_for_filename(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


def write_raw_html(storage_root: str | Path, site_id: str, fetched_at: datetime, html: str) -> Path:
    raw_dir = Path(storage_root) / site_id / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_path = raw_dir / f"{timestamp_for_filename(fetched_at)}.html"
    out_path.write_text(html)
    return out_path


def write_snapshot(
    storage_root: str | Path, site_id: str, scraped_at: datetime, jobs: list[JobPosting]
) -> Path:
    site_dir = Path(storage_root) / site_id
    site_dir.mkdir(parents=True, exist_ok=True)
    out_path = site_dir / f"{timestamp_for_filename(scraped_at)}.json"
    payload = [job.model_dump(mode="json") for job in jobs]
    out_path.write_text(json.dumps(payload, indent=2))
    return out_path
