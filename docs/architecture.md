# Architecture

## Components

**Config Loader**
Reads global settings (LLM provider, Playwright options, storage root for debug artifacts, logging level) from `config/settings.yaml` at startup (see [config-schema.md](./config-schema.md)). The tracked site list is *not* part of this file — see Persistence below.

**Persistence (Django ORM + Postgres)**
The site list and job posting outputs are structured records in Postgres, accessed via Django's ORM (`src/app/models.py`: `Site`, `JobPosting`). Django was adopted specifically because this app is expected to eventually grow into a **Django Ninja** API backend — using Django's ORM now means that future backend can reuse the exact same models with zero data-layer rewrite, just adding `urls.py`/Ninja schemas on top. There's no web server today; Django is used purely for its ORM and migrations (`manage.py migrate`), bootstrapped in the CLI via `app.django_setup.ensure_django_setup()`. Site rows are managed directly via SQL for now (see [config-schema.md](./config-schema.md)) — no CLI CRUD yet.

**Scheduler** *(not yet built)*
A long-running process component that keeps one schedule per site, triggering that site's scrape job when its configured frequency elapses, based on each `Site.frequency` cron expression. Each site's schedule is independent — sites don't wait on each other. Also exposes a way to trigger a single site's job on demand (used by the CLI's `extract`).

**Fetcher (Playwright)**
Given a `Site` row's URL, launches/reuses a headless browser session, navigates to the page, waits for content to render (network idle and/or `Site.wait_selector`), and returns the rendered HTML/text. Handles basic pagination/infinite-scroll if configured for that site (see open questions in [roadmap.md](./roadmap.md) for depth-of-crawl decisions). Applies a request timeout; retry/backoff and rate limiting are out of scope for V1 (see [roadmap.md](./roadmap.md)).

**Extractor (LLM, provider-agnostic)**
Takes the fetched page text and produces a list of `ExtractedJob` (Pydantic — see [job-schema.md](./job-schema.md)). Defined behind an abstract interface (`LLMExtractor.extract(content: str) -> list[ExtractedJob]`) so the concrete provider is swappable via `settings.llm` — Claude is the recommended default implementation, with Gemini currently wired up for free-tier testing. Uses structured JSON output so the LLM's response conforms to the schema rather than free-form text. `to_job_postings()` then converts each `ExtractedJob` into an (unsaved) `JobPosting` model instance, flattening `salary_range` into flat columns and attaching the `Site` FK, `source_url`, and `scraped_at`.

**Storage**
`save_job_postings()` bulk-inserts the run's `JobPosting` rows into Postgres. `write_raw_html()` separately writes the raw fetched HTML to `data/<site_id>/raw/<timestamp>.html` as a filesystem debug artifact (unaffected by the Postgres migration — this is not part of the structured job data).

**Orchestrator / Runner** *(not yet built)*
Will tie the above together for a single site's scrape: Fetcher → Extractor → Storage, with logging and error handling so a failure at any stage is caught, logged, and doesn't crash the service or affect other sites. Today the CLI's `extract` command does this directly for one site at a time.

**CLI**
- `career-scraper fetch --site <id>` — fetch a site's page and save the raw HTML debug dump.
- `career-scraper extract --site <id>` — fetch, extract via the configured LLM, and save the resulting `JobPosting` rows to Postgres.
- `run` (all sites, on schedule) is planned once the Scheduler is built.

**Logging & error handling**
Structured, per-run logs (site id, start/end time, success/failure, counts of jobs extracted). Per-site isolation means one site's persistent failure (e.g. site down, blocked, LLM can't parse) is logged and retried on its own schedule rather than halting the service.

## Data flow

```
config/settings.yaml                              Postgres: Site
      │                                                  │
      ▼                                                  ▼
Config Loader                                   Site.objects.get(pk=...)
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
```

`write_raw_html()` runs alongside this (from `Fetcher`'s output) as a separate filesystem-only debug path, not shown above.

## Reliability notes

- **Per-site isolation**: each site's scrape runs and fails independently; exceptions are caught at the CLI/Orchestrator level and logged rather than propagated.
- **Retry/backoff and rate limiting**: out of scope for V1 — a failed fetch simply fails that run's cycle and is picked up again on the next scheduled trigger. Retry/backoff, request throttling, and robots.txt compliance are planned for V2 (see [roadmap.md](./roadmap.md)).

## Repo structure

```
henry/
├── docs/                     # this folder
├── config/
│   └── settings.yaml         # LLM/Playwright/storage/logging settings only — no site list
├── data/
│   └── <site_id>/
│       └── raw/<timestamp>.html   # raw HTML debug dumps only; job postings live in Postgres
├── manage.py                 # Django management commands (migrate, makemigrations, etc.)
├── src/
│   └── app/
│       ├── settings.py       # Django settings (DATABASE_URL, INSTALLED_APPS=["app"])
│       ├── django_setup.py   # ensure_django_setup(), called before any ORM use outside manage.py
│       ├── models.py         # Site, JobPosting (Django models)
│       ├── migrations/       # Django migrations
│       ├── config.py         # Config Loader (Pydantic, settings.yaml only)
│       ├── fetcher.py        # Playwright-based Fetcher
│       ├── extractor.py      # LLM Extractor interface + provider implementations
│       ├── schema.py         # ExtractedJob/SalaryRange (LLM-facing Pydantic contract)
│       ├── storage.py        # save_job_postings(), write_raw_html()
│       └── cli.py
└── tests/
```
