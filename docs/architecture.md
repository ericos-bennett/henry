# Architecture

## Components

**Config Loader**
Reads global settings (LLM provider, Playwright options, storage root for debug artifacts, logging level) from `backend/config/settings.yaml` at startup (see [config-schema.md](./config-schema.md)). The tracked company list is *not* part of this file — see Persistence below.

**Persistence (Django ORM + Postgres)**
The company list and job posting outputs are structured records in Postgres, accessed via Django's ORM (`backend/src/app/models.py`: `Company`, `JobPosting`, `UserPreferences`). Django was adopted specifically because this app is a **Django Ninja** API backend — using Django's ORM means the API layer reuses the exact same models with no data-layer translation. Company rows are managed directly via SQL, or via the REST API's `POST`/`PATCH`/`DELETE /api/companies` endpoints — see [config-schema.md](./config-schema.md).

**Auth & multi-user (Django sessions)**
This is no longer single-user: every `Company` has an `owner` FK (`django.contrib.auth` user), and all `/api/companies*` and `/api/jobs*` endpoints filter by `request.user`. The API is protected end-to-end by `django_auth` (session-cookie auth, `NinjaAPI(auth=django_auth)` in `api.py`), with `POST /api/login`, `POST /api/logout`, and `GET /api/me` as the only unauthenticated/self-describing endpoints. User accounts are created via Django's admin site (`/admin/`), not a signup flow. `User.is_staff` gates admin-only actions (currently just `POST /api/companies/scrape-all`) — staff-only, not superuser-only.

**Recommender (matching)**
`app/matching.py`'s `is_recommended(job, preferences) -> bool` compares a `JobPosting` against that user's `UserPreferences` (`locations`, `keywords`). A job with no `location` extracted at all is never disqualified by a location preference — it falls back to keyword-only matching. With no preferences saved at all, nothing is recommended. Used both to annotate API responses (`JobPostingOut.is_recommended`) and to decide what goes into notification emails.

**Notifier (email)**
`app/notifications.py` has two entry points, both best-effort (exceptions are caught and logged, never allowed to fail a scrape/request):
- `notify_new_recommended_jobs(company, jobs)` — called after every `run_scrape` (unless `notify=False`); emails the company's owner about postings from *this run* that are both new (`JobPosting.is_new`) and recommended.
- `notify_all_recommended_jobs(user)` — called by `POST /api/companies/scrape-all`; emails one combined digest of every *currently* recommended job across all of the user's companies, regardless of `is_new`.

**Scheduler** *(not yet built)*
A long-running process component that keeps one schedule per company, triggering that company's scrape job when its configured frequency elapses, based on each `Company.frequency` cron expression. Each company's schedule is independent — companies don't wait on each other. Until this exists, scrapes are triggered on demand via `POST /api/companies/{id}/scrape`.

**Fetcher (Playwright)**
Given a `Company` row's URL, launches/reuses a headless browser session, navigates to the page, waits for network idle, and returns the rendered HTML/text. Handles basic pagination/infinite-scroll if configured for that company (see open questions in [roadmap.md](./roadmap.md) for depth-of-crawl decisions). Applies a request timeout; retry/backoff and rate limiting are out of scope for V1 (see [roadmap.md](./roadmap.md)).

**Extractor (LLM, provider-agnostic)**
Takes the fetched page text and produces a list of `ExtractedJob` (Pydantic — see [job-schema.md](./job-schema.md)). Defined behind an abstract interface (`LLMExtractor.extract(content: str) -> list[ExtractedJob]`) so the concrete provider is swappable via `LLM_PROVIDER`/`LLM_MODEL` env vars — Claude is the recommended default implementation, with Gemini also wired up. Uses structured JSON output so the LLM's response conforms to the schema rather than free-form text. `to_job_postings()` then converts each `ExtractedJob` into an (unsaved) `JobPosting` model instance, flattening `salary_range` into flat columns, normalizing `url` to the job's description/detail page (not an "Apply" form URL), and attaching the `Company` FK, `source_url`, and `scraped_at`.

**Storage**
`save_job_postings()` diffs the run's `job_id`s against the immediately preceding run for that company to set each `JobPosting.is_new`, then bulk-inserts the rows into Postgres. `write_raw_html()` separately writes the raw fetched HTML to `data/<company_id>/raw/<timestamp>.html` as a filesystem debug artifact (not part of the structured job data).

