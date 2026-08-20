# Architecture

## Components

**Config Loader**
Reads the site-list config file (see [config-schema.md](./config-schema.md)) and global settings (LLM provider, Playwright options, storage root, logging level) at startup. Validates the config and hands each site's definition to the Scheduler.

**Scheduler**
A long-running process component that keeps one schedule per site, triggering that site's scrape job when its configured frequency elapses. Each site's schedule is independent — sites don't wait on each other. Also exposes a way to trigger a single site's job on demand (used by the CLI's `run-once`).

**Fetcher (Playwright)**
Given a site's URL, launches/reuses a headless browser session, navigates to the page, waits for content to render (network idle and/or a configured wait-selector), and returns the rendered HTML/text. Handles basic pagination/infinite-scroll if configured for that site (see open questions in [roadmap.md](./roadmap.md) for depth-of-crawl decisions). Applies a request timeout; retry/backoff and rate limiting are out of scope for V1 (see [roadmap.md](./roadmap.md)).

**Extractor (LLM, provider-agnostic)**
Takes the fetched page content and produces a list of structured job postings. Defined behind an abstract interface (e.g. `LLMExtractor.extract(content: str) -> list[JobPosting]`) so the concrete provider is swappable via config — Claude is the recommended default implementation, with room to add others (OpenAI, etc.) without touching the rest of the pipeline. Uses structured output / tool-use so the LLM's response conforms to the job schema rather than free-form text.

**Validator**
Runs the Extractor's output through the job posting schema (see [job-schema.md](./job-schema.md)), coercing/validating types and dropping or flagging entries that don't fit. Ensures downstream files always contain well-formed JSON.

**Storage Writer**
Writes the validated list of job postings for a given run to `data/<site_id>/<ISO8601-timestamp>.json`.

**Orchestrator / Runner**
Ties the above together for a single site's scrape: Fetcher → Extractor → Validator → Storage Writer, with logging and error handling so a failure at any stage is caught, logged, and doesn't crash the service or affect other sites.

**CLI**
Thin entry points for operating the service:
- `run` — start the long-running scheduler service (all sites, on their configured frequencies).
- `run-once --site <id>` — trigger a single site's scrape immediately, useful for testing/backfill.

**Logging & error handling**
Structured, per-run logs (site id, start/end time, success/failure, counts of jobs extracted). Per-site isolation means one site's persistent failure (e.g. site down, blocked, layout LLM can't parse) is logged and retried on its own schedule rather than halting the service.

## Data flow

```
config/sites.yaml
      │
      ▼
Config Loader ──► Scheduler ──(per site, on its frequency)──► Orchestrator
                                                                   │
                                                                   ▼
                                                        Fetcher (Playwright)
                                                                   │
                                                            rendered HTML/text
                                                                   ▼
                                                     Extractor (LLM, provider-agnostic)
                                                                   │
                                                           JobPosting[] (raw)
                                                                   ▼
                                                              Validator
                                                                   │
                                                          JobPosting[] (validated)
                                                                   ▼
                                                            Storage Writer
                                                                   │
                                                                   ▼
                                          data/<site_id>/<ISO8601-timestamp>.json
```

## Reliability notes

- **Per-site isolation**: each site's scrape runs and fails independently; exceptions are caught at the Orchestrator level and logged rather than propagated.
- **Retry/backoff and rate limiting**: out of scope for V1 — a failed fetch simply fails that run's cycle and is picked up again on the next scheduled trigger. Retry/backoff, request throttling, and robots.txt compliance are planned for V2 (see [roadmap.md](./roadmap.md)).

## Proposed repo structure

```
henry/
├── docs/                  # this folder
├── config/
│   └── sites.yaml         # user-maintained list of tracked career pages
├── data/
│   └── <site_id>/
│       └── <timestamp>.json
├── src/
│   └── app/
│       ├── config.py      # Config Loader
│       ├── scheduler.py   # Scheduler
│       ├── fetcher.py     # Playwright-based Fetcher
│       ├── extractor/     # LLM Extractor interface + provider implementations
│       ├── schema.py      # Job posting schema (Validator)
│       ├── storage.py     # Storage Writer
│       ├── orchestrator.py
│       └── cli.py
└── tests/
```
