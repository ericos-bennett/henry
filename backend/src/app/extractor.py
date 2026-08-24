from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel

from app.config import LLMSettings
from app.models import Company, JobPosting
from app.schema import ExtractedJob

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = (
    "You are given the visible text of a company's career page. "
    "Extract every distinct job posting listed on the page. "
    "If a field isn't present for a job, omit it or leave it null rather than guessing. "
    "Do not invent jobs that aren't actually listed. "
    "If no jobs are listed, return an empty list."
)


class ExtractionError(Exception):
    """Raised when an LLMExtractor fails to extract job postings, for any reason
    (upstream API failure, malformed response, etc.)."""


class LLMExtractor(ABC):
    @abstractmethod
    def extract(self, content: str) -> list[ExtractedJob]:
        """Extract job postings from a career page's text content."""


class GeminiExtractor(LLMExtractor):
    def __init__(self, api_key: str, model: str):
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model

    def extract(self, content: str) -> list[ExtractedJob]:
        response = self._client.models.generate_content(
            model=self._model,
            contents=f"{EXTRACTION_PROMPT}\n\n---\n\n{content}",
            config={
                "response_mime_type": "application/json",
                "response_schema": list[ExtractedJob],
                # We only use response_schema for structured output, not tool calls,
                # so automatic function calling doesn't apply here.
                "automatic_function_calling": {"disable": True},
            },
        )
        return [ExtractedJob.model_validate(item) for item in json.loads(response.text)]


class _ExtractedJobList(BaseModel):
    jobs: list[ExtractedJob]


class AnthropicExtractor(LLMExtractor):
    def __init__(self, api_key: str, model: str):
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def extract(self, content: str) -> list[ExtractedJob]:
        response = self._client.messages.parse(
            model=self._model,
            max_tokens=16000,
            messages=[{"role": "user", "content": f"{EXTRACTION_PROMPT}\n\n---\n\n{content}"}],
            output_format=_ExtractedJobList,
        )
        return response.parsed_output.jobs


def get_extractor(settings: LLMSettings) -> LLMExtractor:
    api_key = settings.api_key
    if not api_key:
        raise RuntimeError(
            f"No API key found in env var '{settings.api_key_env}'. "
            "Set it in your .env file."
        )

    if settings.provider == "gemini":
        return GeminiExtractor(api_key=api_key, model=settings.model)
    if settings.provider == "claude":
        return AnthropicExtractor(api_key=api_key, model=settings.model)

    raise NotImplementedError(f"No extractor implemented for provider '{settings.provider}'")


def _make_job_id(company_id: str, extracted: ExtractedJob) -> str:
    # Without a url, fall back to title + location rather than title alone — the
    # same role posted in multiple locations (e.g. "Client Delivery Lead" in both
    # Tokyo and Melbourne) is two distinct postings, not one.
    fallback = f"{extracted.title}:{extracted.location or ''}"
    basis = f"{company_id}:{extracted.url or fallback}"
    return hashlib.sha1(basis.encode()).hexdigest()[:12]


def to_job_postings(
    extracted_jobs: list[ExtractedJob],
    *,
    company: Company,
    scraped_at: datetime,
) -> list[JobPosting]:
    postings = []
    seen_job_ids: set[str] = set()
    for job in extracted_jobs:
        job_id = _make_job_id(company.id, job)
        if job_id in seen_job_ids:
            # Same company + url/title within one scrape (e.g. a job double-listed
            # under two categories on the page) would otherwise collide on the
            # (job_id, scraped_at) unique constraint and crash the whole batch.
            logger.warning(
                "skipping duplicate job_id %s in scrape of %s: %r", job_id, company.id, job.title
            )
            continue
        seen_job_ids.add(job_id)

        salary = job.salary_range
        postings.append(
            JobPosting(
                job_id=job_id,
                source_company=company,
                source_url=company.url,
                scraped_at=scraped_at,
                title=job.title,
                url=job.url,
                location=job.location,
                department=job.department,
                employment_type=job.employment_type,
                description=job.description,
                posted_date=job.posted_date,
                salary_min=salary.min if salary else None,
                salary_max=salary.max if salary else None,
                salary_currency=salary.currency if salary else None,
                salary_raw=salary.raw if salary else None,
            )
        )
    return postings
