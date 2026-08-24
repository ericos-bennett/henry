"""Hermetic tests for is_recommended annotation on job-listing endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.models import Company, JobPosting


class JobRecommendationTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice", password="password123")
        self.client.force_login(self.user)
        self.company = Company.objects.create(
            id="acme", name="Acme", url="https://acme.example/jobs", frequency="0 * * * *", owner=self.user
        )
        scraped_at = datetime(2026, 8, 24, tzinfo=timezone.utc)
        JobPosting.objects.create(
            job_id="a", source_company=self.company, source_url=self.company.url, scraped_at=scraped_at,
            title="Software Engineer", location="Tokyo, Japan",
        )
        JobPosting.objects.create(
            job_id="b", source_company=self.company, source_url=self.company.url, scraped_at=scraped_at,
            title="Product Designer", location="Tokyo, Japan",
        )

    def set_preferences(self, locations=None, keywords=None):
        self.client.put(
            "/api/preferences",
            data=json.dumps({"locations": locations or [], "keywords": keywords or []}),
            content_type="application/json",
        )

    def test_no_preferences_means_nothing_recommended(self):
        response = self.client.get(f"/api/companies/{self.company.id}/jobs")
        self.assertTrue(all(job["is_recommended"] is False for job in response.json()))

    def test_marks_matching_jobs_recommended(self):
        self.set_preferences(locations=["Tokyo"], keywords=["engineer"])

        response = self.client.get(f"/api/companies/{self.company.id}/jobs")
        by_title = {job["title"]: job["is_recommended"] for job in response.json()}

        self.assertTrue(by_title["Software Engineer"])
        self.assertFalse(by_title["Product Designer"])

    def test_cross_company_jobs_endpoint_also_annotates(self):
        self.set_preferences(keywords=["engineer"])

        response = self.client.get("/api/jobs")
        by_title = {job["title"]: job["is_recommended"] for job in response.json()}

        self.assertTrue(by_title["Software Engineer"])
        self.assertFalse(by_title["Product Designer"])
