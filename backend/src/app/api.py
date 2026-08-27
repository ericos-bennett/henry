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
from app.matching import is_recommended
from app.models import Company, JobPosting, UserPreferences
from app.notifications import notify_all_recommended_jobs
from app.pipeline import run_scrape, run_scrapes_concurrently
from app.schemas import (
    CompanyIn,
    CompanyOut,
    CompanyPatch,
    JobPostingOut,
    LoginIn,
    PreferencesIn,
    PreferencesOut,
    ScrapeAllResult,
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


@api.post("/companies/scrape-all", response=ScrapeAllResult)
def scrape_all_companies(request):
    """Scrape every one of the user's companies and send a single combined digest
    of all currently recommended jobs, regardless of whether any are new —
    distinct from the per-company is_new-gated email each individual scrape sends.
    Registered before /companies/{company_id} so 'scrape-all' isn't swallowed by
    that parameterized route."""
    if not request.user.is_staff:
        raise HttpError(403, "Admin access required")

    logger.info("scrape-all requested by %s", request.user.username)
    companies = list(Company.objects.filter(owner=request.user, enabled=True))
    jobs_found = 0
    failed = 0
    for company, outcome in run_scrapes_concurrently(companies, notify=False):
        if isinstance(outcome, Exception):
            failed += 1
            logger.exception("scrape failed for %s during scrape-all", company.id, exc_info=outcome)
        else:
            jobs_found += outcome.jobs_found

    try:
        notify_all_recommended_jobs(request.user)
    except Exception:
        logger.exception("failed to send combined notification email for %s", request.user.username)

    return ScrapeAllResult(
        companies_scraped=len(companies) - failed, companies_failed=failed, jobs_found=jobs_found
    )


@api.get("/companies/{company_id}", response=CompanyOut)
def get_company(request, company_id: str):
    return get_object_or_404(Company, pk=company_id, owner=request.user)


@api.post("/companies", response={201: CompanyOut})
def create_company(request, payload: CompanyIn):
    company = Company.objects.create(id=slugify(payload.name), owner=request.user, **payload.dict())
    if company.enabled:
        try:
            run_scrape(company)
        except Exception:
            # The company is created either way — a failed first scrape can be retried
            # via the "Scrape" button, same as any other scrape failure.
            logger.exception("initial scrape failed for %s", company.id)
    return 201, company


@api.patch("/companies/{company_id}", response=CompanyOut)
def update_company(request, company_id: str, payload: CompanyPatch):
    company = get_object_or_404(Company, pk=company_id, owner=request.user)
    if payload.enabled is not None:
        company.enabled = payload.enabled
    if payload.frequency is not None:
        company.frequency = payload.frequency
    if payload.url is not None:
        company.url = payload.url
    company.save()
    return company


@api.delete("/companies/{company_id}")
def delete_company(request, company_id: str):
    company = get_object_or_404(Company, pk=company_id, owner=request.user)
    company.delete()
    return {"success": True}


def _annotate_recommended(request, jobs: list[JobPosting]) -> list[JobPosting]:
    prefs = UserPreferences.objects.filter(owner=request.user).first() or UserPreferences()
    for job in jobs:
        job._is_recommended = is_recommended(job, prefs)
    return jobs


@api.get("/companies/{company_id}/jobs", response=list[JobPostingOut])
def list_company_jobs(request, company_id: str, latest_only: bool = False):
    company = get_object_or_404(Company, pk=company_id, owner=request.user)
    qs = company.job_postings.all().order_by("-latest_scrape_timestamp")
    if latest_only:
        latest = qs.first()
        if latest is not None:
            qs = qs.filter(latest_scrape_timestamp=latest.latest_scrape_timestamp)
    return _annotate_recommended(request, list(qs))


@api.get("/jobs", response=list[JobPostingOut])
def list_jobs(
    request,
    company_id: str | None = None,
    location: str | None = None,
    salary_min: float | None = None,
):
    qs = JobPosting.objects.filter(source_company__owner=request.user).order_by("-latest_scrape_timestamp")
    if company_id:
        qs = qs.filter(source_company_id=company_id)
    if location:
        qs = qs.filter(location__icontains=location)
    if salary_min is not None:
        qs = qs.filter(salary_min__gte=salary_min)
    return _annotate_recommended(request, list(qs))


@api.get("/preferences", response=PreferencesOut)
def get_preferences(request):
    prefs, _ = UserPreferences.objects.get_or_create(owner=request.user)
    return prefs


@api.put("/preferences", response=PreferencesOut)
def update_preferences(request, payload: PreferencesIn):
    prefs, _ = UserPreferences.objects.update_or_create(owner=request.user, defaults=payload.dict())
    return prefs


@api.post("/companies/{company_id}/scrape", response=ScrapeResult)
def scrape_company(request, company_id: str):
    company = get_object_or_404(Company, pk=company_id, owner=request.user)
    if not company.enabled:
        raise HttpError(400, "Company is disabled")
    logger.info("scrape requested for %s by %s", company.id, request.user.username)
    return run_scrape(company)
