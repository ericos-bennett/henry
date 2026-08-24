"""Hermetic tests for GET/PUT /api/preferences, using Django's own test database."""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.models import UserPreferences


class PreferencesTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice", password="password123")
        self.client.force_login(self.user)

    def test_get_defaults_to_empty_lists(self):
        response = self.client.get("/api/preferences")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"locations": [], "keywords": []})

    def test_put_round_trips_saved_values(self):
        body = {"locations": ["Tokyo", "Melbourne"], "keywords": ["engineer"]}
        response = self.client.put("/api/preferences", data=json.dumps(body), content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), body)

        get_response = self.client.get("/api/preferences")
        self.assertEqual(get_response.json(), body)

    def test_put_overwrites_previous_values(self):
        self.client.put(
            "/api/preferences",
            data=json.dumps({"locations": ["Tokyo"], "keywords": ["engineer"]}),
            content_type="application/json",
        )
        response = self.client.put(
            "/api/preferences", data=json.dumps({"locations": [], "keywords": ["designer"]}), content_type="application/json"
        )

        self.assertEqual(response.json(), {"locations": [], "keywords": ["designer"]})

    def test_preferences_are_isolated_per_user(self):
        self.client.put(
            "/api/preferences",
            data=json.dumps({"locations": ["Tokyo"], "keywords": []}),
            content_type="application/json",
        )

        other_user = get_user_model().objects.create_user(username="bob", password="password123")
        self.client.force_login(other_user)

        response = self.client.get("/api/preferences")
        self.assertEqual(response.json(), {"locations": [], "keywords": []})
        self.assertEqual(UserPreferences.objects.get(owner=self.user).locations, ["Tokyo"])
