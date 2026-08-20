# Job Posting Schema

The structured JSON format that every extracted job listing is validated against before being written to a snapshot file. This is the contract between the Extractor/Validator and the output files (see [architecture.md](./architecture.md)).

Since extraction is LLM-based across arbitrary site layouts, quality and field availability vary by site — most fields beyond `title` and `url` are **best-effort and nullable**.

| Field | Type | Nullable | Description |
|---|---|---|---|
| `job_id` | string | no | Stable identifier for this posting, derived from `source_site_id` + `url` (or title, if no per-job URL exists). Used to identify the same job across runs once diffing is added. |
| `title` | string | no | Job title as posted. |
| `url` | string | yes | Direct link to the job posting, if the page provides one. |
| `location` | string | yes | Location as posted (city/remote/etc.), free text. |
| `department` | string | yes | Team/department, if listed. |
| `employment_type` | string | yes | e.g. "Full-time", "Contract", if listed. |
| `salary_range` | object | yes | Salary info as posted, if listed. Shape: `{ "min": number\|null, "max": number\|null, "currency": string\|null, "raw": string\|null }`. `raw` preserves the original text (e.g. "$120K - $150K/yr") since postings phrase this inconsistently; `min`/`max`/`currency` are the LLM's best-effort parse of it. |
| `description` | string | yes | Whatever summary/description text is present in the career page's listing view (v1 extracts listing-only, no detail-page visits — see [roadmap.md](./roadmap.md)). May be brief or absent depending on the site. |
| `posted_date` | string (ISO 8601 date) | yes | Date the job was posted, if the site exposes it. |
| `source_site_id` | string | no | The `id` of the site from `config/sites.yaml` this posting came from. |
| `source_url` | string | no | The career page URL that was scraped to find this posting. |
| `scraped_at` | string (ISO 8601 datetime) | no | Timestamp of the run that produced this record — matches the containing file's timestamp. |

## Example

```json
{
  "job_id": "acme-corp:senior-backend-engineer-9f3a",
  "title": "Senior Backend Engineer",
  "url": "https://acme.example.com/careers/senior-backend-engineer",
  "location": "Remote (US)",
  "department": "Engineering",
  "employment_type": "Full-time",
  "salary_range": {
    "min": 120000,
    "max": 150000,
    "currency": "USD",
    "raw": "$120K - $150K/yr"
  },
  "description": "We're looking for a Senior Backend Engineer to...",
  "posted_date": "2026-08-14",
  "source_site_id": "acme-corp",
  "source_url": "https://acme.example.com/careers",
  "scraped_at": "2026-08-20T10:00:00Z"
}
```

Each snapshot file (`data/<site_id>/<timestamp>.json`) contains a JSON array of objects in this shape, representing all postings found on that site at that run's timestamp.
