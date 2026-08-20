from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-for-real-deployment")
DEBUG = True

INSTALLED_APPS = [
    "app",
]

ROOT_URLCONF = "app.urls"
WSGI_APPLICATION = "app.wsgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True


def _database_from_url(url: str) -> dict:
    parsed = urlsplit(url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username,
        "PASSWORD": parsed.password,
        "HOST": parsed.hostname,
        "PORT": parsed.port or 5432,
    }


DATABASES = {"default": _database_from_url(os.environ["DATABASE_URL"])}
