# Architecture

## Components

**Config Loader**
Reads global settings (LLM provider, Playwright options, storage root for debug artifacts, logging level) from `backend/config/settings.yaml` at startup (see [config-schema.md](./config-schema.md)). The tracked company list is *not* part of this file — see Persistence below.

**Persistence (Django ORM + Postgres)**
The company list and job posting outputs are structured records in Postgres, accessed via Django's ORM (`backend/src/app/models.py`: `Company`, `JobPosting`). Django was adopted specifically because this app is a **Django Ninja** API backend — using Django's ORM means the API layer reuses the exact same models with no data-layer translation. Company rows are managed directly via SQL, or via the REST API's `POST`/`DELETE /api/companies` endpoints — see [config-schema.md](./config-schema.md).

**Scheduler** *(not yet built)*
A long-running process component that keeps one schedule per company, triggering that company's scrape job when its configured frequency elapses, based on each `Company.frequency` cron expression. Each company's schedule is independent — companies don't wait on each other. Until this exists, scrapes are triggered on demand via `POST /api/companies/{id}/scrape`.

**Fetcher (Playwright)**
Given a `Company` row's URL, launches/reuses a headless browser session, navigates to the page, waits for network idle, and returns the rendered HTML/text. Handles basic pagination/infinite-scroll if configured for that company (see open questions in [roadmap.md](./roadmap.md) for depth-of-crawl decisions). Applies a request timeout; retry/backoff and rate limiting are out of scope for V1 (see [roadmap.md](./roadmap.md)).

**Extractor (LLM, provider-agnostic)**
Takes the fetched page text and produces a list of `ExtractedJob` (Pydantic — see [job-schema.md](./job-schema.md)). Defined behind an abstract interface (`LLMExtractor.extract(content: str) -> list[ExtractedJob]`) so the concrete provider is swappable via `settings.llm` — Claude is the recommended default implementation, with Gemini currently wired up for free-tier testing. Uses structured JSON output so the LLM's response conforms to the schema rather than free-form text. `to_job_postings()` then converts each `ExtractedJob` into an (unsaved) `JobPosting` model instance, flattening `salary_range` into flat columns and attaching the `Company` FK, `source_url`, and `scraped_at`.

**Storage**
`save_job_postings()` bulk-inserts the run's `JobPosting` rows into Postgres. `write_raw_html()` separately writes the raw fetched HTML to `data/<company_id>/raw/<timestamp>.html` as a filesystem debug artifact (not part of the structured job data).

**API (Django Ninja)**
`backend/src/app/api.py` defines the REST endpoints, mounted at `/api/` (`backend/src/app/urls.py`):
- `GET /api/companies`, `GET /api/companies/{id}` — list/get tracked companies.
- `POST /api/companies` — create a company (validates `frequency` as a cron expression).
- `DELETE /api/companies/{id}` — remove a company (cascades to its job postings).
- `GET /api/companies/{id}/jobs` — a company's postings, with a `latest_only` filter for just the most recent scrape.
- `GET /api/jobs` — search across all companies (filters: `company_id`, `location`, `salary_min`).
- `POST /api/companies/{id}/scrape` — runs Fetcher → Extractor → Storage synchronously for one company and returns a summary (`jobs_found`, `scraped_at`). Runs inline on the request (no background task queue yet), so this call blocks for as long as the fetch + LLM call take.

Django Ninja auto-generates an interactive API console (Swagger UI) at `GET /api/docs`, plus the raw OpenAPI schema at `GET /api/openapi.json`. Rendering `/api/docs` requires Django's template engine, so `settings.py` configures a minimal `TEMPLATES` entry purely for this — nothing else in the project uses Django templates.

**Logging & error handling**
Structured, per-run logs (company id, start/end time, success/failure, counts of jobs extracted). Per-company isolation means one company's persistent failure (e.g. site down, blocked, LLM can't parse) doesn't affect scraping other companies.

