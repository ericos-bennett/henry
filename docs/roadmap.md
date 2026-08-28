# Roadmap

## Scope note

This is a small personal-use project, not a service built for scale. It now supports multiple authenticated users (Django sessions, each with their own companies/preferences — see [architecture.md](./architecture.md)), but user accounts are still hand-provisioned via Django admin, not self-serve signup. LLM cost and concurrency are not being engineered for scale, since the company list and request volume per user are expected to stay small.

## V1 — MVP

Goal: a working end-to-end pipeline for a small, hand-curated list of companies.

- Config Loader for `backend/config/settings.yaml` (see [config-schema.md](./config-schema.md)).
- Fetcher using Playwright (headless), with a basic navigation timeout (no retry logic or rate limiting — see V2).
- Extractor: provider-agnostic LLM interface, with a Claude implementation as the default. Extracts from the career page's **listing view only** — no crawling into individual job detail pages (see decision below).
- Company list and job posting output as structured records in Postgres via Django's ORM, chosen because the app is a Django Ninja backend (see [architecture.md](./architecture.md)) — done ahead of schedule, pulled forward from V3.
- REST API (Django Ninja) replacing the original CLI plan: `GET/POST/PATCH/DELETE /api/companies`, `GET /api/companies/{id}/jobs`, `GET /api/jobs`, `POST /api/companies/{id}/scrape` — see [architecture.md](./architecture.md) for the full list.
- Structured logging per run (per-company success/failure, job counts).
- Multi-user auth (Django sessions) with per-user company/preferences ownership, and OpenTelemetry-based logging export — both done ahead of schedule, pulled forward from later phases.
- Per-user job preferences (`locations`/`keywords`) and a recommendation match against them (`app/matching.py`), surfaced in the UI and used to filter notification emails — pulled forward from V3's notifications work.
- Email notifications (SMTP, provider-agnostic) when a scrape finds a new job matching preferences, plus a staff-only "scrape all + combined digest" action — pulled forward from V3, ahead of the diffing/change-tracking work in V2 it was originally planned to sit on top of. This only works because `JobPosting.is_new` is derived per posting (`first_scrape_timestamp == latest_scrape_timestamp`); broader diff/history reporting (below) is still open.
- `JobPosting` rows collapsed from one-per-scrape to one-per-lifetime: `save_job_postings()` updates a row in place across consecutive scrapes that still find the job, instead of inserting a duplicate every run, and only starts a new row when a job is genuinely new or reappears after a gap — see [job-schema.md](./job-schema.md). A step toward the "Diffing/change detection" V2 item below, though the fuller history/report is still open.

## V2 — Hardening & change tracking

- **Scheduler**: run each company's scrape automatically on its configured `frequency`, instead of only on demand via `POST /api/companies/{id}/scrape` (or the staff-only `scrape-all`).
- **Diffing/change detection**: each `JobPosting` row now tracks its own lifetime (`first_scrape_timestamp`/`latest_scrape_timestamp`, `is_new`), and a reappearance after a gap gets its own row — but there's still no query/report surfacing that history (e.g. "jobs removed since last week", "how long has this posting been up").
- ~~Pagination / infinite-scroll support in the Fetcher~~ — done, but as a generic heuristic (next-page/load-more selector set + infinite scroll, capped at `playwright.max_pages`), not per-company config hints. Add per-company overrides only if the heuristic misses real pages.
- Per-company fetch customization (e.g. a wait-for-selector override, custom headers, cookies/auth) if network-idle alone proves insufficient for some pages — dropped from v1's `Company` model since it's not something a user can supply upfront without inspecting the page first (see [Decisions](#decisions)).
- robots.txt compliance and configurable rate limiting/politeness between requests.
- Retry/backoff and dead-letter handling for persistently failing companies.
- Moving `POST /api/companies/{id}/scrape` off the request/response cycle (background task queue) so it doesn't block on Playwright + LLM latency. (`PATCH /api/companies/{id}` itself is done — see [architecture.md](./architecture.md).)
- Optional: detail-page crawling for a fuller job description, if listing-only extraction proves insufficient (see decision below) — the `description` column itself was removed as unused; reintroduce it if this is picked up.

## V3 — Usability

- Slack notifications, as an alternative/addition to the email notifications already built (see [architecture.md](./architecture.md)).
- Expand the `frontend/` app beyond its current single page (richer job browsing/filtering, scrape status/history) — create/delete companies, a preferences form, and a staff-only admin section are done as a minimal first pass, pulled forward from V3.
- Cross-company deduplication (the same role posted to multiple boards/aggregators).
- Self-serve signup — accounts are currently provisioned by hand via Django admin.

## Decisions

- **Detail-page depth**: resolved for v1 — extraction works from the career page's listing view only (title/location/link/whatever summary is shown there). No per-job detail-page visits. The `description` column was removed as unused (nothing read it); revisit in V2 if listing pages don't carry enough info and detail-page crawling gets picked up.
- **LLM cost**: not a v1 design constraint. This is a single-user, small-company-list project, so per-run token usage is low and not worth optimizing for yet. Revisit only if the company list or frequency grows significantly.
- **`wait_selector`**: removed from the `Company` model. It required knowing a CSS selector for a page's rendered content, which isn't something a user can supply when first adding a company — it's only discoverable by inspecting the page (or hitting a failed/incomplete scrape) after the fact. The Fetcher relies solely on Playwright's network-idle wait for now; revisit as a per-company override in V2 if that proves insufficient for some pages.

## Open questions / risks

- **Companies requiring auth or blocking bots**: some career pages may sit behind login walls or bot-detection (e.g. Cloudflare challenges). Out of scope for V1; needs a decision on whether/how to support later.
- **Timezone handling**: how per-company `frequency` cron expressions interpret time (server-local vs. UTC vs. per-company timezone) — matters once the Scheduler is built.
- **Testing strategy**: fixture HTML pages per company-page archetype (static, JS-rendered, paginated) plus mocked LLM responses, so extraction logic can be tested without live API calls or live scraping.
- **Retention/cleanup**: whether old `JobPosting` rows (Postgres) are kept indefinitely or pruned after some age/count, once history starts accumulating. Raw HTML debug dumps (`data/`) are pruned weekly on the home-server deploy (`deploy/weekly-maintenance.sh` → `clear-snapshots.sh <days>`, default 7); still no `JobPosting` row policy.
