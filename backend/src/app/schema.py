from __future__ import annotations

from pydantic import BaseModel, Field


class SalaryRange(BaseModel):
    min: float | None = None
    max: float | None = None
    currency: str | None = None


class ExtractedJob(BaseModel):
    title: str
    url: str | None = Field(
        default=None,
        description=(
            "Direct link to this job's detail/application page, if available. "
            "In the source text, a link's absolute URL appears in parentheses "
            "right after that link's text, e.g. 'Apply now (https://example.com/jobs/123)' "
            "— use the URL nearest this job's title/listing block."
        ),
    )
    location: str | None = None
    department: str | None = None
    employment_type: str | None = None
    salary_range: SalaryRange | None = None
    posted_date: str | None = None
