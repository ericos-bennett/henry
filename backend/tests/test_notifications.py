"""Hermetic tests for notify_new_recommended_jobs, using Django's test mail outbox."""

from __future__ import annotations

from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase

from app.models import Company, JobPosting, UserPreferences
from app.notifications import notify_all_recommended_jobs, notify_new_recommended_jobs

SCRAPED_AT = datetime(2026, 8, 24, tzinfo=timezone.utc)


def make_job(company: Company, title: str, *, is_new: bool, location: str | None = None) -> JobPosting:
    return JobPosting(
        job_id=title, source_company=company, source_url=company.url, scraped_at=SCRAPED_AT,
        title=title, location=location, is_new=is_new,
    )


class NotifyNewRecommendedJobsTest(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="alice", password="password123", email="alice@example.com"
        )
        self.company = Company.objects.create(
            id="acme", name="Acme", url="https://acme.example/jobs", frequency="0 * * * *", owner=self.owner
        )
        UserPreferences.objects.create(owner=self.owner, keywords=["engineer"])

    def test_sends_email_for_a_new_recommended_job(self):
        jobs = [make_job(self.company, "Software Engineer", is_new=True)]

        notify_new_recommended_jobs(self.company, jobs)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ["alice@example.com"])
        self.assertIn("1 new recommended job", sent.subject)
        self.assertIn("Software Engineer", sent.body)

    def test_no_email_when_nothing_matches_preferences(self):
        jobs = [make_job(self.company, "Product Designer", is_new=True)]

        notify_new_recommended_jobs(self.company, jobs)

        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_for_a_recommended_job_that_isnt_new(self):
        jobs = [make_job(self.company, "Software Engineer", is_new=False)]

        notify_new_recommended_jobs(self.company, jobs)

        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_when_company_has_no_owner(self):
        self.company.owner = None
        self.company.save()
        jobs = [make_job(self.company, "Software Engineer", is_new=True)]

        notify_new_recommended_jobs(self.company, jobs)

        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_when_owner_has_no_email(self):
        self.owner.email = ""
        self.owner.save()
        jobs = [make_job(self.company, "Software Engineer", is_new=True)]

        notify_new_recommended_jobs(self.company, jobs)

        self.assertEqual(len(mail.outbox), 0)

    def test_batches_multiple_matches_into_one_email(self):
        jobs = [
            make_job(self.company, "Software Engineer", is_new=True, location="Tokyo"),
            make_job(self.company, "Senior Engineer", is_new=True, location="Remote"),
            make_job(self.company, "Product Designer", is_new=True),
        ]

        notify_new_recommended_jobs(self.company, jobs)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn("2 new recommended jobs", sent.subject)
        self.assertIn("Software Engineer", sent.body)
        self.assertIn("Senior Engineer", sent.body)
        self.assertNotIn("Product Designer", sent.body)


class NotifyAllRecommendedJobsTest(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="alice", password="password123", email="alice@example.com"
        )
        UserPreferences.objects.create(owner=self.owner, keywords=["engineer"])

    def create_job(self, company: Company, title: str, *, scraped_at: datetime, **kwargs):
        return JobPosting.objects.create(
            job_id=f"{company.id}:{title}:{scraped_at}", source_company=company, source_url=company.url,
            scraped_at=scraped_at, title=title, **kwargs,
        )

    def test_groups_matches_across_companies_into_one_email(self):
        acme = Company.objects.create(id="acme", name="Acme", url="https://acme.example/jobs", frequency="0 * * * *", owner=self.owner)
        globex = Company.objects.create(id="globex", name="Globex", url="https://globex.example/jobs", frequency="0 * * * *", owner=self.owner)
        self.create_job(acme, "Software Engineer", scraped_at=SCRAPED_AT)
        self.create_job(globex, "Senior Engineer", scraped_at=SCRAPED_AT)

        notify_all_recommended_jobs(self.owner)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ["alice@example.com"])
        self.assertIn("2 recommended jobs across 2 companies", sent.subject)
        self.assertIn("Acme", sent.body)
        self.assertIn("Software Engineer", sent.body)
        self.assertIn("Globex", sent.body)
        self.assertIn("Senior Engineer", sent.body)

    def test_includes_matches_regardless_of_is_new(self):
        acme = Company.objects.create(id="acme", name="Acme", url="https://acme.example/jobs", frequency="0 * * * *", owner=self.owner)
        self.create_job(acme, "Software Engineer", scraped_at=SCRAPED_AT, is_new=False)

        notify_all_recommended_jobs(self.owner)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Software Engineer", mail.outbox[0].body)

    def test_only_considers_each_companys_latest_scraped_batch(self):
        acme = Company.objects.create(id="acme", name="Acme", url="https://acme.example/jobs", frequency="0 * * * *", owner=self.owner)
        earlier = datetime(2026, 8, 1, tzinfo=timezone.utc)
        self.create_job(acme, "Software Engineer", scraped_at=earlier)
        # Latest batch replaces it with a non-matching posting.
        self.create_job(acme, "Product Designer", scraped_at=SCRAPED_AT)

        notify_all_recommended_jobs(self.owner)

        self.assertEqual(len(mail.outbox), 0)

    def test_ignores_other_users_companies(self):
        other = get_user_model().objects.create_user(username="bob", password="password123", email="bob@example.com")
        other_company = Company.objects.create(id="other", name="Other", url="https://other.example/jobs", frequency="0 * * * *", owner=other)
        self.create_job(other_company, "Software Engineer", scraped_at=SCRAPED_AT)

        notify_all_recommended_jobs(self.owner)

        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_when_nothing_matches(self):
        acme = Company.objects.create(id="acme", name="Acme", url="https://acme.example/jobs", frequency="0 * * * *", owner=self.owner)
        self.create_job(acme, "Product Designer", scraped_at=SCRAPED_AT)

        notify_all_recommended_jobs(self.owner)

        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_when_user_has_no_email(self):
        self.owner.email = ""
        self.owner.save()
        acme = Company.objects.create(id="acme", name="Acme", url="https://acme.example/jobs", frequency="0 * * * *", owner=self.owner)
        self.create_job(acme, "Software Engineer", scraped_at=SCRAPED_AT)

        notify_all_recommended_jobs(self.owner)

        self.assertEqual(len(mail.outbox), 0)
