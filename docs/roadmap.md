# Roadmap

## Scope note

This is a personal project for a single user, not a multi-tenant service. Decisions below are made with that in mind — e.g. LLM cost and concurrency are not being engineered for scale, since the company list and request volume are expected to stay small.

## V1 — MVP

Goal: a working end-to-end pipeline for a small, hand-curated list of companies.

- Config Loader for `backend/config/settings.yaml` (see [config-schema.md](./config-schema.md)).
- Fetcher using Playwright (headless), with a basic navigation timeout (no retry logic or rate limiting — see V2).
- Extractor: provider-agnostic LLM interface, with a Claude implementation as the default. Extracts from the career page's **listing view only** — no crawling into individual job detail pages (see decision below).
- Company list and job posting output as structured records in Postgres via Django's ORM, chosen because the app is a Django Ninja backend (see [architecture.md](./architecture.md)) — done ahead of schedule, pulled forward from V3.
- REST API (Django Ninja) replacing the original CLI plan: `GET/POST/DELETE /api/companies`, `GET /api/companies/{id}/jobs`, `GET /api/jobs`, `POST /api/companies/{id}/scrape` — see [architecture.md](./architecture.md) for the full list.
- Structured logging per run (per-company success/failure, job counts).

## V2 — Hardening & change tracking

- **Scheduler**: run each company's scrape automatically on its configured `frequency`, instead of only on demand via `POST /api/companies/{id}/scrape`.
- **Diffing/change detection**: compare each run's results to the previous one for that company and record new/changed/removed jobs.
- Pagination / infinite-scroll support in the Fetcher, driven by per-company config hints.
- Per-company fetch customization (e.g. a wait-for-selector override, custom headers, cookies/auth) if network-idle alone proves insufficient for some pages — dropped from v1's `Company` model since it's not something a user can supply upfront without inspecting the page first (see [Decisions](#decisions)).
- robots.txt compliance and configurable rate limiting/politeness between requests.
- Retry/backoff and dead-letter handling for persistently failing companies.
- `PATCH /api/companies/{id}` for partial updates (e.g. toggling `enabled`), and moving `POST /api/companies/{id}/scrape` off the request/response cycle (background task queue) so it doesn't block on Playwright + LLM latency.
- Optional: detail-page crawling for a fuller `description`, if listing-only extraction proves insufficient (see decision below).

## V3 — Usability

- Notifications (email/Slack) when new jobs are detected, built on top of V2's diffing.
- Dashboard/UI for managing tracked companies and browsing job history, built on the existing REST API.
- Cross-company deduplication (the same role posted to multiple boards/aggregators).

## Decisions

- **Detail-page depth**: resolved for v1 — extraction works from the career page's listing view only (title/location/link/whatever summary is shown there). No per-job detail-page visits. Revisit in V2 if listing pages don't carry enough info (e.g. `description` ends up too sparse to be useful).
- **LLM cost**: not a v1 design constraint. This is a single-user, small-company-list project, so per-run token usage is low and not worth optimizing for yet. Revisit only if the company list or frequency grows significantly.
- **`wait_selector`**: removed from the `Company` model. It required knowing a CSS selector for a page's rendered content, which isn't something a user can supply when first adding a company — it's only discoverable by inspecting the page (or hitting a failed/incomplete scrape) after the fact. The Fetcher relies solely on Playwright's network-idle wait for now; revisit as a per-company override in V2 if that proves insufficient for some pages.

## Open questions / risks

- **Companies requiring auth or blocking bots**: some career pages may sit behind login walls or bot-detection (e.g. Cloudflare challenges). Out of scope for V1; needs a decision on whether/how to support later.
- **Timezone handling**: how per-company `frequency` cron expressions interpret time (server-local vs. UTC vs. per-company timezone) — matters once the Scheduler is built.
- **Testing strategy**: fixture HTML pages per company-page archetype (static, JS-rendered, paginated) plus mocked LLM responses, so extraction logic can be tested without live API calls or live scraping.
- **Retention/cleanup**: whether old `JobPosting` rows (Postgres) and raw HTML debug dumps (`data/`) are kept indefinitely or pruned after some age/count, once history starts accumulating.
