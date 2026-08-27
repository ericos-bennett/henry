"""Hermetic tests for /api/companies endpoints, using Django's own test database."""

from __future__ import annotations

import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from app.models import Company
from app.schemas import ScrapeResult


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

    def test_updates_url_only(self):
        response = self.patch({"url": "https://acme.example/careers"})
        self.assertEqual(response.status_code, 200)
        self.company.refresh_from_db()
        self.assertEqual(self.company.url, "https://acme.example/careers")
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

    @mock.patch("app.api.run_scrape")
    def test_does_not_scrape_immediately_if_created_disabled(self, mock_run_scrape):
        body = {
            "name": "Acme",
            "url": "https://acme.example/jobs",
            "frequency": "0 * * * *",
            "enabled": False,
        }
        response = self.client.post("/api/companies", data=json.dumps(body), content_type="application/json")

        self.assertEqual(response.status_code, 201)
        mock_run_scrape.assert_not_called()


class ScrapeCompanyTest(TestCase):
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

    @mock.patch("app.api.run_scrape")
    def test_scrapes_enabled_company(self, mock_run_scrape):
        mock_run_scrape.return_value = ScrapeResult(
            company_id="acme", jobs_found=1, scraped_at=timezone.now()
        )

        response = self.client.post(f"/api/companies/{self.company.id}/scrape")

        self.assertEqual(response.status_code, 200)
        mock_run_scrape.assert_called_once_with(self.company)

    @mock.patch("app.api.run_scrape")
    def test_rejects_scraping_a_disabled_company(self, mock_run_scrape):
        self.company.enabled = False
        self.company.save()

        response = self.client.post(f"/api/companies/{self.company.id}/scrape")

        self.assertEqual(response.status_code, 400)
        mock_run_scrape.assert_not_called()


def _fake_scrape_result(counts: dict[str, int]):
    def fake(company, **kwargs):
        return ScrapeResult(company_id=company.id, jobs_found=counts[company.id], scraped_at=timezone.now())

    return fake


class ScrapeAllCompaniesTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="alice", password="password123", is_staff=True
        )
        self.client.force_login(self.user)
        Company.objects.create(id="acme", name="Acme", url="https://acme.example/jobs", frequency="0 * * * *", owner=self.user)
        Company.objects.create(id="globex", name="Globex", url="https://globex.example/jobs", frequency="0 * * * *", owner=self.user)

    def test_rejects_non_staff_users(self):
        non_staff = get_user_model().objects.create_user(username="bob", password="password123", is_staff=False)
        self.client.force_login(non_staff)

        response = self.client.post("/api/companies/scrape-all")

        self.assertEqual(response.status_code, 403)

    @mock.patch("app.api.notify_all_recommended_jobs")
    @mock.patch("app.api.run_scrapes_concurrently")
    def test_scrapes_every_owned_company_and_sends_one_digest(self, mock_run_scrapes, mock_notify):
        results = _fake_scrape_result({"acme": 3, "globex": 5})
        mock_run_scrapes.side_effect = lambda companies, **kwargs: [
            (company, results(company)) for company in companies
        ]

        response = self.client.post("/api/companies/scrape-all")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"companies_scraped": 2, "companies_failed": 0, "jobs_found": 8})
        mock_run_scrapes.assert_called_once()
        called_companies, called_kwargs = mock_run_scrapes.call_args.args[0], mock_run_scrapes.call_args.kwargs
        self.assertEqual({c.id for c in called_companies}, {"acme", "globex"})
        self.assertEqual(called_kwargs, {"notify": False})
        mock_notify.assert_called_once_with(self.user)

    @mock.patch("app.api.notify_all_recommended_jobs")
    @mock.patch("app.api.run_scrapes_concurrently")
    def test_continues_past_individual_scrape_failures(self, mock_run_scrapes, mock_notify):
        def fake(companies, **kwargs):
            outcomes = []
            for company in companies:
                if company.id == "acme":
                    outcomes.append((company, RuntimeError("boom")))
                else:
                    outcomes.append((company, ScrapeResult(company_id=company.id, jobs_found=5, scraped_at=timezone.now())))
            return outcomes

        mock_run_scrapes.side_effect = fake

        response = self.client.post("/api/companies/scrape-all")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"companies_scraped": 1, "companies_failed": 1, "jobs_found": 5})
        mock_notify.assert_called_once_with(self.user)

    @mock.patch("app.api.notify_all_recommended_jobs")
    @mock.patch("app.api.run_scrapes_concurrently")
    def test_only_scrapes_own_companies(self, mock_run_scrapes, mock_notify):
        other = get_user_model().objects.create_user(username="bob", password="password123")
        Company.objects.create(id="other", name="Other", url="https://other.example/jobs", frequency="0 * * * *", owner=other)
        results = _fake_scrape_result({"acme": 1, "globex": 1})
        mock_run_scrapes.side_effect = lambda companies, **kwargs: [
            (company, results(company)) for company in companies
        ]

        response = self.client.post("/api/companies/scrape-all")

        self.assertEqual(response.json()["companies_scraped"], 2)
        scraped_ids = {c.id for c in mock_run_scrapes.call_args.args[0]}
        self.assertEqual(scraped_ids, {"acme", "globex"})

    @mock.patch("app.api.notify_all_recommended_jobs")
    @mock.patch("app.api.run_scrapes_concurrently")
    def test_excludes_disabled_companies(self, mock_run_scrapes, mock_notify):
        Company.objects.filter(id="globex").update(enabled=False)
        mock_run_scrapes.return_value = [
            (Company.objects.get(id="acme"), ScrapeResult(company_id="acme", jobs_found=1, scraped_at=timezone.now()))
        ]

        response = self.client.post("/api/companies/scrape-all")

        self.assertEqual(response.status_code, 200)
        scraped_ids = {c.id for c in mock_run_scrapes.call_args.args[0]}
        self.assertEqual(scraped_ids, {"acme"})
