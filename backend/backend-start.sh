#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

set -a
[ -f .env ] && source .env
set +a

uv sync
uv run opentelemetry-bootstrap -a install
uv run playwright install chromium
uv run python manage.py migrate
uv run opentelemetry-instrument python manage.py runserver
