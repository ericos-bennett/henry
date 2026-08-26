# Config Schema

The application's process-level settings live in a YAML file (default: `backend/config/settings.yaml`) with a single top-level `settings` section. The tracked company list itself is **not** in this file — it lives in Postgres (see [architecture.md](./architecture.md)) as the `Company` model, managed via SQL or the `/api/companies` REST endpoints.

## `settings`

Global options for the app:

| Field | Type | Required | Description |
|---|---|---|---|
| `llm.api_key_env` | string | no (default `"LLM_API_KEY"`) | Name of the environment variable holding the provider's API key (the key itself is never stored in this file). |
| `playwright.headless` | boolean | no (default `true`) | Whether to run the browser headless. |
| `playwright.timeout_ms` | number | no (default e.g. `30000`) | Navigation/wait timeout per page. |
| `storage.root` | string | no (default `"data/"`) | Root directory for raw HTML debug dumps (job postings themselves go to Postgres, not this directory). |
| `logging.level` | string | no (default `"info"`) | Log verbosity. |

The LLM provider and model are **not** set in this file — they're read from environment variables in `backend/.env`, so switching providers doesn't require touching a committed file:

| Env var | Description |
|---|---|
| `LLM_PROVIDER` | Which LLM provider implementation to use (`"gemini"` or `"claude"`). |
| `LLM_MODEL` | Model name/id to use for extraction (e.g. `"claude-haiku-4-5"`). |
| `LLM_API_KEY` | API key for whichever provider `LLM_PROVIDER` names (env var name configurable via `llm.api_key_env` above). |

## Email notifications

When a scrape finds a job that's both new (`JobPosting.is_new`) and a match for a user's saved preferences (`UserPreferences`, see [job-schema.md](./job-schema.md)), the app emails that company's owner. Sent via Django's SMTP backend, configured entirely through env vars in `backend/.env` — no code change needed to switch providers:

| Env var | Description |
|---|---|
| `EMAIL_HOST` | SMTP server hostname. Left blank, sending fails (logged, doesn't break the scrape) — notifications are effectively disabled. |
| `EMAIL_PORT` | SMTP port (default `587`). |
| `EMAIL_HOST_USER` | SMTP username. |
| `EMAIL_HOST_PASSWORD` | SMTP password (or app password/API key, depending on the provider). |
| `EMAIL_USE_TLS` | `true`/`false` (default `true`). |
| `DEFAULT_FROM_EMAIL` | `From` address on outgoing mail (defaults to `EMAIL_HOST_USER`). |

Any SMTP-capable provider works: a dedicated Gmail account with an app password, AWS SES's SMTP interface, Mailgun, Postmark, etc.

## Example

```yaml
settings:
  playwright:
    headless: true
    timeout_ms: 30000
  storage:
    root: data/
  logging:
    level: info
```

## The `Company` model (Postgres)

Each tracked career page is a row in the `Company` table (see `backend/src/app/models.py`), owned by exactly one user:

| Field | Type | Description |
|---|---|---|
| `id` | string (PK) | Unique slug for the company (e.g. `"acme-corp"`), derived from `name` on creation via the API. |
| `name` | string | Human-readable name, for logs/output. |
| `url` | string | Career page URL to scrape. |
| `frequency` | string | Cron expression, restricted to a fixed allowed set kept in sync with the frontend's dropdown (see [architecture.md](./architecture.md)) — arbitrary cron expressions are rejected. |
| `enabled` | boolean | Set `false` to keep a company around but skip scheduling it (default `true`). |
| `owner` | FK → `User.id` | The user this company belongs to; all API access is scoped to `owner == request.user`. Nullable only so pre-existing rows created before multi-user auth was added aren't broken. |

Companies can be added/edited either via SQL directly against the local Postgres database:

```sql
INSERT INTO app_company (id, name, url, frequency, enabled, owner_id)
VALUES ('acme-corp', 'Acme Corp', 'https://acme.example.com/careers', '0 */6 * * *', true, 1);
```

...or via the REST API (see [architecture.md](./architecture.md) for the full endpoint list), authenticated as the owning user:

```sh
curl -X POST http://127.0.0.1:8000/api/companies \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp", "url": "https://acme.example.com/careers", "frequency": "0 */6 * * *"}'
```

## Auth & user accounts

There's no self-serve signup — user accounts are created via Django's admin site (`http://127.0.0.1:8000/admin/`, requires a superuser created with `manage.py createsuperuser`). The REST API itself uses Django's session-cookie auth (`POST /api/login` with `{username, password}`, then subsequent requests carry the session cookie). A user's `is_staff` flag (also set via `/admin/`) gates admin-only API actions — currently just `POST /api/companies/scrape-all` (see [architecture.md](./architecture.md)).
