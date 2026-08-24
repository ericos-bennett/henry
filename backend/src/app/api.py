from __future__ import annotations

import logging

from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from ninja import NinjaAPI
from ninja.errors import HttpError
from ninja.security import django_auth

from app.extractor import ExtractionError
from app.models import Company, JobPosting
from app.pipeline import run_scrape
from app.schemas import (
    CompanyIn,
    CompanyOut,
    CompanyPatch,
    JobPostingOut,
    LoginIn,
    ScrapeResult,
    UserOut,
)

logger = logging.getLogger(__name__)

api = NinjaAPI(auth=django_auth)


@api.exception_handler(ExtractionError)
def handle_extraction_error(request: HttpRequest, exc: ExtractionError):
    logger.exception("Extraction failed during request")
    return api.create_response(
        request,
        {"detail": "The job extraction service is temporarily unavailable. Please try again later."},
        status=502,
    )


@api.post("/login", response=UserOut, auth=None)
def login_view(request, payload: LoginIn):
    user = authenticate(request, username=payload.username, password=payload.password)
    if user is None:
        raise HttpError(401, "Invalid username or password")
    login(request, user)
    return user


@api.post("/logout", auth=None)
def logout_view(request):
    logout(request)
    return {"success": True}


@api.get("/me", response=UserOut)
def me(request):
    return request.user


@api.get("/companies", response=list[CompanyOut])
def list_companies(request):
    return Company.objects.filter(owner=request.user)


@api.get("/companies/{company_id}", response=CompanyOut)
def get_company(request, company_id: str):
    return get_object_or_404(Company, pk=company_id, owner=request.user)


@api.post("/companies", response={201: CompanyOut})
def create_company(request, payload: CompanyIn):
    company = Company.objects.create(id=slugify(payload.name), owner=request.user, **payload.dict())
    return 201, company


@api.patch("/companies/{company_id}", response=CompanyOut)
def update_company(request, company_id: str, payload: CompanyPatch):
    company = get_object_or_404(Company, pk=company_id, owner=request.user)
    company.enabled = payload.enabled
    company.save()
    return company


@api.delete("/companies/{company_id}")
def delete_company(request, company_id: str):
    company = get_object_or_404(Company, pk=company_id, owner=request.user)
    company.delete()
    return {"success": True}


@api.get("/companies/{company_id}/jobs", response=list[JobPostingOut])
def list_company_jobs(request, company_id: str, latest_only: bool = False):
    company = get_object_or_404(Company, pk=company_id, owner=request.user)
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
    qs = JobPosting.objects.filter(source_company__owner=request.user).order_by("-scraped_at")
    if company_id:
        qs = qs.filter(source_company_id=company_id)
    if location:
        qs = qs.filter(location__icontains=location)
    if salary_min is not None:
        qs = qs.filter(salary_min__gte=salary_min)
    return qs


@api.post("/companies/{company_id}/scrape", response=ScrapeResult)
def scrape_company(request, company_id: str):
    company = get_object_or_404(Company, pk=company_id, owner=request.user)
    return run_scrape(company)
