"""Hermetic tests for /api/companies endpoints, using Django's own test database."""

from __future__ import annotations

import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.models import Company


class UpdateCompanyTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice", password="password123")
        self.client.force_login(self.user)
        self.company = Company.objects.create(
            id="acme",
            name="Acme",
            url="https://acme.example/jobs",
            frequency="0 * * * *",
            enabled=True,
            owner=self.user,
        )

    def patch(self, body: dict):
        return self.client.patch(
            f"/api/companies/{self.company.id}", data=json.dumps(body), content_type="application/json"
        )

    def test_updates_frequency_only(self):
        response = self.patch({"frequency": "0 8 * * *"})
        self.assertEqual(response.status_code, 200)
        self.company.refresh_from_db()
        self.assertEqual(self.company.frequency, "0 8 * * *")
        self.assertTrue(self.company.enabled)

    def test_updates_enabled_only(self):
        response = self.patch({"enabled": False})
        self.assertEqual(response.status_code, 200)
        self.company.refresh_from_db()
        self.assertFalse(self.company.enabled)
        self.assertEqual(self.company.frequency, "0 * * * *")

    def test_updates_both_fields_together(self):
        response = self.patch({"enabled": False, "frequency": "0 8 * * 0"})
        self.assertEqual(response.status_code, 200)
        self.company.refresh_from_db()
        self.assertFalse(self.company.enabled)
        self.assertEqual(self.company.frequency, "0 8 * * 0")

    def test_rejects_invalid_frequency(self):
        response = self.patch({"frequency": "not-a-cron-expression"})
        self.assertEqual(response.status_code, 422)
        self.company.refresh_from_db()
        self.assertEqual(self.company.frequency, "0 * * * *")


class CreateCompanyTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice", password="password123")
        self.client.force_login(self.user)

    def create(self):
        body = {"name": "Acme", "url": "https://acme.example/jobs", "frequency": "0 * * * *"}
        return self.client.post("/api/companies", data=json.dumps(body), content_type="application/json")

    @mock.patch("app.api.run_scrape")
    def test_scrapes_immediately_after_creation(self, mock_run_scrape):
        response = self.create()

        self.assertEqual(response.status_code, 201)
        company = Company.objects.get(id="acme")
        mock_run_scrape.assert_called_once_with(company)

    @mock.patch("app.api.run_scrape", side_effect=RuntimeError("scrape failed"))
    def test_company_still_created_if_initial_scrape_fails(self, mock_run_scrape):
        response = self.create()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(Company.objects.filter(id="acme").exists())
