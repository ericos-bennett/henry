"""Seeds 3 real companies by hitting the live API.

Not a hermetic unit test — it exercises a real running dev server and Postgres
database rather than an isolated test DB, on purpose: this doubles as a quick
way to bootstrap data right after `manage.py migrate`. Safe to re-run —
companies that already exist are skipped rather than erroring.

Requires the dev server to be running (see README):
    uv run python manage.py runserver 8000

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

TEST_COMPANIES = [
    {
        "id": "uplight",
        "name": "Uplight",
        "url": "https://jobs.jobvite.com/uplight/jobs",
        "frequency": "0 */6 * * *",
    },
    {
        "id": "voltus",
        "name": "Voltus",
        "url": "https://www.voltus.co/jobs",
        "frequency": "0 */6 * * *",
    },
    {
        "id": "developmentseed",
        "name": "Development Seed",
        "url": "https://developmentseed.org/careers/",
        "frequency": "0 0 * * *",
    },
]


class SeedCompaniesTest(unittest.TestCase):
    def test_create_companies(self):
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            for company in TEST_COMPANIES:
                existing = client.get(f"/api/companies/{company['id']}")
                if existing.status_code == 200:
                    print(f"skipped {company['id']} (already exists)")
                    continue

                response = client.post("/api/companies", json=company)
                self.assertEqual(
                    response.status_code,
                    201,
                    f"failed to create {company['id']}: {response.status_code} {response.text}",
                )
                print(f"created {company['id']}")


if __name__ == "__main__":
    unittest.main()
