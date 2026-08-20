#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

uv sync
uv run playwright install chromium
uv run python manage.py migrate
uv run python manage.py runserver 8000
