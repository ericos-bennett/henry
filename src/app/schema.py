from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SalaryRange(BaseModel):
    min: float | None = None
    max: float | None = None
    currency: str | None = None
    raw: str | None = None


class ExtractedJob(BaseModel):
    """Fields the LLM extracts directly from page content."""

    title: str
    url: str | None = None
    location: str | None = None
    department: str | None = None
    employment_type: str | None = None
    salary_range: SalaryRange | None = None
    description: str | None = None
    posted_date: str | None = None


class JobPosting(ExtractedJob):
    """An ExtractedJob plus the run metadata that makes it a full record."""

    job_id: str
    source_site_id: str
    source_url: str
    scraped_at: datetime