**Pipeline**
`app/pipeline.py`'s `run_scrape(company, *, notify=True) -> ScrapeResult` orchestrates Fetcher → Extractor → Storage → Notifier for one company. Shared by `POST /api/companies/{id}/scrape`, the initial scrape-on-create, and `POST /api/companies/scrape-all` (which passes `notify=False` per-company and sends one combined digest itself instead) — so the orchestration isn't duplicated per caller.

**API (Django Ninja)**
`backend/src/app/api.py` defines the REST endpoints, mounted at `/api/` (`backend/src/app/urls.py`). All endpoints below require an authenticated session and are scoped to `request.user`'s own companies, except `POST /api/login`/`/api/logout` (`auth=None`):
- `POST /api/login`, `POST /api/logout`, `GET /api/me` — session auth; `/me` returns `{username, is_staff}`.
- `GET /api/companies`, `GET /api/companies/{id}` — list/get this user's tracked companies.
- `POST /api/companies` — create a company (validates `frequency` against a fixed allowed set, kept in sync with the frontend's frequency dropdown) and kicks off an immediate first scrape (best-effort — a failed initial scrape doesn't block company creation).
- `PATCH /api/companies/{id}` — partial update of `enabled` and/or `frequency`.
- `DELETE /api/companies/{id}` — remove a company (cascades to its job postings).
- `GET /api/companies/{id}/jobs` — a company's postings, with a `latest_only` filter for just the most recent scrape; each posting is annotated with `is_recommended` against the caller's saved preferences.
- `GET /api/jobs` — search across all of this user's companies (filters: `company_id`, `location`, `salary_min`), same `is_recommended` annotation.
- `GET/PUT /api/preferences` — read/replace the caller's `UserPreferences` (`locations`, `keywords`) used for job matching/recommendations and notification filtering.
- `POST /api/companies/{id}/scrape` — runs the Pipeline synchronously for one company and returns a summary (`jobs_found`, `scraped_at`). Runs inline on the request (no background task queue yet), so this call blocks for as long as the fetch + LLM call take.
- `POST /api/companies/scrape-all` — **staff-only** (`is_staff`, checked server-side); registered before `/companies/{id}` so the literal path segment isn't swallowed by that parameterized route. Scrapes every one of the user's companies (continuing past individual failures) and sends one combined recommended-jobs digest email, then returns `{companies_scraped, companies_failed, jobs_found}`.

Django Ninja auto-generates an interactive API console (Swagger UI) at `GET /api/docs`, plus the raw OpenAPI schema at `GET /api/openapi.json`. Rendering `/api/docs` requires Django's template engine, so `settings.py` configures a minimal `TEMPLATES` entry purely for this — nothing else in the project uses Django templates.

**Logging & error handling**
Structured, per-run logs (company id, start/end time, success/failure, counts of jobs extracted). Per-company isolation means one company's persistent failure (e.g. site down, blocked, LLM can't parse) doesn't affect scraping other companies.

**Frontend (React + Vite)**
`frontend/` is a single-page React + TypeScript app (`frontend/src/App.tsx`) that talks to the same REST API: a login form gating the rest of the app, a company list, triggers `POST /api/companies/{id}/scrape` and shows the result, expands a company to view its latest job postings (with recommended postings split out based on saved preferences), a "Preferences" form (`locations`/`keywords`), an "Add a Company" form, and — only rendered when `GET /api/me` reports `is_staff`— an "Admin" section with a "Scrape All" button (`POST /api/companies/scrape-all`). It's a separate app from the backend (own `package.json`, own dev server on port 5173) — no server-side rendering or backend template involvement. In development, Vite's dev server proxies `/api/*` requests to `http://127.0.0.1:8000` (`frontend/vite.config.ts`) with `changeOrigin: false` (preserves the original `Host` header so it keeps matching the browser's `Origin`, which Django's CSRF check requires), so no CORS configuration is needed on the Django side. `allowedHosts` in the same config lists non-localhost hostnames (e.g. a Cloudflare tunnel hostname) permitted to reach the dev server.

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
                    (diffs against previous run to set is_new)
                          ▼
              Postgres: JobPosting (bulk insert)
                          │
                          ├──────────────► notify_new_recommended_jobs() ──► email (if notify=True)
                          ▼
              ScrapeResult response (POST /api/companies/{id}/scrape)
