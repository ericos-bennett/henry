from __future__ import annotations

from datetime import datetime

from croniter import croniter
from ninja import ModelSchema, Schema
from pydantic import field_validator

from app.models import Company, JobPosting


class CompanyOut(ModelSchema):
    class Meta:
        model = Company
        fields = ["id", "name", "url", "frequency", "enabled"]


class CompanyIn(Schema):
    name: str
    url: str
    frequency: str
    enabled: bool = True

    @field_validator("frequency")
    @classmethod
    def validate_cron(cls, value: str) -> str:
        if not croniter.is_valid(value):
            raise ValueError(f"'{value}' is not a valid cron expression")
        return value


class JobPostingOut(ModelSchema):
    class Meta:
        model = JobPosting
        fields = "__all__"


class ScrapeResult(Schema):
    company_id: str
    jobs_found: int
    scraped_at: datetime
