# Job Posting Schema

Every extracted job listing is persisted as a row in Postgres's `JobPosting` table (`src/app/models.py`). This is the contract between the Extractor and the database (see [architecture.md](./architecture.md)).

Since extraction is LLM-based across arbitrary site layouts, quality and field availability vary by site — most fields beyond `title` are **best-effort and nullable**. The LLM itself returns a nested `salary_range` object (see `app.schema.ExtractedJob`/`SalaryRange`); the Extractor flattens it into four columns before the row is saved, since flat columns are what's queryable in SQL (e.g. `WHERE salary_min >= 100000`).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `job_id` | string | no | Stable identifier for this posting, derived from `source_site_id` + `url` (or title, if no per-job URL exists). Unique together with `scraped_at` — see note below. |
| `title` | string | no | Job title as posted. |
| `url` | string | yes | Direct link to the job posting, if the page provides one. |
| `location` | string | yes | Location as posted (city/remote/etc.), free text. |
| `department` | string | yes | Team/department, if listed. |
| `employment_type` | string | yes | e.g. "Full-time", "Contract", if listed. |
| `salary_min` | float | yes | Best-effort parsed minimum salary. |
| `salary_max` | float | yes | Best-effort parsed maximum salary. |
| `salary_currency` | string | yes | e.g. "USD", if determinable. |
| `salary_raw` | string | yes | Original salary text as posted (e.g. "$120K - $150K/yr") — postings phrase this inconsistently, so this is kept verbatim alongside the parsed fields. |
| `description` | string | yes | Whatever summary/description text is present in the career page's listing view (v1 extracts listing-only, no detail-page visits — see [roadmap.md](./roadmap.md)). May be brief or absent depending on the site. |
| `posted_date` | string | yes | Date the job was posted, as posted (not normalized to a real date type — sites phrase this inconsistently too). |
| `source_site` | FK → `Site.id` | no | The site this posting came from. |
| `source_url` | string | no | The career page URL that was scraped to find this posting. |
| `scraped_at` | datetime (tz-aware) | no | Timestamp of the run that produced this record. |

## Why `job_id` isn't globally unique

v1 is snapshot-only — there's no diffing/upsert logic yet (see [roadmap.md](./roadmap.md)), so the same job legitimately gets a fresh row on every scrape run. The uniqueness constraint is `(job_id, scraped_at)` together, not `job_id` alone: it prevents duplicate rows *within* a single run, while still letting the same job accumulate a row per run over time — which is exactly what a future diffing feature would query against.

## Example row

```json
{
  "job_id": "9f3a1c2b4d5e",
  "source_site_id": "acme-corp",
  "source_url": "https://acme.example.com/careers",
  "scraped_at": "2026-08-20T10:00:00Z",
  "title": "Senior Backend Engineer",
  "url": "https://acme.example.com/careers/senior-backend-engineer",
  "location": "Remote (US)",
  "department": "Engineering",
  "employment_type": "Full-time",
  "salary_min": 120000,
  "salary_max": 150000,
  "salary_currency": "USD",
  "salary_raw": "$120K - $150K/yr",
  "description": "We're looking for a Senior Backend Engineer to...",
  "posted_date": "2026-08-14"
}
```
