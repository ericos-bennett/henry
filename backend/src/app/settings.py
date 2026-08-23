from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-for-real-deployment")
DEBUG = True

# Empty by default, which makes Django fall back to ['localhost', '127.0.0.1', '[::1]']
# while DEBUG=True. Set DJANGO_ALLOWED_HOSTS in .env (comma-separated) to allow other hosts,
# e.g. for reaching a dev server over LAN.
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]

INSTALLED_APPS = [
    "app",
]

ROOT_URLCONF = "app.urls"
WSGI_APPLICATION = "app.wsgi.application"

# Django Ninja's interactive API docs (/api/docs) render via Django's template
# engine, which isn't otherwise needed by this API-only project.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [],
        },
    },
]

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
