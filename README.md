# Career Page Scraper — Project Overview

## Problem

Job seekers, recruiters, and researchers often want to track job postings across a specific set of companies' career pages over time. Career pages vary wildly in structure (custom HTML, Greenhouse, Lever, Workday, etc.), many render listings via JavaScript, and there's no easy way to get a normalized, structured view of what's currently posted without visiting each site manually.

## What this application does

- Lets a user maintain a list of career page URLs, each with its own scrape frequency, in a local config file.
- On each site's schedule, fetches the rendered page (headless browser, to handle JS-heavy sites).
- Uses an LLM to translate the scraped content into structured job listing JSON (title, location, department, description, etc.) — no per-site parser required.
- Writes each run's results to a timestamped JSON file, so history accumulates as a series of snapshots.

## Goals (v1 / MVP)

- Config-driven: add/remove/edit tracked sites and their frequency by editing a YAML file — no UI required.
- Reliable per-site scheduling: each site runs independently on its own interval; one site failing doesn't block others.
- Works on both static and JS-rendered career pages.
- LLM-based extraction that works across arbitrary site layouts, via a provider-agnostic interface.
- Structured, validated JSON output on a consistent schema, written as timestamped snapshot files per site per run.

## Non-goals (v1)

- No diffing/change-detection between runs (snapshot only — see [roadmap.md](./docs/roadmap.md) for when this comes in).
- No web UI/dashboard.
- No notifications (email/Slack) on new postings.
- No database — plain files on disk.

## Docs in this folder

- [`architecture.md`](./docs/architecture.md) — system components, data flow, and proposed repo structure.
- [`config-schema.md`](./docs/config-schema.md) — the site-list config file format.
- [`job-schema.md`](./docs/job-schema.md) — the structured JSON schema for an extracted job posting.
- [`roadmap.md`](./docs/roadmap.md) — phased build plan (V1/V2/V3) and open questions/risks.
