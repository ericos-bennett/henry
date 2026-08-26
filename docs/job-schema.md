# Job Posting Schema

Every extracted job listing is persisted as a row in Postgres's `JobPosting` table (`backend/src/app/models.py`). This is the contract between the Extractor and the database (see [architecture.md](./architecture.md)).

Since extraction is LLM-based across arbitrary company page layouts, quality and field availability vary by company — most fields beyond `title` are **best-effort and nullable**. The LLM itself returns a nested `salary_range` object (see `app.schema.ExtractedJob`/`SalaryRange`); the Extractor flattens it into three columns before the row is saved, since flat columns are what's queryable in SQL (e.g. `WHERE salary_min >= 100000`).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `job_id` | string | no | Stable identifier for this posting, derived from `source_company_id` + `url` (or title + location, if no per-job URL exists). Unique together with `scraped_at` — see note below. |
| `is_new` | boolean | no (default `false`) | Whether this `job_id` was absent from the immediately preceding scrape of this company. Set by `save_job_postings()` at write time (`app/storage.py`); `false` on a company's very first scrape (nothing to diff against). Drives the new-job notification email — see [architecture.md](./architecture.md). |
| `title` | string | no | Job title as posted. |
| `url` | string | yes | Direct link to the job's description/detail page, if the page provides one — normalized away from an "Apply"-form URL when the two differ. |
| `location` | string | yes | Location as posted (city/remote/etc.), free text. |
| `department` | string | yes | Team/department, if listed. |
| `employment_type` | string | yes | e.g. "Full-time", "Contract", if listed. |
| `salary_min` | float | yes | Best-effort parsed minimum salary. |
| `salary_max` | float | yes | Best-effort parsed maximum salary. |
| `salary_currency` | string | yes | e.g. "USD", if determinable. |
| `posted_date` | string | yes | Date the job was posted, as posted (not normalized to a real date type — companies phrase this inconsistently too). |
| `source_company` | FK → `Company.id` | no | The company this posting came from. |
| `source_url` | string | no | The career page URL that was scraped to find this posting. |
| `scraped_at` | datetime (tz-aware) | no | Timestamp of the run that produced this record. |

## Why `job_id` isn't globally unique

v1 is snapshot-only — there's no diffing/upsert logic yet (see [roadmap.md](./roadmap.md)), so the same job legitimately gets a fresh row on every scrape run. The uniqueness constraint is `(job_id, scraped_at)` together, not `job_id` alone: it prevents duplicate rows *within* a single run, while still letting the same job accumulate a row per run over time — which is exactly what a future diffing feature would query against.

## Example row

```json
{
  "job_id": "9f3a1c2b4d5e",
  "source_company_id": "acme-corp",
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
  "posted_date": "2026-08-14",
  "is_new": true
}
```

## `UserPreferences`

Each user has at most one `UserPreferences` row (`backend/src/app/models.py`), managed via `GET`/`PUT /api/preferences` — not extracted or written by the scrape pipeline itself. It drives job matching (`app/matching.py`'s `is_recommended()`), which powers both the `is_recommended` field on `JobPostingOut` (API-only — computed per request, not a database column) and the recommended-jobs filter used by notification emails (see [architecture.md](./architecture.md)).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `owner` | FK → `User.id` (one-to-one) | no | The user these preferences belong to. |
| `locations` | array of string | no (default `[]`) | Case-insensitive substring matches against a job's `location`. A job with no `location` at all is never disqualified by this — see matching note below. |
| `keywords` | array of string | no (default `[]`) | Case-insensitive substring matches against a job's `title`. |

Both `locations` and `keywords` must be non-empty for anything to be `is_recommended` — leaving either one unset means nothing is recommended, rather than matching on just the other.