**Frontend (React + Vite)**
`frontend/` is a single-page React + TypeScript app (`frontend/src/App.tsx`) that talks to the same REST API: lists companies, triggers `POST /api/companies/{id}/scrape` and shows the result, expands a company to view its latest job postings, and has a small form for `POST /api/companies`. It's a separate app from the backend (own `package.json`, own dev server on port 5173) — no server-side rendering or backend template involvement. In development, Vite's dev server proxies `/api/*` requests to `http://127.0.0.1:8000` (`frontend/vite.config.ts`), so no CORS configuration is needed on the Django side.

## Data flow

```
config/settings.yaml                              Postgres: Company
      │                                                  │
      ▼                                                  ▼
Config Loader                                Company.objects.get(pk=...)
      │                                                  │
      └──────────────────┬───────────────────────────────┘
                          ▼
                     Fetcher (Playwright)
                          │
                   rendered HTML/text
                          ▼
             Extractor (LLM, provider-agnostic)
                          │
                  ExtractedJob[] (raw)
                          ▼
                    to_job_postings()
                          │
              JobPosting[] (unsaved model instances)
                          ▼
                 save_job_postings()
                          │
                          ▼
              Postgres: JobPosting (bulk insert)
                          │
                          ▼
              ScrapeResult response (POST /api/companies/{id}/scrape)
```

`write_raw_html()` runs alongside this (from `Fetcher`'s output) as a separate filesystem-only debug path, not shown above.

## Reliability notes

- **Per-company isolation**: each company's scrape runs and fails independently; an unhandled exception during `POST /api/companies/{id}/scrape` surfaces as a 500 response for that request without affecting other companies.
- **Retry/backoff and rate limiting**: out of scope for V1 — a failed scrape simply fails that request; the caller retries manually (or the future Scheduler retries on its own schedule). Retry/backoff, request throttling, and robots.txt compliance are planned for V2 (see [roadmap.md](./roadmap.md)).

## Repo structure

This is a monorepo: `backend/` (Django Ninja API) and `frontend/` (React) are independent apps with their own dependency manifests and dev servers, sharing only the REST API contract between them.

```
henry/
├── docs/                      # this folder
├── backend/
│   ├── manage.py              # Django management commands (migrate, makemigrations, etc.)
│   ├── pyproject.toml         # uv-managed Python deps
│   ├── config/
│   │   └── settings.yaml      # LLM/Playwright/storage/logging settings only — no company list
│   ├── data/
│   │   └── <company_id>/
│   │       └── raw/<timestamp>.html   # raw HTML debug dumps only; job postings live in Postgres
│   ├── tests/
│   │   └── test_seed_companies.py     # hits the live API to bootstrap 3 real companies
│   └── src/
│       └── app/
│           ├── settings.py    # Django settings (DATABASE_URL, INSTALLED_APPS=["app"])
│           ├── urls.py        # mounts the Ninja API at /api/
│           ├── wsgi.py / asgi.py  # standard Django entry points
│           ├── models.py      # Company, JobPosting (Django models)
│           ├── migrations/    # Django migrations
│           ├── config.py      # Config Loader (Pydantic, settings.yaml only)
│           ├── fetcher.py     # Playwright-based Fetcher
│           ├── extractor.py   # LLM Extractor interface + provider implementations
│           ├── schema.py      # ExtractedJob/SalaryRange (LLM-facing Pydantic contract)
│           ├── schemas.py     # Ninja request/response schemas (CompanyIn/Out, JobPostingOut, ScrapeResult)
│           ├── storage.py     # save_job_postings(), write_raw_html()
│           └── api.py         # REST endpoints
└── frontend/
    ├── package.json           # npm-managed dependencies (React, Vite, TypeScript)
    ├── vite.config.ts         # dev server + /api proxy to the backend
    └── src/
        ├── App.tsx            # the single page: company list, scrape trigger, job viewer
        └── api.ts             # typed fetch client for the backend REST API
```
