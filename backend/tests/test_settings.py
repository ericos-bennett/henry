"""Hermetic tests for the env-driven production-safety knobs in app.settings.

app.settings runs its DEBUG / SECRET_KEY / SSL logic once at import time, so each
case loads it in a fresh subprocess with a controlled environment. No database or
network is touched - the subprocess only imports the module and prints values.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

BACKEND_SRC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")

# A DATABASE_URL is required for import but never connected to here.
BASE_ENV = {
    "PATH": os.environ.get("PATH", ""),
    "DATABASE_URL": "postgresql://u@localhost:5432/x",
    "PYTHONPATH": BACKEND_SRC,
}

PROBE = (
    "import app.settings as s, json, sys; "
    "sys.stdout.write(json.dumps({"
    "'DEBUG': s.DEBUG, "
    "'SECRET_KEY': s.SECRET_KEY, "
    "'CONN_MAX_AGE': s.DATABASES['default'].get('CONN_MAX_AGE'), "
    "'SESSION_COOKIE_SECURE': getattr(s, 'SESSION_COOKIE_SECURE', None), "
    "'SECURE_HSTS_SECONDS': getattr(s, 'SECURE_HSTS_SECONDS', None), "
    "'has_whitenoise': 'whitenoise.middleware.WhiteNoiseMiddleware' in s.MIDDLEWARE, "
    "}))"
)


def load_settings(env: dict) -> dict | None:
    """Import app.settings in a subprocess with `env`; return the probed values,
    or None if import raised."""
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        env={**BASE_ENV, **env},
        # Run outside the repo so settings.py's load_dotenv() can't pick up the
        # developer's real backend/.env and override the test environment.
        cwd=tempfile.gettempdir(),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)


class SettingsTest(unittest.TestCase):
    def test_debug_defaults_off_and_requires_secret_key(self):
        self.assertIsNone(load_settings({}), "prod mode with no SECRET_KEY should fail to import")

    def test_prod_mode_with_secret_key(self):
        values = load_settings({"DJANGO_SECRET_KEY": "x" * 60})
        assert values is not None
        self.assertFalse(values["DEBUG"])
        self.assertEqual(values["SECRET_KEY"], "x" * 60)
        # SSL hardening stays off unless explicitly enabled.
        self.assertIsNone(values["SESSION_COOKIE_SECURE"])

    def test_debug_mode_allows_fallback_secret_key(self):
        values = load_settings({"DJANGO_DEBUG": "true"})
        assert values is not None
        self.assertTrue(values["DEBUG"])
        self.assertTrue(values["SECRET_KEY"])

    def test_conn_max_age_and_whitenoise_always_set(self):
        values = load_settings({"DJANGO_DEBUG": "true"})
        assert values is not None
        self.assertEqual(values["CONN_MAX_AGE"], 60)
        self.assertTrue(values["has_whitenoise"])

    def test_secure_ssl_flag_enables_hardening(self):
        values = load_settings({"DJANGO_SECRET_KEY": "x" * 60, "DJANGO_SECURE_SSL": "true"})
        assert values is not None
        self.assertTrue(values["SESSION_COOKIE_SECURE"])
        self.assertEqual(values["SECURE_HSTS_SECONDS"], 31536000)


if __name__ == "__main__":
    unittest.main()
