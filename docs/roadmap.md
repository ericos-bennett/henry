# Roadmap

## Scope note

This is a personal project for a single user, not a multi-tenant service. Decisions below are made with that in mind — e.g. LLM cost and concurrency are not being engineered for scale, since the site list and request volume are expected to stay small.

## V1 — MVP

Goal: a working end-to-end pipeline for a small, hand-curated list of sites.

- Config Loader for `config/sites.yaml` (see [config-schema.md](./config-schema.md)).
- Scheduler that runs each site independently on its configured frequency.
- Fetcher using Playwright (headless), with a basic navigation timeout (no retry logic or rate limiting — see V2).
- Extractor: provider-agnostic LLM interface, with a Claude implementation as the default. Extracts from the career page's **listing view only** — no crawling into individual job detail pages (see decision below).
- Validator against the job posting schema (see [job-schema.md](./job-schema.md)).
- Storage Writer producing `data/<site_id>/<timestamp>.json` snapshots.
- CLI: `run` (start the service) and `run-once --site <id>` (manual trigger).
- Structured logging per run (per-site success/failure, job counts).

## V2 — Hardening & change tracking

- **Diffing/change detection**: compare each run's snapshot to the previous one for that site and record new/changed/removed jobs (as a separate diff file or a field alongside the snapshot).
- Pagination / infinite-scroll support in the Fetcher, driven by the `pagination` config hints.
- Per-site fetch customization beyond `wait_selector` (e.g. custom headers, cookies/auth if needed).
- robots.txt compliance and configurable rate limiting/politeness between requests.
- Retry/backoff and dead-letter handling for persistently failing sites.
- Optional: detail-page crawling for a fuller `description`, if listing-only extraction proves insufficient (see decision below).

## V3 — Usability

- Notifications (email/Slack) when new jobs are detected, built on top of V2's diffing.
- Dashboard/UI for managing tracked sites and browsing historical snapshots (replacing hand-edited YAML as the primary interface, if desired).
- Optional database-backed storage as an alternative to flat files, for querying across sites/history.
- Cross-site deduplication (the same role posted to multiple boards/aggregators).

## Decisions

- **Detail-page depth**: resolved for v1 — extraction works from the career page's listing view only (title/location/link/whatever summary is shown there). No per-job detail-page visits. Revisit in V2 if listing pages don't carry enough info (e.g. `description` ends up too sparse to be useful).
- **LLM cost**: not a v1 design constraint. This is a single-user, small-site-list project, so per-run token usage is low and not worth optimizing for yet. Revisit only if the site list or frequency grows significantly.

## Open questions / risks

- **Sites requiring auth or blocking bots**: some career pages may sit behind login walls or bot-detection (e.g. Cloudflare challenges). Out of scope for V1; needs a decision on whether/how to support later.
- **Timezone handling**: how per-site `frequency` cron expressions interpret time (server-local vs. UTC vs. per-site timezone).
- **Testing strategy**: fixture HTML pages per site archetype (static, JS-rendered, paginated) plus mocked LLM responses, so extraction logic can be tested without live API calls or live scraping.
- **Retention/cleanup**: whether old snapshot files are kept indefinitely or pruned after some age/count, once the `data/` directory starts accumulating history.
