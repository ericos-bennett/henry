# Career Page Scraper — Project Overview

## Problem

Job seekers, recruiters, and researchers often want to track job postings across a specific set of companies' career pages over time. Career pages vary wildly in structure (custom HTML, Greenhouse, Lever, Workday, etc.), many render listings via JavaScript, and there's no easy way to get a normalized, structured view of what's currently posted without visiting each site manually.

## What this application does

- Lets a user maintain a list of tracked career pages (companies), each with its own scrape frequency, as structured records in Postgres.
- On demand (via a REST API), fetches the rendered page (headless browser, to handle JS-heavy sites).
- Uses an LLM to translate the scraped content into structured job listings (title, location, department, salary, etc.) — no per-company parser required.
- Saves each run's results as `JobPosting` rows in Postgres, so history accumulates as a series of scrapes per company.
- A small React frontend lists companies, triggers scrapes, and browses job results, on top of the same REST API.

## Goals (v1 / MVP)

- Structured storage: tracked companies and scraped job postings live in Postgres (via Django's ORM), queryable via a REST API (Django Ninja).
- Works on both static and JS-rendered career pages.
- LLM-based extraction that works across arbitrary company page layouts, via a provider-agnostic interface.
- Structured, validated job data on a consistent schema, saved per company per scrape run.

## Non-goals (v1)

- No diffing/change-detection between runs (snapshot only — see [roadmap.md](./docs/roadmap.md) for when this comes in).
- No scheduler yet — scrapes are triggered on demand via the API, not run automatically on each company's `frequency`.
- No notifications (email/Slack) on new postings.

## Repo layout

- **`backend/`** — Django + Django Ninja REST API, Postgres via Django's ORM, the Playwright fetcher, and the LLM extractor.
- **`frontend/`** — React + TypeScript (Vite) single-page app that talks to the backend API.
- **`docs/`** — architecture, schema, and roadmap docs (see links at the bottom of this file).

## Getting started

### Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Node.js and npm
- A local Postgres instance running
- An API key for whichever LLM provider `backend/config/settings.yaml` points to (Gemini's free tier works fine for testing)

### Backend

All commands below are run from `backend/`.

#### 1. Configure environment

```sh
cd backend
cp .env.example .env
```

Fill in `.env`:
- `LLM_API_KEY` — key for the provider set in `config/settings.yaml`'s `settings.llm.provider`
- `DATABASE_URL` — connection string for your local Postgres instance

#### 2. Create the database

```sh
createdb career_scraper   # or whatever database name your DATABASE_URL points to
```

#### 3. Start the server

```sh
cd backend
./backend-start.sh
```

This installs Python dependencies (`uv sync`), installs the Playwright browser, runs database migrations, then starts the dev server — safe to re-run any time (each step is a no-op if already up to date). The API is now live at `http://127.0.0.1:8000/api/`. Django Ninja's interactive API console (Swagger UI) is at `http://127.0.0.1:8000/api/docs` — browse and try every endpoint from there without writing any `curl` commands.

#### 4. Seed some companies

[`tests/test_seed_companies.py`](./backend/tests/test_seed_companies.py) creates 3 real companies (Uplight, Voltus, Development Seed), owned by a user account, by logging in and then hitting `POST /api/companies` on the server you just started — a quick way to bootstrap data on a fresh database. It's safe to re-run (companies that already exist, for that user, are skipped).

It needs a user account to log in as — create one with `uv run python manage.py createsuperuser` or via the admin panel at `/controls/` — passed as `CAREER_SCRAPER_SEED_USERNAME`/`CAREER_SCRAPER_SEED_PASSWORD`. Set both inline on the command rather than in `.env`, since they're only needed for this one-off run, not by the running app. In a second terminal:

```sh
cd backend
CAREER_SCRAPER_SEED_USERNAME=<username> CAREER_SCRAPER_SEED_PASSWORD=<password> uv run python tests/test_seed_companies.py
```

Companies are also manageable directly via SQL — see [config-schema.md](./docs/config-schema.md).

A few things to try once you have data:

```sh
curl http://127.0.0.1:8000/api/companies
curl -X POST http://127.0.0.1:8000/api/companies/voltus/scrape
curl http://127.0.0.1:8000/api/companies/voltus/jobs
```

### Frontend

With the backend running on port 8000 (above), in a separate terminal:

```sh
cd frontend
./frontend-start.sh
```

This installs npm dependencies and starts the dev server. Opens at `http://localhost:5173/`. The Vite dev server proxies `/api/*` requests to `http://127.0.0.1:8000`, so no CORS setup is needed — just make sure the backend is running on port 8000 first.

## Docs in this folder

- [`architecture.md`](./docs/architecture.md) — system components, data flow, and repo structure.
- [`config-schema.md`](./docs/config-schema.md) — settings file format and the `Company` model.
- [`job-schema.md`](./docs/job-schema.md) — the `JobPosting` schema for an extracted job posting.
- [`roadmap.md`](./docs/roadmap.md) — phased build plan (V1/V2/V3) and open questions/risks.
