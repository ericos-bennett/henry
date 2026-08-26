from __future__ import annotations

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models


class Company(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=200)
    url = models.URLField(max_length=500)
    frequency = models.CharField(max_length=100)
    enabled = models.BooleanField(default=True)
    # Nullable so existing rows aren't broken by this migration; assign an owner to
    # each pre-existing company via the admin panel after creating user accounts.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="companies", null=True, blank=True
    )
    # sha256 of the most recently fetched (post-trim) page text, used to skip
    # re-extraction when a scrape finds the page unchanged. Null until a
    # company's first successful scrape.
    last_content_hash = models.CharField(max_length=64, null=True, blank=True)

    def __str__(self) -> str:
        return self.id


class JobPosting(models.Model):
    # Stable content identity of the posting (company + url, or title+location
    # fallback) — unchanged across reappearances. Not unique: the same job_key
    # can have multiple historical rows, one per lifetime (a gap between two
    # rows means a reappearance, not a continuation — see save_job_postings()
    # in app/storage.py). Row identity itself is just the auto pk (`id`).
    job_key = models.CharField(max_length=64, db_index=True)
    source_company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="job_postings"
    )
    source_url = models.URLField(max_length=500)
    first_scrape_timestamp = models.DateTimeField()
    latest_scrape_timestamp = models.DateTimeField()

    title = models.CharField(max_length=500)
    url = models.URLField(max_length=500, null=True, blank=True)
    location = models.CharField(max_length=300, null=True, blank=True)
    department = models.CharField(max_length=300, null=True, blank=True)
    employment_type = models.CharField(max_length=100, null=True, blank=True)
    posted_date = models.CharField(max_length=100, null=True, blank=True)

    salary_min = models.FloatField(null=True, blank=True)
    salary_max = models.FloatField(null=True, blank=True)
    salary_currency = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["source_company", "latest_scrape_timestamp"],
                name="jp_company_latest_idx",
            ),
            models.Index(
                fields=["source_company", "job_key"],
                name="jp_company_jobkey_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.source_company_id})"

    @property
    def is_new(self) -> bool:
        return self.first_scrape_timestamp == self.latest_scrape_timestamp


class UserPreferences(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_preferences"
    )
    locations = ArrayField(models.CharField(max_length=200), default=list, blank=True)
    keywords = ArrayField(models.CharField(max_length=200), default=list, blank=True)

    def __str__(self) -> str:
        return f"preferences for {self.owner_id}"
