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
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "app",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "app.urls"
WSGI_APPLICATION = "app.wsgi.application"

# Django's admin site (used to create/manage user accounts) renders via the
# template engine, as does Django Ninja's interactive API docs (/api/docs).
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True

# Routes Django's logs through the stdlib `logging` module so the OpenTelemetry
# logging auto-instrumentation (enabled via OTEL_LOGS_EXPORTER=otlp) can capture them.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}


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
