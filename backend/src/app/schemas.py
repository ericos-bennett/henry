from __future__ import annotations

from datetime import datetime

from ninja import ModelSchema, Schema
from pydantic import field_validator

from app.models import Company, JobPosting, UserPreferences

# Kept in sync with FREQUENCY_OPTIONS in frontend/src/App.tsx, the only source of
# frequency values in the UI.
ALLOWED_FREQUENCIES = {
    "0 * * * *",  # Hourly
    "0 */8 * * *",  # Every 8 Hours
    "0 8 * * *",  # Daily
    "0 8 * * 0",  # Weekly
}


def _validate_frequency(value: str) -> str:
    if value not in ALLOWED_FREQUENCIES:
        raise ValueError(f"'{value}' is not one of the allowed frequencies: {sorted(ALLOWED_FREQUENCIES)}")
    return value


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
    def validate_frequency(cls, value: str) -> str:
        return _validate_frequency(value)


class CompanyPatch(Schema):
    enabled: bool | None = None
    frequency: str | None = None

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, value: str | None) -> str | None:
        return _validate_frequency(value) if value is not None else value


class JobPostingOut(ModelSchema):
    is_recommended: bool = False

    class Meta:
        model = JobPosting
        fields = "__all__"

    @staticmethod
    def resolve_is_recommended(obj) -> bool:
        return getattr(obj, "_is_recommended", False)


class PreferencesOut(ModelSchema):
    class Meta:
        model = UserPreferences
        fields = ["locations", "keywords"]


class PreferencesIn(Schema):
    locations: list[str] = []
    keywords: list[str] = []


class ScrapeResult(Schema):
    company_id: str
    jobs_found: int
    scraped_at: datetime


class LoginIn(Schema):
    username: str
    password: str


class UserOut(Schema):
    username: str