```

`write_raw_html()` runs alongside this (from `Fetcher`'s output) as a separate filesystem-only debug path, not shown above. `POST /api/companies/scrape-all` runs this same flow per company with `notify=False`, then separately calls `notify_all_recommended_jobs()` once at the end for a combined digest.

## Reliability notes

- **Per-company isolation**: each company's scrape runs and fails independently; an unhandled exception during `POST /api/companies/{id}/scrape` surfaces as a 500 response for that request without affecting other companies. `scrape-all` goes further and continues past a per-company failure, reporting `companies_failed` in its response rather than aborting the batch.
- **Retry/backoff and rate limiting**: out of scope for V1 — a failed scrape simply fails that request; the caller retries manually (or the future Scheduler retries on its own schedule). Retry/backoff, request throttling, and robots.txt compliance are planned for V2 (see [roadmap.md](./roadmap.md)).
- **Notification failures never fail a scrape**: both notifier entry points catch and log all exceptions internally.

## Observability

`opentelemetry-distro`/`opentelemetry-exporter-otlp` are configured on the backend (`backend/src/app/settings.py` routes Django's stdlib logging so OTel's log auto-instrumentation can pick it up; export is controlled via standard `OTEL_*` env vars, e.g. `OTEL_LOGS_EXPORTER=otlp`). `start-all.sh` (repo root) runs a local `grafana/otel-lgtm` container (Grafana + Prometheus + Loki in one image, data persisted under `otel-data/`) as the OTLP receiver/viewer, alongside starting the backend and frontend dev servers each in their own `tmux` session. `stop-all.sh` tears down the tmux sessions and container. This is local dev tooling, not a deployed observability stack.

## Repo structure

This is a monorepo: `backend/` (Django Ninja API) and `frontend/` (React) are independent apps with their own dependency manifests and dev servers, sharing only the REST API contract between them.

```
henry/
├── docs/                      # this folder
├── start-all.sh                # tmux backend+frontend sessions, plus a local otel-lgtm container
├── stop-all.sh                 # tears down the above
├── clear-snapshots.sh          # deletes raw HTML debug dumps under backend/data/
├── backend/
│   ├── backend-start.sh        # installs deps, migrates, starts the dev server
│   ├── manage.py               # Django management commands (migrate, makemigrations, createsuperuser, etc.)
│   ├── pyproject.toml          # uv-managed Python deps
│   ├── config/
│   │   └── settings.yaml       # LLM/Playwright/storage/logging settings only — no company list
│   ├── data/
│   │   └── <company_id>/
│   │       └── raw/<timestamp>.html   # raw HTML debug dumps only; job postings live in Postgres
│   ├── tests/
│   │   └── test_seed_companies.py     # hits the live API to bootstrap 3 real companies
│   └── src/
│       └── app/
│           ├── settings.py    # Django settings (DATABASE_URL, auth, email, OTel logging, INSTALLED_APPS=["app"])
│           ├── urls.py        # mounts the Ninja API at /api/, Django admin at /admin/
│           ├── wsgi.py / asgi.py  # standard Django entry points
│           ├── models.py      # Company (owner FK), JobPosting (is_new), UserPreferences
│           ├── migrations/    # Django migrations
│           ├── config.py      # Config Loader (Pydantic, settings.yaml only)
│           ├── fetcher.py     # Playwright-based Fetcher
│           ├── extractor.py   # LLM Extractor interface + provider implementations
│           ├── schema.py      # ExtractedJob/SalaryRange (LLM-facing Pydantic contract)
│           ├── schemas.py     # Ninja request/response schemas (CompanyIn/Out/Patch, JobPostingOut, Preferences*, ScrapeResult, ScrapeAllResult, LoginIn, UserOut)
│           ├── matching.py    # is_recommended() — job vs. UserPreferences
│           ├── notifications.py  # notify_new_recommended_jobs(), notify_all_recommended_jobs()
│           ├── pipeline.py    # run_scrape() — Fetcher → Extractor → Storage → Notifier, shared by scrape/scrape-all
│           ├── storage.py     # save_job_postings() (also sets is_new), write_raw_html()
│           └── api.py         # REST endpoints
└── frontend/
    ├── frontend-start.sh       # installs npm deps, starts the dev server
    ├── package.json           # npm-managed dependencies (React, Vite, TypeScript)
    ├── vite.config.ts         # dev server + /api proxy to the backend + allowedHosts
    └── src/
        ├── App.tsx            # login gate, company list, scrape trigger, job viewer, preferences form, admin (staff-only) section
        └── api.ts             # typed fetch client for the backend REST API
```
