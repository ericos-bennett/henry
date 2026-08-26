"""Seeds 3 real companies, owned by one user, by hitting the live API.

Not a hermetic unit test — it exercises a real running dev server and Postgres
database rather than an isolated test DB, on purpose: this doubles as a quick
way to bootstrap data right after `manage.py migrate`. Safe to re-run —
companies that already exist are skipped rather than erroring.

Requires the dev server to be running (see README):
    uv run python manage.py runserver 8000

And a user account to own the seeded companies (see README for creating one via
`manage.py createsuperuser` or the /controls/ admin panel):
    export CAREER_SCRAPER_SEED_USERNAME=<username>
    export CAREER_SCRAPER_SEED_PASSWORD=<password>

Run directly to seed data:
    uv run python tests/test_seed_companies.py

Or via unittest:
    uv run python -m unittest tests.test_seed_companies
"""

from __future__ import annotations

import os
import unittest

import httpx

BASE_URL = os.environ.get("CAREER_SCRAPER_BASE_URL", "http://127.0.0.1:8000")
SEED_USERNAME = os.environ.get("CAREER_SCRAPER_SEED_USERNAME")
SEED_PASSWORD = os.environ.get("CAREER_SCRAPER_SEED_PASSWORD")

TEST_COMPANIES = [
    {
        "name": "Uplight",
        "url": "https://jobs.jobvite.com/uplight/jobs",
        "frequency": "0 */8 * * *",
    },
    {
        "name": "Voltus",
        "url": "https://www.voltus.co/jobs",
        "frequency": "0 8 * * *",
    },
    {
        "name": "Development Seed",
        "url": "https://developmentseed.org/careers/",
        "frequency": "0 8 * * 0",
    },
]


class SeedCompaniesTest(unittest.TestCase):
    def test_create_companies(self):
        self.assertIsNotNone(SEED_USERNAME, "Set CAREER_SCRAPER_SEED_USERNAME to a user's username")
        self.assertIsNotNone(
            SEED_PASSWORD, "Set CAREER_SCRAPER_SEED_PASSWORD to that user's password"
        )
        # POST /api/companies runs a synchronous first scrape (Playwright fetch +
        # LLM extraction) before responding, which routinely exceeds a short timeout.
        with httpx.Client(base_url=BASE_URL, timeout=120) as client:
            login = client.post(
                "/api/login", json={"username": SEED_USERNAME, "password": SEED_PASSWORD}
            )
            self.assertEqual(
                login.status_code, 200, f"login failed for {SEED_USERNAME}: {login.text}"
            )
            csrf_token = client.cookies.get("csrftoken")

            existing_response = client.get("/api/companies")
            existing_response.raise_for_status()
            # Check by name, not a guessed id/slug: existing rows may predate the
            # server's current slugify-from-name scheme, so an id guess can miss.
            existing_names = {c["name"] for c in existing_response.json()}

            for company in TEST_COMPANIES:
                if company["name"] in existing_names:
                    print(f"skipped {company['name']} (already exists)")
                    continue

                response = client.post(
                    "/api/companies", json=company, headers={"X-CSRFToken": csrf_token}
                )
                self.assertEqual(
                    response.status_code,
                    201,
                    f"failed to create {company['name']}: {response.status_code} {response.text}",
                )
                print(f"created {company['name']}")


if __name__ == "__main__":
    unittest.main()
