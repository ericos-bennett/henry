from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Production-safe by default: DEBUG stays off unless DJANGO_DEBUG=true, and in that
# (dev) mode a throwaway SECRET_KEY fallback is fine. With DEBUG off, DJANGO_SECRET_KEY
# is required - fail loudly at startup rather than run with a known key.
# Generate one: python -c "import secrets; print(secrets.token_urlsafe(50))"
DEBUG = os.environ.get("DJANGO_DEBUG", "").lower() == "true"
if DEBUG:
    SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-for-real-deployment")
elif os.environ.get("DJANGO_SECRET_KEY"):
    SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
else:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is not 'true'. "
        'Generate one: python -c "import secrets; print(secrets.token_urlsafe(50))"'
    )

# Always includes localhost. Set DJANGO_ALLOWED_HOSTS in .env (comma-separated) to
# additionally allow other hosts, e.g. a LAN IP for reaching a dev server over LAN.
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"] + [
    h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()
]

# Extra origins (full scheme://host:port) allowed to make unsafe (POST/PATCH/DELETE)
# requests, beyond what Django's default same-origin check already allows. Not needed
# for the normal LAN setup (the Vite proxy preserves the original Host header, so it
# already matches the browser's Origin) - this is an escape hatch for other cases, e.g.
# hitting the backend directly on its own port. Set DJANGO_CSRF_TRUSTED_ORIGINS
# (comma-separated) in .env if needed.
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serves collected static files (Django admin, Ninja /api/docs) directly from
    # Gunicorn in production, so no separate static file server is needed. No-op
    # under runserver, which serves static files itself.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True

# TLS-behind-proxy hardening. Off by default so a bare HTTP deployment still works;
# set DJANGO_SECURE_SSL=true once Caddy (or another proxy) terminates HTTPS in front
# of Gunicorn - otherwise the secure-cookie flags make sessions/CSRF unusable.
if os.environ.get("DJANGO_SECURE_SSL", "").lower() == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = True

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
        # Reuse connections for 60s instead of opening one per request. Safe with
        # the scheduler thread too: it calls close_old_connections() each tick.
        "CONN_MAX_AGE": 60,
    }


DATABASES = {"default": _database_from_url(os.environ["DATABASE_URL"])}

# Provider-agnostic SMTP config for job-notification emails — works with any SMTP
# relay (a dedicated Gmail account + app password, AWS SES SMTP, Mailgun, Postmark,
# etc.) via env vars, same pattern as LLM_PROVIDER/LLM_MODEL/LLM_API_KEY in
# app.config. Left blank, sending simply fails (caught and logged, doesn't break
# a scrape) rather than requiring SMTP setup to run the app at all.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
