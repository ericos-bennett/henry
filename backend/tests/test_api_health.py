"""Hermetic test for the unauthenticated GET /api/health liveness endpoint."""

from __future__ import annotations

from django.test import TestCase


class HealthTest(TestCase):
    def test_returns_ok_without_auth(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
