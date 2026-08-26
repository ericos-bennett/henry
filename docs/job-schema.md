# Job Posting Schema

Every distinct job *lifetime* is persisted as one row in Postgres's `JobPosting` table (`backend/src/app/models.py`). This is the contract between the Extractor/Storage and the database (see [architecture.md](./architecture.md)). A row isn't a snapshot of one scrape — it's updated in place across every consecutive scrape that still finds the posting, and only gets a fresh row when the posting is genuinely new or reappears after being absent from a scrape.

Since extraction is LLM-based across arbitrary company page layouts, quality and field availability vary by company — most fields beyond `title` are **best-effort and nullable**. The LLM itself returns a nested `salary_range` object (see `app.schema.ExtractedJob`/`SalaryRange`); the Extractor flattens it into three columns before the row is saved, since flat columns are what's queryable in SQL (e.g. `WHERE salary_min >= 100000`).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `job_key` | string | no | Stable **content identity** of the posting, derived from `source_company_id` + `url` (or title + location, if no per-job URL exists). Unchanged across reappearances. Used by `save_job_postings()` to detect whether an incoming job continues an existing lifetime or starts a new one. Not unique — the same `job_key` can have multiple historical rows over time, one per lifetime; a row's actual identity is just the model's auto `id` primary key. |
| `is_new` | boolean | — (computed, not a column) | `first_scrape_timestamp == latest_scrape_timestamp`. True for a row that hasn't yet survived a second scrape. Exposed as a property on the model (`JobPosting.is_new`) and via `JobPostingOut.is_new`/`resolve_is_new`, same pattern as `is_recommended` below. Drives the new-job notification email — see [architecture.md](./architecture.md) — except on a company's very first-ever scrape, where the email is explicitly suppressed even though every row is technically "new". |
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
| `first_scrape_timestamp` | datetime (tz-aware) | no | When this lifetime was first seen. Fixed for the row's whole life. |
| `latest_scrape_timestamp` | datetime (tz-aware) | no | When this lifetime was most recently seen. Bumped in place on every consecutive scrape that still finds the job — this is what replaces the old per-scrape snapshot rows. |

## Why a row can outlive a single scrape

Every row is one continuous lifetime of a posting: `save_job_postings()` (`app/storage.py`) updates a row's other fields and `latest_scrape_timestamp` in place for as long as the job keeps showing up in consecutive scrapes, instead of inserting a new row each time. A job only ever gets a fresh row when its `job_key` is either seen for the first time, or seen again after being absent from the immediately preceding scrape of that company (a gap) — so two rows never represent overlapping time ranges for the same posting, without needing a database-level uniqueness constraint to enforce it (that's `save_job_postings()`'s job, not the schema's).

## Example row

```json
{
  "job_key": "9f3a1c2b4d5e",
  "source_company_id": "acme-corp",
  "source_url": "https://acme.example.com/careers",
  "first_scrape_timestamp": "2026-08-20T10:00:00Z",
  "latest_scrape_timestamp": "2026-08-27T10:00:00Z",
  "title": "Senior Backend Engineer",
  "url": "https://acme.example.com/careers/senior-backend-engineer",
  "location": "Remote (US)",
  "department": "Engineering",
  "employment_type": "Full-time",
  "salary_min": 120000,
  "salary_max": 150000,
  "salary_currency": "USD",
  "posted_date": "2026-08-14",
  "is_new": false
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
