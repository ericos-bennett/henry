from __future__ import annotations

import logging

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import NinjaAPI

from app.extractor import ExtractionError
from app.models import Company, JobPosting
from app.pipeline import run_scrape
from app.schemas import CompanyIn, CompanyOut, JobPostingOut, ScrapeResult

logger = logging.getLogger(__name__)

api = NinjaAPI()


@api.exception_handler(ExtractionError)
def handle_extraction_error(request: HttpRequest, exc: ExtractionError):
    logger.exception("Extraction failed during request")
    return api.create_response(
        request,
        {"detail": "The job extraction service is temporarily unavailable. Please try again later."},
        status=502,
    )


@api.get("/companies", response=list[CompanyOut])
def list_companies(request):
    return Company.objects.all()


@api.get("/companies/{company_id}", response=CompanyOut)
def get_company(request, company_id: str):
    return get_object_or_404(Company, pk=company_id)


@api.post("/companies", response={201: CompanyOut})
def create_company(request, payload: CompanyIn):
    company = Company.objects.create(**payload.dict())
    return 201, company


@api.delete("/companies/{company_id}")
def delete_company(request, company_id: str):
    company = get_object_or_404(Company, pk=company_id)
    company.delete()
    return {"success": True}


@api.get("/companies/{company_id}/jobs", response=list[JobPostingOut])
def list_company_jobs(request, company_id: str, latest_only: bool = False):
    company = get_object_or_404(Company, pk=company_id)
    qs = company.job_postings.all().order_by("-scraped_at")
    if latest_only:
        latest = qs.first()
        if latest is not None:
            qs = qs.filter(scraped_at=latest.scraped_at)
    return qs


@api.get("/jobs", response=list[JobPostingOut])
def list_jobs(
    request,
    company_id: str | None = None,
    location: str | None = None,
    salary_min: float | None = None,
):
    qs = JobPosting.objects.all().order_by("-scraped_at")
    if company_id:
        qs = qs.filter(source_company_id=company_id)
    if location:
        qs = qs.filter(location__icontains=location)
    if salary_min is not None:
        qs = qs.filter(salary_min__gte=salary_min)
    return qs


@api.post("/companies/{company_id}/scrape", response=ScrapeResult)
def scrape_company(request, company_id: str):
    company = get_object_or_404(Company, pk=company_id)
    return run_scrape(company)
