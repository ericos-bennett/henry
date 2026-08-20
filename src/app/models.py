from __future__ import annotations

from django.db import models


class Company(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=200)
    url = models.URLField(max_length=500)
    frequency = models.CharField(max_length=100)
    enabled = models.BooleanField(default=True)
    wait_selector = models.CharField(max_length=300, null=True, blank=True)

    def __str__(self) -> str:
        return self.id


class JobPosting(models.Model):
    job_id = models.CharField(max_length=64)
    source_company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="job_postings"
    )
    source_url = models.URLField(max_length=500)
    scraped_at = models.DateTimeField()

    title = models.CharField(max_length=500)
    url = models.URLField(max_length=500, null=True, blank=True)
    location = models.CharField(max_length=300, null=True, blank=True)
    department = models.CharField(max_length=300, null=True, blank=True)
    employment_type = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    posted_date = models.CharField(max_length=100, null=True, blank=True)

    salary_min = models.FloatField(null=True, blank=True)
    salary_max = models.FloatField(null=True, blank=True)
    salary_currency = models.CharField(max_length=10, null=True, blank=True)
    salary_raw = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["job_id", "scraped_at"], name="unique_job_per_run"),
        ]
        indexes = [
            models.Index(fields=["source_company", "scraped_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.source_company_id})"
