from __future__ import annotations

import hashlib
import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel

from app.config import LLMSettings
from app.models import Company, JobPosting
from app.schema import ExtractedJob

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = (
    "You are given the visible text of a company's career page. "
    "Extract every distinct job posting listed on the page. "
    "Links appear inline as their visible text followed by their absolute URL in "
    "parentheses, e.g. 'Senior Engineer (https://example.com/jobs/123)' — use the "
    "nearest such URL as a job's url field when one is present. "
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


def _normalize_job_url(url: str | None) -> str | None:
    """Some ATSes (e.g. Lever) link straight to a job's application form via a
    trailing '/apply' segment rather than its description page. Strip it so the
    saved url points at the description page instead, unless doing so would leave
    nothing but a bare domain (in which case the original url is kept as-is)."""
    if not url:
        return url
    stripped = re.sub(r"/apply/?$", "", url, flags=re.IGNORECASE)
    if stripped != url and urlparse(stripped).path not in ("", "/"):
        return stripped
    return url


def _make_job_key(company_id: str, extracted: ExtractedJob) -> str:
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
    seen_job_keys: set[str] = set()
    for job in extracted_jobs:
        job.url = _normalize_job_url(job.url)
        job_key = _make_job_key(company.id, job)
        if job_key in seen_job_keys:
            # Same company + url/title within one scrape (e.g. a job double-listed
            # under two categories on the page) would otherwise be treated as two
            # separate jobs sharing one job_key by save_job_postings().
            logger.warning(
                "skipping duplicate job_key %s in scrape of %s: %r", job_key, company.id, job.title
            )
            continue
        seen_job_keys.add(job_key)

        salary = job.salary_range
        postings.append(
            JobPosting(
                job_key=job_key,
                source_company=company,
                source_url=company.url,
                first_scrape_timestamp=scraped_at,
                latest_scrape_timestamp=scraped_at,
                title=job.title,
                url=job.url,
                location=job.location,
                department=job.department,
                employment_type=job.employment_type,
                posted_date=job.posted_date,
                salary_min=salary.min if salary else None,
                salary_max=salary.max if salary else None,
                salary_currency=salary.currency if salary else None,
            )
        )
    return postings
