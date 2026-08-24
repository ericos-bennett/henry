from __future__ import annotations

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
