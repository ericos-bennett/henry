from __future__ import annotations

import os


def ensure_django_setup() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
    import django

    django.setup()
