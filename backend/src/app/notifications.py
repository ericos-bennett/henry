from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.core.mail import send_mail

from app.matching import is_recommended
from app.models import Company, JobPosting, UserPreferences


def notify_new_recommended_jobs(company: Company, jobs: list[JobPosting]) -> None:
    if company.owner is None or not company.owner.email:
        return

    prefs = UserPreferences.objects.filter(owner=company.owner).first() or UserPreferences()
    matches = [job for job in jobs if job.is_new and is_recommended(job, prefs)]
    if not matches:
        return

    subject = f"{len(matches)} new recommended job{'s' if len(matches) != 1 else ''} at {company.name}"
    body = "\n\n".join(
        job.title + (f" — {job.location}" if job.location else "") + f"\n{job.url or company.url}"
        for job in matches
    )
    send_mail(subject, body, None, [company.owner.email])


def _latest_jobs(company: Company) -> list[JobPosting]:
    qs = company.job_postings.all().order_by("-scraped_at")
    latest = qs.first()
    if latest is None:
        return []
    return list(qs.filter(scraped_at=latest.scraped_at))


def notify_all_recommended_jobs(user: AbstractUser) -> None:
    """Email a single digest of every currently recommended job across all of the
    user's companies, regardless of whether it's new — used by the manual
    "scrape all" action rather than the per-scrape is_new-gated notifier above."""
    if not user.email:
        return

    prefs = UserPreferences.objects.filter(owner=user).first() or UserPreferences()
    sections: list[tuple[Company, list[JobPosting]]] = []
    for company in Company.objects.filter(owner=user):
        matches = [job for job in _latest_jobs(company) if is_recommended(job, prefs)]
        if matches:
            sections.append((company, matches))

    if not sections:
        return

    total = sum(len(matches) for _, matches in sections)
    subject = (
        f"{total} recommended job{'s' if total != 1 else ''} "
        f"across {len(sections)} compan{'y' if len(sections) == 1 else 'ies'}"
    )
    body = "\n\n\n".join(
        f"{company.name}\n" + "\n\n".join(
            job.title + (f" — {job.location}" if job.location else "") + f"\n{job.url or company.url}"
            for job in matches
        )
        for company, matches in sections
    )
    send_mail(subject, body, None, [user.email])
