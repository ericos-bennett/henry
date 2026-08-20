# Config Schema

The application is configured entirely through a YAML file (default: `config/sites.yaml`). It has two top-level sections: `sites` (the list of career pages to track) and `settings` (global options).

## `sites`

Each entry describes one tracked career page:

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique slug for the site (used as the folder name under `data/`). |
| `name` | string | yes | Human-readable name (e.g. company name), for logs/output. |
| `url` | string | yes | Career page URL to scrape. |
| `frequency` | string | yes | How often to scrape, as a cron expression (e.g. `"0 */6 * * *"` for every 6 hours). |
| `enabled` | boolean | no (default `true`) | Set `false` to keep a site in the config but skip scheduling it. |
| `wait_selector` | string | no | CSS selector the Fetcher should wait for before considering the page loaded (useful for JS-rendered listings). |
| `pagination` | object | no | Optional hints for multi-page/infinite-scroll listings (e.g. `{"type": "click", "selector": ".load-more", "max_pages": 5}`). Exact shape to be finalized in V2 — see [roadmap.md](./roadmap.md). |

## `settings`

Global options that apply across all sites unless overridden:

| Field | Type | Required | Description |
|---|---|---|---|
| `llm.provider` | string | yes | Which LLM provider implementation to use by default (e.g. `"claude"`, `"openai"`). |
| `llm.model` | string | yes | Model name/id to use for extraction (e.g. `"claude-sonnet-5"`). |
| `llm.api_key_env` | string | yes | Name of the environment variable holding the provider's API key (the key itself is never stored in this file). |
| `playwright.headless` | boolean | no (default `true`) | Whether to run the browser headless. |
| `playwright.timeout_ms` | number | no (default e.g. `30000`) | Navigation/wait timeout per page. |
| `storage.root` | string | no (default `"data/"`) | Root directory for timestamped output files. |
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

sites:
  - id: acme-corp
    name: Acme Corp
    url: https://acme.example.com/careers
    frequency: "0 */6 * * *"
    wait_selector: ".job-listing"

  - id: globex
    name: Globex
    url: https://globex.example.com/jobs
    frequency: "0 0 * * *"
    enabled: true
```
