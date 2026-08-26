"""Hermetic unit tests for is_recommended, no DB access needed."""

from __future__ import annotations

import unittest

from app.matching import is_recommended
from app.models import JobPosting, UserPreferences


def make_job(title: str, location: str | None = None) -> JobPosting:
    return JobPosting(title=title, location=location)


def make_prefs(locations: list[str] | None = None, keywords: list[str] | None = None) -> UserPreferences:
    return UserPreferences(locations=locations or [], keywords=keywords or [])


class IsRecommendedTest(unittest.TestCase):
    def test_no_preferences_means_nothing_is_recommended(self):
        job = make_job("Software Engineer", location="Remote")
        self.assertFalse(is_recommended(job, make_prefs()))

    def test_keywords_only_means_nothing_is_recommended(self):
        # Both locations and keywords must be set for anything to match — a
        # preference dimension the user hasn't configured isn't "no opinion".
        prefs = make_prefs(keywords=["engineer"])
        self.assertFalse(is_recommended(make_job("Software Engineer"), prefs))

    def test_locations_only_means_nothing_is_recommended(self):
        prefs = make_prefs(locations=["Tokyo"])
        self.assertFalse(is_recommended(make_job("Client Delivery Lead", location="Tokyo, Japan"), prefs))

    def test_both_set_requires_both_to_match(self):
        prefs = make_prefs(locations=["Tokyo"], keywords=["engineer"])
        self.assertTrue(is_recommended(make_job("Software Engineer", location="Tokyo, Japan"), prefs))
        self.assertFalse(is_recommended(make_job("Software Engineer", location="Melbourne, Australia"), prefs))
        self.assertFalse(is_recommended(make_job("Client Delivery Lead", location="Tokyo, Japan"), prefs))

    def test_both_set_matches_case_insensitively(self):
        prefs = make_prefs(locations=["tokyo"], keywords=["ENGINEER"])
        self.assertTrue(is_recommended(make_job("Software Engineer", location="Tokyo, Japan"), prefs))

    def test_both_set_but_missing_location_falls_back_to_keyword_only(self):
        # Career pages that don't expose location as a distinct field (e.g. Voltus)
        # shouldn't have every posting permanently excluded once a location
        # preference is set — falls back to keyword-only matching instead.
        prefs = make_prefs(locations=["Tokyo"], keywords=["engineer"])
        self.assertTrue(is_recommended(make_job("Software Engineer", location=None), prefs))
        self.assertFalse(is_recommended(make_job("Client Delivery Lead", location=None), prefs))
