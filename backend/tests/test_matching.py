"""Hermetic unit tests for is_recommended, no DB access needed."""

from __future__ import annotations

import unittest

from app.matching import is_recommended
from app.models import JobPosting, UserPreferences


def make_job(title: str, location: str | None = None, description: str | None = None) -> JobPosting:
    return JobPosting(title=title, location=location, description=description)


def make_prefs(locations: list[str] | None = None, keywords: list[str] | None = None) -> UserPreferences:
    return UserPreferences(locations=locations or [], keywords=keywords or [])


class IsRecommendedTest(unittest.TestCase):
    def test_no_preferences_means_nothing_is_recommended(self):
        job = make_job("Software Engineer", location="Remote")
        self.assertFalse(is_recommended(job, make_prefs()))

    def test_keyword_only_matches_title_case_insensitively(self):
        prefs = make_prefs(keywords=["engineer"])
        self.assertTrue(is_recommended(make_job("Software Engineer"), prefs))
        self.assertFalse(is_recommended(make_job("Product Designer"), prefs))

    def test_keyword_match_does_not_check_description(self):
        prefs = make_prefs(keywords=["kubernetes"])
        job = make_job("Software Engineer", description="You'll work with Kubernetes daily.")
        self.assertFalse(is_recommended(job, prefs))

    def test_location_only_matches_substring_case_insensitively(self):
        prefs = make_prefs(locations=["Tokyo"])
        self.assertTrue(is_recommended(make_job("Client Delivery Lead", location="Tokyo, Japan"), prefs))
        self.assertFalse(is_recommended(make_job("Client Delivery Lead", location="Melbourne, Australia"), prefs))

    def test_location_only_excludes_jobs_with_no_location(self):
        prefs = make_prefs(locations=["Tokyo"])
        self.assertFalse(is_recommended(make_job("Client Delivery Lead", location=None), prefs))

    def test_both_set_requires_both_to_match(self):
        prefs = make_prefs(locations=["Tokyo"], keywords=["engineer"])
        self.assertTrue(is_recommended(make_job("Software Engineer", location="Tokyo, Japan"), prefs))
        self.assertFalse(is_recommended(make_job("Software Engineer", location="Melbourne, Australia"), prefs))
        self.assertFalse(is_recommended(make_job("Client Delivery Lead", location="Tokyo, Japan"), prefs))
