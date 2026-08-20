# Config Schema

The application's process-level settings live in a YAML file (default: `backend/config/settings.yaml`) with a single top-level `settings` section. The tracked company list itself is **not** in this file — it lives in Postgres (see [architecture.md](./architecture.md)) as the `Company` model, managed via SQL or the `/api/companies` REST endpoints.

## `settings`

Global options for the app:

| Field | Type | Required | Description |
|---|---|---|---|
| `llm.provider` | string | yes | Which LLM provider implementation to use by default (e.g. `"claude"`, `"gemini"`). |
| `llm.model` | string | yes | Model name/id to use for extraction (e.g. `"claude-sonnet-5"`). |
| `llm.api_key_env` | string | yes | Name of the environment variable holding the provider's API key (the key itself is never stored in this file). |
| `playwright.headless` | boolean | no (default `true`) | Whether to run the browser headless. |
| `playwright.timeout_ms` | number | no (default e.g. `30000`) | Navigation/wait timeout per page. |
| `storage.root` | string | no (default `"data/"`) | Root directory for raw HTML debug dumps (job postings themselves go to Postgres, not this directory). |
| `logging.level` | string | no (default `"info"`) | Log verbosity. |

## Example

```yaml
settings:
  llm:
    provider: claude
    model: claude-sonnet-5
    api_key_env: LLM_API_KEY
  playwright:
    headless: true
    timeout_ms: 30000
  storage:
    root: data/
  logging:
    level: info
```

## The `Company` model (Postgres)

Each tracked career page is a row in the `Company` table (see `backend/src/app/models.py`):

| Field | Type | Description |
|---|---|---|
| `id` | string (PK) | Unique slug for the company (e.g. `"acme-corp"`). |
| `name` | string | Human-readable name, for logs/output. |
| `url` | string | Career page URL to scrape. |
| `frequency` | string | Cron expression (e.g. `"0 */6 * * *"` for every 6 hours). |
| `enabled` | boolean | Set `false` to keep a company around but skip scheduling it (default `true`). |

Companies can be added/edited either via SQL directly against the local Postgres database:

```sql
INSERT INTO app_company (id, name, url, frequency, enabled)
VALUES ('acme-corp', 'Acme Corp', 'https://acme.example.com/careers', '0 */6 * * *', true);
```

...or via the REST API (see [architecture.md](./architecture.md) for the full endpoint list):

```sh
curl -X POST http://127.0.0.1:8000/api/companies \
  -H "Content-Type: application/json" \
  -d '{"id": "acme-corp", "name": "Acme Corp", "url": "https://acme.example.com/careers", "frequency": "0 */6 * * *"}'
```
