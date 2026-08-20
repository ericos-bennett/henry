from __future__ import annotations

from pydantic import BaseModel


class SalaryRange(BaseModel):
    min: float | None = None
    max: float | None = None
    currency: str | None = None
    raw: str | None = None


class ExtractedJob(BaseModel):
    title: str
    url: str | None = None
    location: str | None = None
    department: str | None = None
    employment_type: str | None = None
    salary_range: SalaryRange | None = None
    description: str | None = None
    posted_date: str | None = None
