from __future__ import annotations

from django.shortcuts import get_object_or_404
from ninja import NinjaAPI

from app.config import load_config
from app.extractor import get_extractor, to_job_postings
from app.fetcher import fetch_company
from app.models import Company, JobPosting
from app.schemas import CompanyIn, CompanyOut, JobPostingOut, ScrapeResult
from app.storage import save_job_postings, write_raw_html

api = NinjaAPI()

_config = load_config()
_extractor = get_extractor(_config.settings.llm)


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

    result = fetch_company(company, _config.settings.playwright)
    write_raw_html(_config.settings.storage.root, company.id, result.fetched_at, result.html)

    extracted = _extractor.extract(result.text)
    jobs = to_job_postings(extracted, company=company, scraped_at=result.fetched_at)
    saved = save_job_postings(jobs)

    return ScrapeResult(
        company_id=company.id, jobs_found=len(saved), scraped_at=result.fetched_at
    )
