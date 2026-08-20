# Career Page Scraper — Project Overview

## Problem

Job seekers, recruiters, and researchers often want to track job postings across a specific set of companies' career pages over time. Career pages vary wildly in structure (custom HTML, Greenhouse, Lever, Workday, etc.), many render listings via JavaScript, and there's no easy way to get a normalized, structured view of what's currently posted without visiting each site manually.

## What this application does

- Lets a user maintain a list of tracked career pages (companies), each with its own scrape frequency, as structured records in Postgres.
- On demand (via a REST API), fetches the rendered page (headless browser, to handle JS-heavy sites).
- Uses an LLM to translate the scraped content into structured job listings (title, location, department, salary, etc.) — no per-company parser required.
- Saves each run's results as `JobPosting` rows in Postgres, so history accumulates as a series of scrapes per company.

## Goals (v1 / MVP)

- Structured storage: tracked companies and scraped job postings live in Postgres (via Django's ORM), queryable via a REST API (Django Ninja).
- Works on both static and JS-rendered career pages.
- LLM-based extraction that works across arbitrary company page layouts, via a provider-agnostic interface.
- Structured, validated job data on a consistent schema, saved per company per scrape run.

## Non-goals (v1)

- No diffing/change-detection between runs (snapshot only — see [roadmap.md](./docs/roadmap.md) for when this comes in).
- No scheduler yet — scrapes are triggered on demand via the API, not run automatically on each company's `frequency`.
- No web UI/dashboard — REST API only.
- No notifications (email/Slack) on new postings.

## Getting started

### Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- A local Postgres instance running
- An API key for whichever LLM provider `config/settings.yaml` points to (Gemini's free tier works fine for testing)

### 1. Install dependencies

```sh
uv sync
uv run playwright install chromium
```

### 2. Configure environment

```sh
cp .env.example .env
```

Fill in `.env`:
- `LLM_API_KEY` — key for the provider set in `config/settings.yaml`'s `settings.llm.provider`
- `DATABASE_URL` — connection string for your local Postgres instance

### 3. Set up the database

```sh
createdb career_scraper   # or whatever database name your DATABASE_URL points to
uv run python manage.py migrate
```

### 4. Start the server

```sh
uv run python manage.py runserver 8000
```

The API is now live at `http://127.0.0.1:8000/api/`. Django Ninja's interactive API console (Swagger UI) is at `http://127.0.0.1:8000/api/docs` — browse and try every endpoint from there without writing any `curl` commands.

### 5. Seed some companies

[`tests/test_seed_companies.py`](./tests/test_seed_companies.py) creates 3 real companies (Uplight, Voltus, Development Seed) by hitting `POST /api/companies` on the server you just started — a quick way to bootstrap data on a fresh database. It's safe to re-run (companies that already exist are skipped). In a second terminal:

```sh
uv run python tests/test_seed_companies.py
```

Companies are also manageable directly via SQL — see [config-schema.md](./docs/config-schema.md).

A few things to try once you have data:

```sh
curl http://127.0.0.1:8000/api/companies
curl -X POST http://127.0.0.1:8000/api/companies/voltus/scrape
curl http://127.0.0.1:8000/api/companies/voltus/jobs
```

## Docs in this folder

- [`architecture.md`](./docs/architecture.md) — system components, data flow, and repo structure.
- [`config-schema.md`](./docs/config-schema.md) — settings file format and the `Company` model.
- [`job-schema.md`](./docs/job-schema.md) — the `JobPosting` schema for an extracted job posting.
- [`roadmap.md`](./docs/roadmap.md) — phased build plan (V1/V2/V3) and open questions/risks.
